"""Narzędzia MCP o umowach: `ryzyka` (ostrzeżenia dla rodziny) i `tresc_umowy` (paragrafy własnych umów)."""

from ..ai.tools import ToolContext, ToolError, tool
from ..errors import DomainError
from ..services.contracts import family_risks, user_contracts
from ..services.employment_docs import contract_paragraphs, get_source_doc


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


_SALARY_HEADINGS = ("wynagrodzenie",)


@tool(
    "tresc_umowy",
    "Zwraca treść umów zalogowanego rodzica dodanych z e-teczki pracodawcy (umowa o pracę, zlecenie): paragrafy "
    "z numerami (§), np. okres umowy, warunki pracy, uprawnienia rodzicielskie, ubezpieczenie chorobowe. Bez "
    "paragrafu o wynagrodzeniu. Użyj, gdy rodzic pyta o zapisy swojej umowy; cytuj paragraf i nazwę umowy.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def tresc_umowy(ctx: ToolContext, args: dict) -> dict:
    """Tylko umowy właściciela (plik i treść widzi wyłącznie on — partner ma dane przez `profil_rodziny`).
    Wgranych skanów nie przechowujemy, więc dla nich treści nie ma."""
    if ctx.principal.role != "parent":
        raise ToolError("Narzędzie tresc_umowy jest dostępne tylko dla rodzica.")
    uid = ctx.principal.user_id
    out, scanned = [], 0
    for c in await user_contracts(ctx.store, uid):
        if not c.source_doc_id:
            scanned += 1
            continue
        try:
            doc = await get_source_doc(ctx.store, uid, c.source_doc_id, ctx.today)
        except DomainError:
            continue
        out.append(
            {
                "title": doc.title,
                "document": c.filename,
                "employer_name": c.employer_name,
                "paragraphs": [
                    {"heading": h, "text": t}
                    for h, t in contract_paragraphs(doc)
                    if not any(word in h.lower() for word in _SALARY_HEADINGS)
                ],
            }
        )
    note = None
    if not out:
        note = "Rodzic nie dodał jeszcze umów z e-teczki pracodawcy (można to zrobić w onboardingu lub w „Umowach”)."
    elif scanned:
        note = "Część umów została wgrana jako skan — ich treści nie przechowujemy; dane są w `profil_rodziny`."
    return {"contracts": out, "note": note}
