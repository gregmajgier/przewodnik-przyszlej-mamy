"""API silnika uprawnień: ocena profilu, formularz dynamiczny."""

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter

from ..engine.engine import evaluate_user_profile
from ..engine.schemas import EvaluationResponse, UserProfile

router = APIRouter(prefix="/api/silnik", tags=["silnik"])
DATA = Path(__file__).resolve().parents[1] / "data"


@router.post("/ocena")
def ocena(profil: UserProfile, data_oceny: date | None = None) -> EvaluationResponse:
    """Statusy świadczeń, kwoty, ryzyka, wymagane wnioski (pracodawca/ZUS/gmina/USC), kalendarz i walidacja planu."""
    return evaluate_user_profile(profil, dzis=data_oceny)


@router.get("/formularz")
def formularz() -> dict:
    """Definicja formularza dynamicznego (formularz_ui.json)."""
    return json.loads((DATA / "formularz_ui.json").read_text(encoding="utf-8"))
