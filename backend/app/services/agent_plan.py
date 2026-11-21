"""Plan agenta „klikającego” w makiecie portalu: kolejność pól + krótkie uzasadnienia, wartości z prefillu.

Zasady bezpieczeństwa (spec §8, Review Focus planu 08):
- Do modelu trafia wyłącznie **schemat** pól makiety (id, etykieta, typ, czy wartość jest znana) — żadnych
  danych osobowych (PESEL, adres). Wartości do wpisania zawsze pochodzą z `PrefillResult` (profil rodziny),
  więc model nie może ich zmyślić ani podmienić (także przy próbie prompt injection).
- Kroki powstają tylko dla pól ze schematu portalu; wartość niezgodna z typem/wyborem jest odrzucana.
- Brakująca lub odrzucona wartość wymaganego pola trafia do `blocked` (pytanie do rodzica) — nigdy zgadywanie.
- Wywołanie modelu jest za `ai_guard("agent_plan")` (router).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from ..ai.llm import LLM, LLMMessage
from ..errors import DomainError
from .prefill import FormField, PrefillResult, Question, portal_schema, validate_answer

FEATURE = "agent_plan"
MAX_REASON = 200

SYSTEM_PROMPT = (
    "Jesteś asystentem, który planuje wypełnienie formularza w makiecie portalu urzędowego. "
    "Dostajesz listę pól (id, etykieta, typ, czy wartość jest już znana). Zwróć JSON "
    '{"steps":[{"field_id":"...","reason":"..."}]} — kroki w sensownej kolejności wypełniania, tylko dla pól '
    "oznaczonych jako znane, z krótkim uzasadnieniem po polsku (jedno zdanie, bez danych osobowych). "
    "Nie podawaj wartości pól."
)


class DraftStep(BaseModel):
    field_id: str
    reason: str = ""


class PlanDraft(BaseModel):
    """Odpowiedź modelu: tylko kolejność i uzasadnienia."""

    steps: list[DraftStep] = Field(default_factory=list)


class PlanStep(BaseModel):
    field_id: str
    label: str
    value: Any
    reason: str


class AgentPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    blocked: list[Question] = Field(default_factory=list)


def _describe(schema: list[FormField], prefill: PrefillResult) -> str:
    fields = [
        {
            "id": f.id,
            "label": f.label,
            "type": f.type,
            "choices": f.choices,
            "required": f.required,
            "known": f.id in prefill.values,
        }
        for f in schema
    ]
    return json.dumps({"fields": fields}, ensure_ascii=False)


def _valid(field: FormField, value: Any) -> tuple[bool, Any]:
    try:
        return True, validate_answer(field, value)
    except DomainError:
        return False, None


async def build_plan(llm: LLM, portal_id: str, prefill: PrefillResult) -> AgentPlan:
    schema = portal_schema(portal_id)
    draft = await llm.structured(
        [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=_describe(schema, prefill)),
        ],
        PlanDraft,
        feature=FEATURE,
    )
    by_id = {f.id: f for f in schema}
    reasons = {s.field_id: s.reason.strip()[:MAX_REASON] for s in draft.steps if s.field_id in by_id}
    asked = {q.field_id: q for q in prefill.missing}

    steps: list[PlanStep] = []
    blocked: list[Question] = []
    for field in schema:  # kolejność ze schematu portalu (spójna z układem makiety)
        raw = prefill.values.get(field.id)
        ok, value = _valid(field, raw) if raw is not None else (False, None)
        if ok:
            steps.append(
                PlanStep(
                    field_id=field.id,
                    label=field.label,
                    value=value,
                    reason=reasons.get(field.id) or "Wartość z twojego profilu.",
                )
            )
        elif field.id in asked:
            blocked.append(asked[field.id])
        elif field.required or raw is not None:
            # wartość była, ale odrzucona (zły typ/wybór) albo wymagana i pusta — pytamy rodzica
            blocked.append(Question(field_id=field.id, label=field.label, type=field.type, choices=field.choices))
    return AgentPlan(steps=steps, blocked=blocked)
