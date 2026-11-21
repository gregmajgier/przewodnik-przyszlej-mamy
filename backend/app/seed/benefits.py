"""Seed świadczeń krajowych z `app/data/benefits_national.json` (idempotentny upsert po stałym `id`)."""

import json
from pathlib import Path

from ..models.benefit import Benefit
from ..storage import Store

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "benefits_national.json"


def load_national_benefits() -> list[Benefit]:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [Benefit.model_validate(b) for b in raw["benefits"]]


async def seed_benefits(store: Store) -> None:
    for benefit in load_national_benefits():
        await store.put("benefits", benefit.model_dump(mode="json"))
