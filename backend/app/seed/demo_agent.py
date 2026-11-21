"""Odpowiedź trybu demo dla planu agenta (działa offline, bez modelu): kroki dla pól o znanej wartości.

Rejestrowana przy imporcie pakietu `app.seed` (`register_demo_handler`). Handler dostaje tylko schemat pól
(patrz `services/agent_plan.py`), więc deterministycznie opisuje, skąd pochodzi każda wartość.
"""

from __future__ import annotations

import json

from ..ai.llm import LLMMessage, register_demo_handler
from ..services.agent_plan import FEATURE, DraftStep, PlanDraft


def _demo_plan(messages: list[LLMMessage]) -> PlanDraft:
    try:
        fields = json.loads(messages[-1].content or "{}").get("fields", [])
    except (ValueError, AttributeError, IndexError):
        return PlanDraft()
    steps = [
        DraftStep(field_id=f["id"], reason=f"{f.get('label', 'To pole')}: biorę z twojego profilu.")
        for f in fields
        if isinstance(f, dict) and f.get("known") and "id" in f
    ]
    return PlanDraft(steps=steps)


register_demo_handler(FEATURE, _demo_plan)
