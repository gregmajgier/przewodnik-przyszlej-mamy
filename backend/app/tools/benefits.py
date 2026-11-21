"""Narzędzie MCP `swiadczenia`: dopasowane świadczenia rodziny zalogowanego rodzica (dla czatu)."""

from ..ai.tools import ToolContext, ToolError, tool
from ..errors import DomainError
from ..services.benefit_service import BenefitService


@tool(
    "swiadczenia",
    "Zwraca świadczenia dopasowane do rodziny użytkownika (status: fits = pasuje, maybe = może przysługiwać, "
    "no = nie pasuje) z powodami, pytaniami i źródłem. Parametr status zawęża wynik.",
    {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["fits", "maybe", "no"]}},
        "additionalProperties": False,
    },
)
async def swiadczenia(ctx: ToolContext, args: dict) -> list[dict]:
    if ctx.principal.role != "parent" or not ctx.principal.family_id:
        raise ToolError("Świadczenia są dostępne po założeniu rodziny przez rodzica.")
    try:
        rows = await BenefitService(ctx.store, ctx.today).list_matches(ctx.principal)
    except DomainError as e:
        raise ToolError(e.detail) from None
    wanted = args.get("status")
    return [
        {
            "id": r.benefit.id,
            "nazwa": r.benefit.name,
            "status": r.match.status,
            "dlaczego": r.match.reasons,
            "braki": r.match.unmet,
            "pytania": [q.text for q in r.match.questions],
            "kwota": r.benefit.amount_text,
            "termin": r.deadline_date.isoformat() if r.deadline_date else None,
            "jak_zlozyc": r.benefit.how_to_apply,
            "zrodlo": r.benefit.source_url,
        }
        for r in rows
        if wanted is None or r.match.status == wanted
    ]
