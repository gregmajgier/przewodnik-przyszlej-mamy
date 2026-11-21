"""Świadczenia „w pracy” w panelu urzędnika Krakowa: szkic i warunki czekające na zatwierdzenie.

Dzięki nim panel pokazuje cały cykl (szkic → warunki → publikacja), a nie tylko gotowe pozycje.
Nieopublikowane — rodzice ich nie widzą. Wyłączane razem z innymi danymi demo (DEMO_APPLICATIONS=0).
"""

from datetime import UTC, datetime, timedelta

from ..config import settings
from ..models.official_benefit import OfficialBenefit
from ..storage import Store

_NOW = datetime.now(UTC)

DEMO_OFFICIAL_BENEFITS = [
    {
        "id": "demo-krakow-polkolonie",
        "name": "Dofinansowanie półkolonii dla dzieci z Krakowa",
        "scope": "municipal",
        "unit_id": "unit-krakow",
        "category": "benefit",
        "description": "Zwrot części kosztów letnich i zimowych półkolonii organizowanych przez krakowskie placówki.",
        "amount_text": "do 300 zł na turnus",
        "annual_value_estimate": 600,
        "deadline_text": "Do 30 dni od zakończenia turnusu.",
        "how_to_apply": "Wniosek online w portalu miasta, z fakturą za turnus.",
        "source_url": "https://www.bip.krakow.pl/",
        "criteria": {"child_age_min_months": 84, "child_age_max_months": 155},
        "extra_text": "Dziecko uczęszcza do szkoły podstawowej na terenie Krakowa. Rodzic rozlicza PIT w Krakowie.",
        "extra_conditions": [
            {
                "id": "szkola-w-krakowie",
                "text": "Dziecko uczęszcza do szkoły podstawowej w Krakowie",
                "kind": "ask",
                "profile_key": None,
                "question": "Czy dziecko chodzi do szkoły podstawowej w Krakowie?",
            },
            {
                "id": "pit-w-krakowie",
                "text": "Rodzic rozlicza PIT w Krakowie",
                "kind": "auto",
                "profile_key": "pays_taxes_in_municipality",
                "question": "Czy rozliczasz PIT w Krakowie?",
            },
        ],
        "conditions_approved": False,
        "status": "awaiting_approval",
        "created_by": "official-krakow",
        "updated_at": (_NOW - timedelta(hours=3)).isoformat(),
    },
    {
        "id": "demo-krakow-wyprawka",
        "name": "Krakowska wyprawka dla noworodka",
        "scope": "municipal",
        "unit_id": "unit-krakow",
        "category": "perk",
        "description": "Paczka z najpotrzebniejszymi rzeczami dla dziecka, do odbioru w urzędzie stanu cywilnego.",
        "amount_text": "paczka o wartości ok. 400 zł",
        "annual_value_estimate": None,
        "deadline_text": None,
        "how_to_apply": "",
        "source_url": "",
        "criteria": {"child_age_max_months": 5},
        "extra_text": None,
        "extra_conditions": [],
        "conditions_approved": False,
        "status": "draft",
        "created_by": "official-krakow",
        "updated_at": (_NOW - timedelta(days=2)).isoformat(),
    },
]


async def seed_demo_official_benefits(store: Store) -> None:
    if not settings.demo_applications:
        return
    for raw in DEMO_OFFICIAL_BENEFITS:
        if await store.get("benefits", raw["id"]) is None:  # nie nadpisujemy zmian urzędnika
            await store.put("benefits", OfficialBenefit.model_validate(raw).model_dump(mode="json"))
