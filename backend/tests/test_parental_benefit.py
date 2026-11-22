"""Świadczenie rodzicielskie (1000 zł): rozstrzygane z danych ZUS, a gdy się nie da, pytanie zadane twierdząco."""

import json
from pathlib import Path

from app.models.benefit import Benefit
from app.services.matching import match_benefit
from test_matching import ctx, parent

CATALOG = Path(__file__).resolve().parents[1] / "app" / "data" / "benefits_national.json"
COND = "zasilek-macierzynski"
KEY = f"benefit:nat-swiadczenie-rodzicielskie:{COND}"


def parental() -> Benefit:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return Benefit.model_validate(next(b for b in data["benefits"] if b["id"] == "nat-swiadczenie-rodzicielskie"))


def pregnant_family(parents, answers=None):
    from test_matching import child

    from datetime import date

    return ctx([child("Maleństwo", due=date(2027, 1, 21), status="expected")], parents=parents, answers=answers)


def test_employee_has_maternity_allowance_so_no_parental_benefit_and_no_question():
    result = match_benefit(pregnant_family([parent(kinds=("employment",))]), parental())
    assert result.status == "no"
    assert result.questions == []
    assert any("Przysługuje Wam zasiłek macierzyński" in u for u in result.unmet)


def test_uninsured_parents_qualify_without_question():
    result = match_benefit(pregnant_family([parent(kinds=())]), parental())
    assert result.status == "fits"
    assert "nie przysługuje Wam zasiłek macierzyński" in result.reasons


def test_unknown_voluntary_sickness_asks_a_positive_question():
    result = match_benefit(pregnant_family([parent(kinds=("mandate",))]), parental())
    assert result.status == "maybe"
    (q,) = result.questions
    assert q.text.startswith("Czy przysługuje ci zasiłek macierzyński")
    assert "nie przysługuje" not in q.text.lower()


def test_answer_yes_means_allowance_exists_so_no_parental_benefit():
    family = pregnant_family([parent(kinds=("mandate",))], answers={KEY: True})
    assert match_benefit(family, parental()).status == "no"


def test_answer_no_means_no_allowance_so_parental_benefit_fits():
    family = pregnant_family([parent(kinds=("mandate",))], answers={KEY: False})
    assert match_benefit(family, parental()).status == "fits"


def test_old_negated_answers_are_not_reused():
    """Odpowiedzi zapisane przy dawnym pytaniu przeczącym („bez-zasilku”) nie mogą być czytane odwrotnie."""
    family = pregnant_family(
        [parent(kinds=("mandate",))], answers={"benefit:nat-swiadczenie-rodzicielskie:bez-zasilku": True}
    )
    assert match_benefit(family, parental()).status == "maybe"
