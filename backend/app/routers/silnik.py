"""API silnika uprawnień: ocena profilu, formularz dynamiczny."""

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends

from ..engine.engine import evaluate_user_profile
from ..engine.schemas import EvaluationResponse, UserProfile
from ..storage import Store, get_store
from ..services.national_parameters import apply_overrides

router = APIRouter(prefix="/api/silnik", tags=["silnik"])
DATA = Path(__file__).resolve().parents[1] / "data"


@router.post("/ocena")
async def ocena(profil: UserProfile, data_oceny: date | None = None, store: Store = Depends(get_store)) -> EvaluationResponse:
    """Statusy świadczeń, kwoty, ryzyka, wymagane wnioski (pracodawca/ZUS/gmina/USC), kalendarz i walidacja planu."""
    doc = await store.get("engine_parameters", "national-active")
    overrides = doc.get("overrides", {}) if doc else {}
    reguly = json.loads((DATA / "reguly_uprawnien.json").read_text(encoding="utf-8"))
    reguly["parametry_drzewo"] = apply_overrides(reguly["parametry_drzewo"], overrides)
    return evaluate_user_profile(profil, rules_json=reguly, dzis=data_oceny)


@router.get("/formularz")
def formularz() -> dict:
    """Definicja formularza dynamicznego (formularz_ui.json)."""
    return json.loads((DATA / "formularz_ui.json").read_text(encoding="utf-8"))
