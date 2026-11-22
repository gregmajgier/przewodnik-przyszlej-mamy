"""Seed świadczeń krajowych z `app/data/benefits_national.json` (idempotentny upsert po stałym `id`)."""

import json
from pathlib import Path

from ..models.benefit import Benefit
from ..storage import Store

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "benefits_national.json"
# Wsparcie po stracie dziecka (plan 10): tag `loss_support`, widoczne tylko w trybie jaskółki.
LOSS_FILE = Path(__file__).resolve().parents[1] / "data" / "benefits_loss.json"


# Świadczenia scalone lub usunięte z katalogu — seed kasuje je także w istniejących bazach (inaczej rodzina nadal widziałaby
# duplikat). „Urlop macierzyński” jest teraz częścią „Urlop i zasiłek macierzyński” (`nat-zasilek-macierzynski`).
OBSOLETE_IDS = ("nat-urlop-macierzynski",)


def load_national_benefits() -> list[Benefit]:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [Benefit.model_validate(b) for b in raw["benefits"]]


def load_loss_benefits() -> list[Benefit]:
    return [Benefit.model_validate(b) for b in json.loads(LOSS_FILE.read_text(encoding="utf-8"))]


async def seed_benefits(store: Store) -> None:
    for obsolete in OBSOLETE_IDS:
        await store.delete("benefits", obsolete)
    for benefit in [*load_national_benefits(), *load_loss_benefits()]:
        await store.put("benefits", benefit.model_dump(mode="json"))
