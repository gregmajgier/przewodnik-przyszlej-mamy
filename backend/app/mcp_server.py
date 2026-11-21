"""Serwer MCP w procesie backendu (SDK `mcp` 2.x) wystawiający rejestr narzędzi z `app.ai.tools` oraz klient MCP.

Architektura (spec §11a, podejście A): backend jest klientem MCP; serwer działa in-process (transport
w pamięci), więc dane rodzica nie opuszczają backendu. Tożsamość rodzica trafia do narzędzi przez
`contextvars` (ustawia ją `McpClient`, z tokena), a nie przez argumenty modelu.

Uwaga dot. SDK: w `mcp` 2.x `FastMCP` zmieniono na `MCPServer`, a klientem jest `mcp.Client`. Narzędzia mają
dowolne schematy JSON z rejestru, więc używamy niskopoziomowego `mcp.server.Server` z `on_list_tools` /
`on_call_tool` zamiast dekoratora opartego na sygnaturach funkcji.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

import mcp_types as types
from mcp import Client
from mcp.server import Server

from .ai.llm import ToolSpec
from .ai.tools import ToolContext, ToolError, call_tool, list_tools, load_all_tools

logger = logging.getLogger("mrodzina.mcp")

MAX_RESULT_CHARS = 14000
NO_CONTEXT = "Brak kontekstu użytkownika — narzędzie nie może zostać wykonane."

_current_ctx: ContextVar[ToolContext | None] = ContextVar("mrodzina_tool_ctx", default=None)


def _default_ctx_factory() -> ToolContext | None:
    return _current_ctx.get()


def _text_result(text: str, *, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


def build_mcp_server(ctx_factory: Callable[[], ToolContext | None] | None = None) -> Server:
    """Buduje serwer MCP z wszystkimi narzędziami z rejestru. `ctx_factory` zwraca `ToolContext` bieżącego
    wywołania (domyślnie z contextvars); brak kontekstu = odmowa (fail-closed)."""
    load_all_tools()
    factory = ctx_factory or _default_ctx_factory

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(name=t.name, description=t.description, input_schema=t.parameters)
                for t in list_tools()
            ]
        )

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        tool_ctx = factory()
        if tool_ctx is None:
            return _text_result(NO_CONTEXT, error=True)
        try:
            result = await call_tool(params.name, dict(params.arguments or {}), tool_ctx)
        except ToolError as e:  # komunikaty ToolError nie zawierają danych użytkownika
            return _text_result(str(e), error=True)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n[…wynik skrócony…]"
        return _text_result(text)

    return Server("mrodzina", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


class McpClient:
    """Klient MCP dla jednej tury czatu. Każde wywołanie otwiera krótkotrwałe połączenie in-process
    (bez trzymania zadań w tle między `yield`-ami streamingu). `ToolContext` ustawiany jest w contextvars."""

    def __init__(self, ctx: ToolContext, server: Server | None = None) -> None:
        self._ctx = ctx
        self._server = server or build_mcp_server()

    async def __aenter__(self) -> McpClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def list_tools(self) -> list[ToolSpec]:
        token = _current_ctx.set(self._ctx)
        try:
            async with Client(self._server) as client:
                result = await client.list_tools()
        finally:
            _current_ctx.reset(token)
        return [
            ToolSpec(name=t.name, description=t.description or "", parameters=dict(t.input_schema))
            for t in result.tools
        ]

    async def call(self, name: str, args: dict) -> str:
        """Wywołuje narzędzie; błędy wracają jako tekst „Błąd narzędzia: …” (dla modelu), nie jako wyjątek."""
        token = _current_ctx.set(self._ctx)
        try:
            async with Client(self._server) as client:
                result = await client.call_tool(name, args)
        except Exception as e:  # noqa: BLE001 - treść wyjątku może zawierać dane; logujemy tylko typ
            logger.error("Wywołanie narzędzia MCP nie powiodło się: %s", type(e).__name__)
            return "Błąd narzędzia: nie udało się wykonać zapytania."
        finally:
            _current_ctx.reset(token)
        text = "".join(c.text for c in result.content if isinstance(c, types.TextContent))
        return f"Błąd narzędzia: {text}" if result.is_error else text
