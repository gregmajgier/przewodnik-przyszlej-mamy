"""Tryb demo czatu (bez modelu AI): wyszukuje przepisy i pokazuje najlepiej pasujące artykuły z linkami.

Rejestrowany jako handler `DemoLLM` dla funkcji `chat` (import w `routers/chat.py`). Działa jak model:
najpierw prosi o wywołanie `szukaj_w_przepisach`, a gdy dostanie wynik — składa z niego odpowiedź.
"""

from __future__ import annotations

import json
import re

from ..ai.llm import LLMMessage, LLMResult, ToolCall, register_demo_handler

MAX_ARTICLES = 3
EXCERPT_CHARS = 380

DEMO_INTRO = (
    "Tryb demo: asystent AI nie jest tu podłączony do modelu, więc pokazuję przepisy najlepiej pasujące do "
    "Twojego pytania. To nie jest porada — sprawdź pełną treść pod linkiem."
)
DEMO_NOT_FOUND = (
    "Tryb demo: nie znalazłem w bazie przepisów nic, co pasuje do tego pytania. Nie będę zgadywać — zapytaj "
    "w urzędzie gminy, w ZUS albo w powiatowym urzędzie pracy."
)


def _excerpt(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[:EXCERPT_CHARS].rsplit(" ", 1)[0]
    return f"{cut}…"


def _tool_results(messages: list[LLMMessage]) -> list[dict]:
    rows: list[dict] = []
    for m in messages:
        body = re.search(r"<wynik_narzedzia[^>]*>\n?(.*?)\n?</wynik_narzedzia>", m.content or "", re.S)
        if not body:
            continue
        try:
            data = json.loads(body.group(1))
        except ValueError:
            continue
        if isinstance(data, dict):
            rows.extend(r for r in data.get("wyniki", []) if isinstance(r, dict) and r.get("artykul"))
    return rows


def demo_chat_handler(messages: list[LLMMessage]) -> LLMResult:
    last_user = max((i for i, m in enumerate(messages) if m.role == "user"), default=None)
    if last_user is None:
        return LLMResult(text=DEMO_NOT_FOUND)
    after = messages[last_user + 1 :]
    if not any(m.role == "tool" for m in after):
        query = (messages[last_user].content or "").strip()[:300]
        if len(query) < 2:
            query = "dziecko"
        return LLMResult(
            tool_calls=[ToolCall(id="demo-szukaj", name="szukaj_w_przepisach", arguments={"query": query, "limit": MAX_ARTICLES})]
        )
    hits = _tool_results(after)[:MAX_ARTICLES]
    if not hits:
        return LLMResult(text=DEMO_NOT_FOUND)
    lines = [DEMO_INTRO, ""]
    for h in hits:
        lines.append(f"• {h['artykul']} — {h.get('akt', '')}: {_excerpt(h.get('tresc', ''))}")
        lines.append(f"  Źródło: {h.get('url', '')}")
    return LLMResult(text="\n".join(lines))


register_demo_handler("chat", demo_chat_handler)
