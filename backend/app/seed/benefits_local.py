"""Przykładowe świadczenia lokalne (plan 07) — idempotentny seed do kolekcji `benefits`."""

import json
from pathlib import Path

from ..models.official_benefit import OfficialBenefit
from ..storage import Store

DATA = Path(__file__).resolve().parent.parent / "data" / "benefits_local_sample.json"


def load_local_samples() -> list[OfficialBenefit]:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return [OfficialBenefit.model_validate(b) for b in raw["benefits"]]


async def seed_local_benefits(store: Store) -> None:
    for b in load_local_samples():
        if await store.get("benefits", b.id) is None:  # nie nadpisujemy zmian urzędnika
            await store.put("benefits", b.model_dump(mode="json"))
