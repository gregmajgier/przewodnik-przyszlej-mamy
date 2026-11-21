"""Narzędzie MCP `ryzyka`: ostrzeżenia o ryzyku utraty świadczeń dla rodziny zalogowanego rodzica."""

from ..ai.tools import ToolContext, ToolError, tool
from ..services.contracts import family_risks


@tool(
    "ryzyka",
    "Zwraca ostrzeżenia o ryzyku utraty świadczeń (z umów, danych ZUS i terminu porodu) dla rodziny "
    "zalogowanego rodzica: ważność, tytuł, wyjaśnienie, co zrobić i do kiedy.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def ryzyka(ctx: ToolContext, args: dict) -> dict:
    if ctx.principal.role != "parent":
        raise ToolError("Narzędzie ryzyka jest dostępne tylko dla rodzica.")
    risks = await family_risks(ctx.store, ctx.principal.user_id, ctx.principal.family_id, ctx.today)
    return {
        "risks": [
            r.model_dump(mode="json", include={"severity", "title", "explanation", "action", "deadline"})
            for r in risks
        ]
    }
