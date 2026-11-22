"""Tryb demo czatu (bez modelu): odpowiada z lokalnych danych — katalogu świadczeń rodziny i bazy przepisów.

Handler przechodzi przez prawdziwą pętlę czatu: w pierwszej rundzie „prosi” o narzędzia `swiadczenia` (z `query`:
tylko trafne świadczenia dla tej rodziny) i `szukaj_w_przepisach`, w drugiej składa odpowiedź:

1. **konkretna odpowiedź na początku** — gdy pytanie dotyczy świadczenia z katalogu: nazwa, kwota, co to znaczy dla
   tej rodziny, jak złożyć wniosek i oficjalne źródło (np. „Ile wynosi becikowe?” → „1000 zł jednorazowo”);
2. gdy katalog nic nie wskazuje, a przepisy tak — krótkie wskazanie najtrafniejszych artykułów (to nie jest porada).
"""

from __future__ import annotations

import json
import re

from ..ai.llm import LLMMessage, LLMResult, ToolCall, register_demo_handler

_BLOCK_RE = re.compile(r'<wynik_narzedzia nazwa="([^"]*)">\n(.*?)\n</wynik_narzedzia>', re.DOTALL)
_SNIPPET = 200
_MAX_HOW = 260
_MAX_LAWS = 2
_MAX_BENEFITS = 2

DEMO_NOTE = "Odpowiedź z lokalnej bazy świadczeń i przepisów (tryb demo, bez modelu AI), nie jest poradą prawną."

NO_RESULTS = (
    "Tryb demo: w bazie przepisów nie znalazłam nic pasującego do tego pytania, więc nie zgaduję. "
    "Zapytaj w urzędzie gminy, ZUS albo powiatowym urzędzie pracy."
)

_SITUATION = {
    "fits": "Dla Waszej rodziny: pasuje",
    "maybe": "Dla Waszej rodziny: może Ci przysługiwać",
    "no": "Dla Waszej rodziny: na razie nie pasuje",
}


def _last_user_index(messages: list[LLMMessage]) -> int:
    return max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)


def _tool_payloads(messages: list[LLMMessage]) -> dict[str, object]:
    """Wyniki narzędzi z ostatniej tury: nazwa narzędzia → zdekodowany JSON (albo None przy błędzie)."""
    out: dict[str, object] = {}
    for m in messages:
        if m.role != "tool":
            continue
        for name, body in _BLOCK_RE.findall(m.content or ""):
            try:
                out[name] = json.loads(body)
            except ValueError:
                out[name] = None
    return out


def _first_sentence(text: str, limit: int = _SNIPPET) -> str:
    text = " ".join(text.split())
    cut = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return cut if len(cut) <= limit else cut[:limit].rsplit(" ", 1)[0] + "…"


def _benefit_block(b: dict) -> list[str]:
    amount = (b.get("amount") or "").strip().rstrip(".")
    lines = [f"**{b['name']}**" + (f": {amount}." if amount else ".")]
    if b.get("description"):
        lines.append(_first_sentence(b["description"]))
    status = b.get("status")
    if status in ("fits", "maybe"):
        reason = ((b.get("reasons") or [""])[0]).strip().rstrip(".")
        lines.append(_SITUATION[status] + (f", bo {reason}." if reason else "."))
    elif status == "no":
        reason = ((b.get("unmet") or [""])[0]).strip().rstrip(".")
        lines.append(_SITUATION[status] + (f". {reason}." if reason else "."))
    if b.get("how_to_apply") and status != "no":
        how = " ".join(b["how_to_apply"].split())
        lines.append("Jak złożyć: " + (how if len(how) <= _MAX_HOW else how[:_MAX_HOW].rsplit(" ", 1)[0] + "…"))
    if b.get("source_url"):
        lines.append(f"Źródło: {b['source_url']}")
    return lines


def _demo_chat(messages: list[LLMMessage]) -> LLMResult:
    idx = _last_user_index(messages)
    question = (messages[idx].content or "") if idx >= 0 else ""
    tool_messages = [m for m in messages[idx + 1 :] if m.role == "tool"]
    if not tool_messages:
        query = question.strip()[:300]
        if len(query) < 2:
            return LLMResult(text="Napisz proszę pytanie, np. „Jak działa urlop macierzyński?”.")
        return LLMResult(
            tool_calls=[
                ToolCall(id="demo-benefits-1", name="swiadczenia", arguments={"query": query}),
                ToolCall(id="demo-law-1", name="szukaj_w_przepisach", arguments={"query": query}),
            ]
        )

    payloads = _tool_payloads(messages[idx + 1 :])
    benefits = payloads.get("swiadczenia")
    law_payload = payloads.get("szukaj_w_przepisach")
    laws = law_payload.get("results", []) if isinstance(law_payload, dict) else []

    answer: list[str] = []
    # 1. świadczenie z katalogu, o które pyta rodzic (narzędzie zwraca tylko trafne, najlepsze pierwsze)
    if isinstance(benefits, list):
        for b in [b for b in benefits if isinstance(b, dict) and b.get("name")][:_MAX_BENEFITS]:
            answer += _benefit_block(b) + [""]

    # 2. katalog nie zna tematu: wskazujemy najtrafniejsze artykuły (krótko, bez interpretacji)
    if not answer:
        cited = [r for r in laws if isinstance(r, dict) and r.get("url")][:_MAX_LAWS]
        if not cited:
            return LLMResult(text=NO_RESULTS)
        answer += ["Nie mam w trybie demo gotowej odpowiedzi na to pytanie. Najtrafniejsze przepisy (bez interpretacji):", ""]
        for r in cited:
            text = " ".join(str(r.get("text", "")).split())
            snippet = text[:_SNIPPET].rsplit(" ", 1)[0] + "…" if len(text) > _SNIPPET else text
            answer += [f"**{r.get('act', '')}, {r.get('article', '')}**: {snippet}", f"Źródło: {r['url']}", ""]

    answer.append(DEMO_NOTE)
    return LLMResult(text="\n".join(answer).strip())


register_demo_handler("chat", _demo_chat)
