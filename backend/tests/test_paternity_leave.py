"""Urlop ojcowski w katalogu zgodnie z materiałami ZUS: do ukończenia przez dziecko 12 miesięcy,
zasiłek także dla ubezpieczonych niepracowników (zlecenie, działalność)."""

import json
from pathlib import Path

from app.models.benefit import Benefit
from app.services.matching import match_benefit
from test_matching import born_months_ago, ctx, parent

CATALOG = Path(__file__).resolve().parents[1] / "app" / "data" / "benefits_national.json"


def father(kinds=("employment",)):
    """Urlop ojcowski dotyczy ojca; płeć silnik czyta z PESEL (10. cyfra nieparzysta = mężczyzna)."""
    return parent(kinds=kinds).model_copy(update={"first_name": "Piotr", "pesel": "90010112375"})


def as_viewer(family):
    """Silnik ocenia świadczenie z perspektywy zalogowanego rodzica (`viewer_id`)."""
    return family.model_copy(update={"viewer_id": family.parents[0].user_id})


def paternity() -> Benefit:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return Benefit.model_validate(next(b for b in data["benefits"] if b["id"] == "nat-urlop-ojcowski"))


def test_fits_until_child_is_11_full_months():
    assert match_benefit(as_viewer(ctx([born_months_ago(11)], parents=[father()])), paternity()).status == "fits"


def test_expires_when_child_turns_12_months():
    result = match_benefit(as_viewer(ctx([born_months_ago(12)], parents=[father()])), paternity())
    assert result.status == "no"


def test_description_says_12_months_not_24():
    b = paternity()
    assert "12 miesięcy" in b.description
    assert "24" not in b.description


def test_insured_non_employee_father_also_qualifies():
    for kind in ("mandate", "jdg"):
        family = as_viewer(ctx([born_months_ago(2)], parents=[father((kind,))]))
        assert match_benefit(family, paternity()).status == "fits", kind


def test_does_not_fit_mother():
    mother = parent()  # PESEL z parzystą 10. cyfrą
    assert match_benefit(as_viewer(ctx([born_months_ago(2)], parents=[mother])), paternity()).status == "no"
