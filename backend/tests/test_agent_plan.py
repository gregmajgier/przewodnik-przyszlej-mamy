import asyncio
import json
from datetime import date

import pytest

from app.ai.llm import DemoLLM, FakeLLM, LLMError
from app.services.agent_plan import AgentPlan, DraftStep, PlanDraft, build_plan
from app.services.prefill import PrefillResult, Question, portal_schema

GOOD_PESEL = "02070803628"  # poprawna suma kontrolna


def run(coro):
    return asyncio.run(coro)


def full_values(portal_id="pue_800plus", **over):
    from app.services.prefill import valid_pesel

    assert valid_pesel(GOOD_PESEL)
    values = {
        "applicant_first_name": "Anna",
        "applicant_last_name": "Nowak",
        "applicant_pesel": GOOD_PESEL,
        "street": "Floriańska",
        "house_no": "12",
        "postal_code": "30-001",
        "city": "Kraków",
        "citizenship": "polskie",
        "account_number": "12345678901234567890123456",
        "child_first_name": "Maja",
        "child_last_name": "Nowak",
        "child_birth_date": date(2019, 1, 1).isoformat(),
        "child_pesel": GOOD_PESEL,
    }
    values.update(over)
    return values


def plan_for(values, missing=(), llm=None, portal="pue_800plus"):
    llm = llm or FakeLLM().script(PlanDraft())
    return run(build_plan(llm, portal, PrefillResult(values=values, missing=list(missing))))


def test_steps_only_for_schema_fields():
    llm = FakeLLM().script(
        PlanDraft(steps=[DraftStep(field_id="rm -rf", reason="x"), DraftStep(field_id="street", reason="Adres.")])
    )
    plan = plan_for(full_values(), llm=llm)
    ids = [s.field_id for s in plan.steps]
    assert "rm -rf" not in ids and set(ids) <= {f.id for f in portal_schema("pue_800plus")}
    assert ids == [f.id for f in portal_schema("pue_800plus")]  # kolejność ze schematu portalu
    assert {s.field_id: s.reason for s in plan.steps}["street"] == "Adres."
    assert plan.blocked == []


def test_values_come_from_prefill_not_from_the_model():
    """Model dostaje schemat bez wartości i nawet jeśli zwróci własną wartość, plan jej nie użyje."""
    llm = FakeLLM().script(PlanDraft.model_validate({"steps": [{"field_id": "street", "reason": "ok", "value": "HACK"}]}))
    plan = plan_for(full_values(), llm=llm)
    assert {s.field_id: s.value for s in plan.steps}["street"] == "Floriańska"
    prompt = " ".join(m.content or "" for m in llm.calls[0].messages)
    assert GOOD_PESEL not in prompt and "Floriańska" not in prompt and "Anna" not in prompt  # minimalizacja danych
    assert json.loads(llm.calls[0].messages[-1].content)["fields"][0]["known"] is True


def test_invalid_value_for_choice_dropped_and_asked():
    plan = plan_for(full_values(citizenship="marsjańskie"))
    assert "citizenship" not in {s.field_id for s in plan.steps}
    assert [q.field_id for q in plan.blocked] == ["citizenship"]
    assert plan.blocked[0].choices == ["polskie", "inne"]


def test_invalid_pesel_dropped_and_asked():
    plan = plan_for(full_values(child_pesel="11111111111"))
    assert "child_pesel" not in {s.field_id for s in plan.steps}
    assert [q.field_id for q in plan.blocked] == ["child_pesel"]


def test_missing_required_goes_to_blocked_without_guessing():
    values = full_values()
    del values["street"], values["house_no"]
    asked = [Question(field_id="street", label="Ulica"), Question(field_id="house_no", label="Numer domu")]
    plan = plan_for(values, missing=asked)
    assert [q.field_id for q in plan.blocked] == ["street", "house_no"]
    assert {"street", "house_no"}.isdisjoint(s.field_id for s in plan.steps)


def test_required_field_missing_from_prefill_report_is_still_blocked():
    values = full_values()
    del values["account_number"]  # prefill nie zgłosił braku, ale pole jest wymagane w schemacie
    plan = plan_for(values)
    assert [q.field_id for q in plan.blocked] == ["account_number"]


def test_long_model_reason_is_trimmed():
    llm = FakeLLM().script(PlanDraft(steps=[DraftStep(field_id="street", reason="x" * 5000)]))
    step = next(s for s in plan_for(full_values(), llm=llm).steps if s.field_id == "street")
    assert len(step.reason) == 200


def test_demo_handler_builds_plan_from_prefill_without_llm():
    import app.seed  # noqa: F401  (rejestruje handler demo)

    values = full_values()
    del values["street"]
    plan = run(build_plan(DemoLLM(), "pue_800plus", PrefillResult(values=values, missing=[Question(field_id="street", label="Ulica")])))
    assert isinstance(plan, AgentPlan) and len(plan.steps) == len(values)
    assert all(s.reason and s.reason != "Wartość z twojego profilu." for s in plan.steps)  # uzasadnienia z handlera demo
    assert [q.field_id for q in plan.blocked] == ["street"]


def test_llm_error_propagates():
    with pytest.raises(LLMError):
        plan_for(full_values(), llm=FakeLLM().script(LLMError("niedostępny")))


def test_extends_form_portal_uses_form_schema():
    zam_fields = portal_schema("pue_zam")
    assert any(f.id == "pesel" for f in zam_fields)
    plan = plan_for({"pesel": GOOD_PESEL}, portal="pue_zam")
    assert [s.field_id for s in plan.steps] == ["pesel"]
