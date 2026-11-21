"""Narzędzie MCP `swiadczenia`: dopasowania świadczeń dla rodziny zalogowanego rodzica."""

from ..ai.tools import ToolContext, ToolError, tool
from ..errors import DomainError
from ..services.benefit_service import BenefitService


@tool(
    "swiadczenia",
    "Zwraca świadczenia i uprawnienia dopasowane do rodziny zalogowanego rodzica "
    "(status: fits = pasuje, maybe = może przysługiwać, no = nie pasuje) wraz z powodami i kwotą.",
    {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["fits", "maybe", "no"]}},
        "additionalProperties": False,
    },
)
async def swiadczenia(ctx: ToolContext, args: dict) -> list[dict]:
    try:
        matches = await BenefitService(ctx.store).list_matches(ctx.principal.user_id, ctx.today)
    except DomainError as e:
        raise ToolError(e.detail) from None
    status = args.get("status")
    return [
        {
            "id": m.benefit.id,
            "name": m.benefit.name,
            "status": m.match.status,
            "reasons": m.match.reasons,
            "unmet": m.match.unmet,
            "amount": m.benefit.amount_text,
            "source_url": m.benefit.source_url,
        }
        for m in matches
        if status is None or m.match.status == status
    ]
