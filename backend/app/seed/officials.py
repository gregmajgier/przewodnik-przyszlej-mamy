from ..config import settings
from ..security import hash_password
from ..storage import Store

# Konta urzędników nadajemy my (brak samorejestracji). Hasło: OFFICIAL_DEFAULT_PASSWORD.
OFFICIALS = [
    {
        "id": "official-krakow",
        "name": "Urzędnik Gminy Kraków",
        "email": "urzednik.krakow@mrodzina.local",
        "unit_id": "unit-krakow",
    },
    {
        "id": "official-malopolska",
        "name": "Urzędnik Województwa Małopolskiego",
        "email": "urzednik.malopolska@mrodzina.local",
        "unit_id": "unit-malopolskie",
    },
]


async def seed_officials(store: Store) -> None:
    password_hash = hash_password(settings.official_default_password)
    for o in OFFICIALS:
        doc = {**o, "role": "official", "persona_id": None, "family_id": None}
        await store.put("users", {**doc, "password_hash": password_hash})
