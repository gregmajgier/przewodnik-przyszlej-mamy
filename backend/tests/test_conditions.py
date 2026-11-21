import asyncio

import pytest

from app.ai.llm import DemoLLM, FakeLLM, LLMError
from app.seed import demo_conditions  # noqa: F401
from app.services.conditions import (
    ConditionList,
    ConditionsError,
    RawCondition,
    ResolutionExtract,
    extract_conditions,
    normalize_conditions,
    prefill_from_resolution,
)


def run(c):
    return asyncio.run(c)


def test_unknown_profile_key_becomes_ask():
    fake = FakeLLM().script(
        ConditionList(conditions=[RawCondition(text="Posiada psa", kind="auto", profile_key="has_dog")])
    )
    [c] = run(extract_conditions(fake, "Posiada psa."))
    assert c.kind == "ask" and c.profile_key is None
    assert c.question.endswith("?")


def test_known_profile_key_stays_auto():
    fake = FakeLLM().script(
        ConditionList(conditions=[RawCondition(text="Dziecko w żłobku publicznym", kind="auto", profile_key="child_in_public_nursery")])
    )
    [c] = run(extract_conditions(fake, "x"))
    assert c.kind == "auto" and c.profile_key == "child_in_public_nursery"


def test_duplicates_removed():
    fake = FakeLLM().script(
        ConditionList(
            conditions=[
                RawCondition(text="Zameldowanie w gminie", kind="ask"),
                RawCondition(text="zameldowanie  w gminie.", kind="ask"),
                RawCondition(text="   ", kind="ask"),
                RawCondition(text=None),
                RawCondition(text="Dochód poniżej progu", kind="ask", question="Czy dochód jest poniżej progu"),
            ]
        )
    )
    out = run(extract_conditions(fake, "x"))
    assert [c.text for c in out] == ["Zameldowanie w gminie", "Dochód poniżej progu"]
    assert out[1].question == "Czy dochód jest poniżej progu?"
    assert len({c.id for c in out}) == 2


def test_ids_unique_slug():
    out = normalize_conditions(
        [{"text": "Żłobek ąę", "kind": "ask"}, {"text": "Żłobek ĄĘ!", "kind": "ask"}, {"text": "Inny", "kind": "ask"}]
    )
    assert out[0].id == "zlobek-ae"
    assert len(out) == 2


def test_empty_text_returns_empty_without_llm_call():
    fake = FakeLLM()
    assert run(extract_conditions(fake, "   ")) == []
    assert fake.calls == []


def test_llm_error_raises_conditions_error():
    fake = FakeLLM().script(LLMError("x"))
    with pytest.raises(ConditionsError) as e:
        run(extract_conditions(fake, "Coś"))
    assert "dodaj je ręcznie" in e.value.detail


def test_prefill_maps_age_and_income():
    fake = FakeLLM().script(
        ResolutionExtract(
            name="Dopłata do żłobka",
            child_age_min_months=35,
            child_age_max_months=12,
            max_income_per_person=2500,
            min_children=0,
            extra_text="Zameldowanie 12 mies.",
        )
    )
    d = run(prefill_from_resolution(fake, "Uchwała ..."))
    assert d.name == "Dopłata do żłobka"
    assert (d.criteria.child_age_min_months, d.criteria.child_age_max_months) == (12, 35)
    assert d.criteria.max_income_per_person == 2500
    assert d.criteria.min_children is None
    assert d.extra_text == "Zameldowanie 12 mies."


def test_demo_handler_extracts_residency_condition():
    out = run(extract_conditions(DemoLLM(), "Zameldowanie w gminie od co najmniej 12 miesięcy."))
    assert len(out) == 1
    assert out[0].kind in ("ask", "auto")
    assert "12" in out[0].text and out[0].question.endswith("?")


def test_demo_prefill_from_resolution():
    text = (
        "Uchwała nr XII/1/2026 Rady Miasta w sprawie dopłaty do opieki żłobkowej.\n"
        "Dopłata przysługuje na dziecko do ukończenia 3 lat w wysokości 500 zł miesięcznie, "
        "jeżeli dochód na osobę nie przekracza 3000 zł. Rodzic musi być zameldowany w gminie od 12 miesięcy."
    )
    d = run(prefill_from_resolution(DemoLLM(), text))
    assert d.name.startswith("Dopłaty do opieki")
    assert d.criteria.child_age_max_months == 35
    assert d.criteria.max_income_per_person == 3000
    assert d.amount_text.startswith("500 zł")
    assert "zameldowany" in d.extra_text
