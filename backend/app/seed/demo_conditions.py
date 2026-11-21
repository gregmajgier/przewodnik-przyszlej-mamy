"""Odpowiedzi trybu demo (bez Azure) dla funkcji AI planu 07: warunki z „Dodatkowych wymogów”
i wypełnianie z tekstu uchwały. Proste reguły słów kluczowych — wystarczające do pokazu.
"""

import re

from ..ai.llm import LLMMessage, register_demo_handler
from ..services.conditions import (
    FEATURE_CONDITIONS,
    FEATURE_PREFILL,
    ConditionList,
    RawCondition,
    ResolutionExtract,
)


def _user_text(messages: list[LLMMessage]) -> str:
    user = next((m for m in reversed(messages) if m.role == "user"), None)
    text = (user.content or "") if user else ""
    return re.sub(r"</?(wymogi|uchwala)>", "", text).strip()


def _condition(sentence: str) -> RawCondition:
    low = sentence.casefold()
    if ("zameld" in low or "zamieszk" in low) and (m := re.search(r"(\d+)\s*mies", low)):
        months = m.group(1)
        return RawCondition(
            text=f"Zameldowanie w gminie od co najmniej {months} miesięcy",
            kind="ask",
            question=f"Czy jesteś zameldowana/zameldowany w gminie od co najmniej {months} miesięcy?",
        )
    if "żłob" in low and "publiczn" in low and "niepubliczn" not in low:
        return RawCondition(text=sentence, kind="auto", profile_key="child_in_public_nursery")
    if "żłob" in low or "klub dziecięc" in low:
        return RawCondition(text=sentence, kind="auto", profile_key="child_in_private_nursery")
    if "pit" in low or "podat" in low:
        return RawCondition(text=sentence, kind="auto", profile_key="pays_taxes_in_municipality")
    if "pracuj" in low or "zatrudn" in low:
        return RawCondition(text=sentence, kind="auto", profile_key="parent_employed")
    return RawCondition(text=sentence, kind="ask")


def _conditions(messages: list[LLMMessage]) -> ConditionList:
    parts = re.split(r"[.;\n]+|\s-\s|•", _user_text(messages))
    return ConditionList(conditions=[_condition(p.strip()) for p in parts if len(p.strip()) > 3])


def _prefill(messages: list[LLMMessage]) -> ResolutionExtract:
    text = _user_text(messages)
    low = text.casefold()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = None
    if m := re.search(r"w sprawie\s+(.+?)(?:\.|\n|$)", text, re.IGNORECASE):
        name = m.group(1).strip()
        name = name[0].upper() + name[1:]
    elif lines:
        name = lines[0][:120]
    age_max = None
    if m := re.search(r"do (?:ukończenia )?(\d+)\s*(?:lat|roku)", low):
        age_max = int(m.group(1)) * 12 - 1
    elif m := re.search(r"do (?:ukończenia )?(\d+)\s*miesi", low):
        age_max = int(m.group(1)) - 1
    income = None
    if m := re.search(r"dochód[^.]*?nie przekracza\s*(\d[\d\s]*(?:,\d+)?)\s*zł", low):
        income = float(m.group(1).replace(" ", "").replace(",", "."))
    amount = None
    if m := re.search(r"w wysokości\s*(\d[\d\s]*(?:,\d+)?\s*zł[^.,;]*)", text, re.IGNORECASE):
        amount = m.group(1).strip()
    extra = None
    if m := re.search(r"((?:zameldowan|zamieszkuj)[^.]*\.)", text, re.IGNORECASE):
        extra = m.group(1).strip()
    return ResolutionExtract(
        name=name,
        description=lines[1][:400] if len(lines) > 1 else None,
        amount_text=amount,
        child_age_min_months=0 if age_max is not None else None,
        child_age_max_months=age_max,
        max_income_per_person=income,
        min_children=3 if "trojga" in low or "3+" in low or "wielodzietn" in low else None,
        extra_text=extra,
    )


register_demo_handler(FEATURE_CONDITIONS, _conditions)
register_demo_handler(FEATURE_PREFILL, _prefill)
