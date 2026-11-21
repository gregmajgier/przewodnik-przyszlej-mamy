"""Przykład narzędzia (tylko dla testów; nazwa z `_` => nie jest auto-importowany)."""

from ..ai.tools import ToolContext, tool


def register_example() -> None:
    @tool(
        "echo",
        "Zwraca podany tekst i identyfikator użytkownika.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )
    async def echo(ctx: ToolContext, args: dict) -> dict:
        return {"text": args["text"], "user_id": ctx.principal.user_id}
