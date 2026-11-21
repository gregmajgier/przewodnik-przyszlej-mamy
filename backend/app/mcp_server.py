"""Serwer MCP (in-process) wystawiający rejestr narzędzi z `app.ai.tools` oraz klient dla pętli czatu.

Backend jest klientem MCP: `McpClient` łączy się z serwerem w tym samym procesie (transport w pamięci).
Kontekst narzędzi (`ToolContext`: Principal z tokena, store, data) jest zamknięty w `ctx_factory` serwera
— model nigdy nie podaje tożsamości w argumentach. Każde wywołanie otwiera krótką sesję, bo klient MCP
używa task group, której nie wolno trzymać otwartej przez `yield` generatora strumienia.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import mcp_types as types
from mcp import Client
from mcp.server import Server

from .ai.llm import ToolSpec
from .ai.tools import ToolContext, ToolError, call_tool, list_tools, load_all_tools

logger = logging.getLogger("mrodzina.mcp")

SERVER_NAME = "mrodzina"
MAX_RESULT_CHARS = 12000


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def build_mcp_server(ctx_factory: Callable[[], ToolContext]) -> Server:
    """Serwer MCP z wszystkimi narzędziami zarejestrowanymi w `app.ai.tools` (auto-import `app/tools/*`)."""
    load_all_tools()

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[types.Tool(name=t.name, description=t.description, input_schema=t.parameters) for t in list_tools()]
        )

    async def on_call_tool(ctx, params) -> types.CallToolResult:
        try:
            result = await call_tool(params.name, params.arguments or {}, ctx_factory())
        except ToolError as e:
            return types.CallToolResult(content=[types.TextContent(text=str(e))], is_error=True)
        text = _as_text(result)[:MAX_RESULT_CHARS]
        return types.CallToolResult(content=[types.TextContent(text=text)], is_error=False)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


class McpClient:
    """Klient MCP w procesie. `call` nie rzuca z powodu błędu narzędzia — zwraca tekst błędu dla modelu."""

    def __init__(self, tool_context: ToolContext) -> None:
        self._server = build_mcp_server(lambda: tool_context)

    async def list_tools(self) -> list[ToolSpec]:
        async with Client(self._server) as client:
            result = await client.list_tools()
        return [
            ToolSpec(name=t.name, description=t.description or "", parameters=dict(t.input_schema))
            for t in result.tools
        ]

    async def call(self, name: str, args: dict) -> str:
        try:
            async with Client(self._server) as client:
                result = await client.call_tool(name, args)
        except Exception as e:  # noqa: BLE001 - błąd transportu MCP; treść nie trafia do logów
            logger.error("Wywołanie MCP %s nie powiodło się: %s", name, type(e).__name__)
            return f"Błąd narzędzia {name}: nie udało się wykonać zapytania."
        text = "\n".join(c.text for c in result.content if isinstance(c, types.TextContent))
        if result.is_error:
            return f"Błąd narzędzia {name}: {text}"
        return text
