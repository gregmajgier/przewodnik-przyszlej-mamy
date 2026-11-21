import logging

from ..config import DEFAULT_OFFICIAL_PASSWORD, settings
from ..security import hash_password
from ..storage import Store

logger = logging.getLogger("mrodzina.seed")

# Konta urzędników nadajemy my (brak samorejestracji). Hasło początkowe: OFFICIAL_DEFAULT_PASSWORD.
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
    """Tworzy brakujące konta urzędników; istniejących (i ich haseł) nigdy nie nadpisuje."""
    password = settings.official_default_password
    if settings.is_production and (not password or password == DEFAULT_OFFICIAL_PASSWORD):
        logger.warning(
            "Pomijam konta urzędników: ustaw własne OFFICIAL_DEFAULT_PASSWORD "
            "(domyślne hasło jest dozwolone tylko w trybie ENV=dev)."
        )
        return
    password_hash: str | None = None
    for o in OFFICIALS:
        if await store.get("users", o["id"]) is not None:
            continue
        password_hash = password_hash or hash_password(password)
        doc = {**o, "role": "official", "persona_id": None, "family_id": None}
        await store.put("users", {**doc, "password_hash": password_hash})
