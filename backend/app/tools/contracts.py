"""Narzędzie MCP `ryzyka`: ostrzeżenia o ryzyku utraty świadczeń z umów i ZUS dla rodziny wołającego."""

from ..ai.tools import ToolContext, tool
from ..services.contracts import ContractService


@tool(
    "ryzyka",
    "Zwraca ostrzeżenia o ryzyku utraty świadczeń rodziny (np. umowa zlecenie bez chorobowego, "
    "umowa na czas określony kończąca się przed porodem, zadłużenie składkowe).",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def ryzyka(ctx: ToolContext, args: dict) -> list[dict]:
    risks = await ContractService(ctx.store).family_risks(ctx.principal.family_id, ctx.today)
    return [r.model_dump(mode="json") for r in risks]
