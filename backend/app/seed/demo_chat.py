"""Tryb demo czatu (bez modelu): wyszukuje przepisy przez narzędzie MCP i wypisuje najtrafniejsze artykuły.

Handler przechodzi przez prawdziwą pętlę czatu: w pierwszej rundzie „prosi” o `szukaj_w_przepisach`, w drugiej
składa odpowiedź z wyniku narzędzia (bez interpretacji — to nie jest porada, tylko wskazanie przepisów).
"""

from __future__ import annotations

import json
import re

from ..ai.llm import LLMMessage, LLMResult, ToolCall, register_demo_handler

_RESULT_RE = re.compile(r"<wynik_narzedzia[^>]*>\n(.*)\n</wynik_narzedzia>", re.DOTALL)
_SNIPPET = 320

NO_RESULTS = (
    "Tryb demo: w bazie przepisów nie znalazłam nic pasującego do tego pytania, więc nie zgaduję. "
    "Zapytaj w urzędzie gminy, ZUS albo powiatowym urzędzie pracy."
)


def _last_user_index(messages: list[LLMMessage]) -> int:
    return max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)


def _demo_chat(messages: list[LLMMessage]) -> LLMResult:
    idx = _last_user_index(messages)
    question = (messages[idx].content or "") if idx >= 0 else ""
    tool_messages = [m for m in messages[idx + 1 :] if m.role == "tool"]
    if not tool_messages:
        query = question.strip()[:300]
        if len(query) < 2:
            return LLMResult(text="Napisz proszę pytanie, np. „Jak działa urlop macierzyński?”.")
        return LLMResult(tool_calls=[ToolCall(id="demo-law-1", name="szukaj_w_przepisach", arguments={"query": query})])

    match = _RESULT_RE.search(tool_messages[-1].content or "")
    try:
        results = json.loads(match.group(1)).get("results", []) if match else []
    except (ValueError, AttributeError):
        results = []
    if not results:
        return LLMResult(text=NO_RESULTS)
    lines = [
        "Tryb demo: asystent AI nie jest tu podłączony do modelu, więc pokazuję najtrafniejsze przepisy "
        "z lokalnej bazy — bez interpretacji.",
        "",
    ]
    for r in results[:3]:
        text = r["text"]
        snippet = text[:_SNIPPET].rsplit(" ", 1)[0] + "…" if len(text) > _SNIPPET else text
        lines += [f"**{r['act']}, {r['article']}** — {snippet}", f"Źródło: {r['url']}", ""]
    return LLMResult(text="\n".join(lines).strip())


register_demo_handler("chat", _demo_chat)
