"""Publiczna ścieżka /jaskolka: sytuacje, checklisty i baza fundacji. Bez logowania, bez cookies."""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query

from ..errors import DomainError

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "jaskolka.json"

router = APIRouter(prefix="/api/jaskolka", tags=["jaskolka"])


@lru_cache
def _load() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _situation(situation_id: str) -> dict:
    for s in _load()["situations"]:
        if s["id"] == situation_id:
            return s
    raise DomainError(404, "Nie ma takiej sytuacji. Wróć do listy i wybierz jedną z dostępnych.")


@router.get("/situations")
def list_situations():
    return [{"id": s["id"], "label": s["label"], "intro": s["intro"]} for s in _load()["situations"]]


@router.get("/situations/{situation_id}")
def get_situation(situation_id: str):
    return _situation(situation_id)


@router.get("/foundations")
def list_foundations(situation: str | None = Query(default=None)):
    foundations = _load()["foundations"]
    if situation is None:
        return foundations
    _situation(situation)  # nieznana sytuacja -> 404 po polsku
    return [f for f in foundations if situation in f["situations"]]
