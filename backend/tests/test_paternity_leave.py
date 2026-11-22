"""Urlop ojcowski w katalogu zgodnie z materiałami ZUS: do ukończenia przez dziecko 12 miesięcy,
zasiłek także dla ubezpieczonych niepracowników (zlecenie, działalność)."""

import json
from pathlib import Path

from app.models.benefit import Benefit
from app.services.matching import match_benefit
from test_matching import born_months_ago, ctx, parent

CATALOG = Path(__file__).resolve().parents[1] / "app" / "data" / "benefits_national.json"


def paternity() -> Benefit:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return Benefit.model_validate(next(b for b in data["benefits"] if b["id"] == "nat-urlop-ojcowski"))


def test_fits_until_child_is_11_full_months():
    assert match_benefit(ctx([born_months_ago(11)]), paternity()).status == "fits"


def test_expires_when_child_turns_12_months():
    result = match_benefit(ctx([born_months_ago(12)]), paternity())
    assert result.status == "no"


def test_description_says_12_months_not_24():
    b = paternity()
    assert "12 miesięcy" in b.description
    assert "24" not in b.description


def test_insured_non_employee_father_also_qualifies():
    for kind in ("mandate", "jdg"):
        family = ctx([born_months_ago(2)], parents=[parent(kinds=(kind,))])
        assert match_benefit(family, paternity()).status == "fits", kind
