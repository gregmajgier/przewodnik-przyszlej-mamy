"""Seed katalogu świadczeń krajowych z `app/data/benefits_national.json` (idempotentny: stałe id)."""

import json
from pathlib import Path

from ..models.benefit import Benefit
from ..storage import Store

DATA = Path(__file__).resolve().parents[1] / "data"


def load_national_benefits() -> list[Benefit]:
    raw = json.loads((DATA / "benefits_national.json").read_text(encoding="utf-8"))
    return [Benefit.model_validate(b) for b in raw["benefits"]]


async def seed_benefits(store: Store) -> None:
    for benefit in load_national_benefits():
        await store.put("benefits", benefit.model_dump(mode="json"))
