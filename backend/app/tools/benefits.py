"""Narzędzie MCP `swiadczenia`: dopasowania świadczeń dla rodziny zalogowanego rodzica."""

from ..ai.tools import ToolContext, ToolError, tool
from ..errors import DomainError
from ..models.benefit import Benefit
from ..services.benefit_service import BenefitMatch, BenefitService
from ..services.matching import MatchResult
from ..services.laws import tokenize

# Rdzenie zbyt ogólne, żeby wskazywać konkretne świadczenie (po obcięciu do prefiksu, jak w `tokenize`).
GENERIC_STEMS = {"dziec", "rodzi", "wnios", "swiad", "przys", "wynos", "pomoc", "zlozy", "zapis", "kwota"}
MAX_QUERY_RESULTS = 3


def relevance(query: str, m: BenefitMatch) -> int:
    """Ile znaczących słów pytania występuje w nazwie, kwocie i tagach świadczenia (0 = nie dotyczy)."""
    wanted = set(tokenize(query)) - GENERIC_STEMS
    have = set(tokenize(" ".join([m.benefit.name, m.benefit.amount_text or "", *m.benefit.tags])))
    return len(wanted & have)


@tool(
    "swiadczenia",
    "Zwraca świadczenia i uprawnienia dopasowane do rodziny zalogowanego rodzica "
    "(status: fits = pasuje, maybe = może przysługiwać, no = nie pasuje) wraz z powodami i kwotą. "
    "Z parametrem `query` (np. „becikowe”) zwraca tylko najtrafniejsze świadczenia, z opisem i sposobem złożenia wniosku.",
    {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["fits", "maybe", "no"]},
            "query": {"type": "string", "maxLength": 300},
        },
        "additionalProperties": False,
    },
)
async def swiadczenia(ctx: ToolContext, args: dict) -> list[dict]:
    status = args.get("status")
    query = (args.get("query") or "").strip()
    try:
        matches = await BenefitService(ctx.store).list_matches(ctx.principal.user_id, ctx.today)
    except DomainError as e:
        if not query:
            raise ToolError(e.detail) from None
        # rodzic bez rodziny/profilu pyta o konkretne świadczenie: odpowiadamy ogólnie z katalogu krajowego (bez dopasowania)
        docs = await ctx.store.find("benefits", status="published")
        matches = [
            BenefitMatch(benefit=b, match=MatchResult(status="no", reasons=[], unmet=[], questions=[]))
            for b in (Benefit.model_validate(d) for d in docs)
            if b.scope == "national"
        ]
        general = True
    else:
        general = False
    matches = [m for m in matches if general or status is None or m.match.status == status]
    if query:
        scored = sorted(((relevance(query, m), m) for m in matches), key=lambda x: (-x[0], x[1].benefit.name))
        top = scored[0][0] if scored else 0
        # tylko najtrafniejsze (np. „urlop macierzyński” nie ma przywlekać „urlopu ojcowskiego”, który pasuje słabiej)
        matches = [m for score, m in scored if score > 0 and score == top][:MAX_QUERY_RESULTS]
    out = []
    for m in matches:
        item = {
            "id": m.benefit.id,
            "name": m.benefit.name,
            "status": None if general else m.match.status,
            "reasons": m.match.reasons,
            "unmet": m.match.unmet,
            "amount": m.benefit.amount_text,
            "source_url": m.benefit.source_url,
        }
        if query:  # szczegóły tylko dla trafień — pełna lista bez `query` musi mieścić się w limicie wyniku narzędzia
            item["description"] = m.benefit.description
            item["how_to_apply"] = m.benefit.how_to_apply
        out.append(item)
    return out
