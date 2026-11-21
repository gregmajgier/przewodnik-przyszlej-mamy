"""Narzędzie MCP `kalendarz`: najbliższe terminy, wnioski i ostrzeżenia rodziny zalogowanego rodzica."""

from datetime import timedelta

from ..ai.tools import ToolContext, ToolError, tool
from ..errors import DomainError
from ..services.calendar_service import family_calendar


@tool(
    "kalendarz",
    "Zwraca najbliższe wpisy kalendarza rodziny: terminy wniosków o świadczenia, złożone wnioski (kto złożył, "
    "status) i ostrzeżenia. Parametr `days` — ile dni naprzód (domyślnie 90); wpisy po terminie też są zwracane.",
    {
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 730}},
        "additionalProperties": False,
    },
)
async def kalendarz(ctx: ToolContext, args: dict) -> dict:
    if ctx.principal.role != "parent":
        raise ToolError("Kalendarz jest dostępny tylko dla rodzica.")
    try:
        events = await family_calendar(ctx.store, ctx.principal.user_id, ctx.today)
    except DomainError as e:
        raise ToolError(e.detail) from None
    horizon = ctx.today + timedelta(days=args.get("days", 90))
    picked = [e for e in events if not e.done and (e.due_date is None or e.due_date <= horizon)]
    return {
        "events": [
            e.model_dump(
                mode="json",
                include={"kind", "title", "summary", "due_date", "effect_until", "overdue", "actor_name", "status"},
            )
            for e in picked[:30]
        ]
    }
