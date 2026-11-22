"""Treści katalogu świadczeń zgodne z materiałami ZUS do zadania (ZUS jest tu źródłem nadrzędnym)."""

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "app" / "data" / "benefits_national.json"


def entry(benefit_id: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return next(b for b in data["benefits"] if b["id"] == benefit_id)


def test_pregnancy_sickness_states_waiting_periods_instead_of_none():
    text = entry("nat-zasilek-chorobowy-ciaza")["description"]
    assert "bez okresu wyczekiwania" not in text
    assert "30 dniach" in text and "90 dniach" in text
    assert "270 dni" in text


def test_maternity_allowance_has_no_waiting_period():
    extra = entry("nat-zasilek-macierzynski")["extra_text"]
    assert "90 dni" not in extra
    assert "w dniu porodu" in extra
