import logging

from ..config import DEFAULT_OFFICIAL_PASSWORD, MIN_OFFICIAL_PASSWORD_LENGTH, settings
from ..security import hash_password, verify_password
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


async def _disable_default_password_accounts(store: Store) -> None:
    """Poza trybem dev wyłącza konta, które nadal mają publicznie znane hasło domyślne."""
    for o in OFFICIALS:
        doc = await store.get("users", o["id"])
        if doc is None or doc.get("disabled"):
            continue
        if verify_password(DEFAULT_OFFICIAL_PASSWORD, doc.get("password_hash")):
            await store.put("users", {**doc, "disabled": True})
            logger.warning(
                "Wyłączono konto urzędnika %s: miało domyślne hasło. "
                "Ustaw nowe hasło i zdejmij flagę `disabled`.",
                o["id"],
            )


async def seed_officials(store: Store) -> None:
    """Tworzy brakujące konta urzędników; istniejących (i ich haseł) nigdy nie nadpisuje."""
    password = settings.official_default_password
    if settings.is_production:
        await _disable_default_password_accounts(store)
        if (
            not password
            or password == DEFAULT_OFFICIAL_PASSWORD
            or len(password) < MIN_OFFICIAL_PASSWORD_LENGTH
        ):
            logger.warning(
                "Pomijam konta urzędników: ustaw własne OFFICIAL_DEFAULT_PASSWORD "
                "(min. %d znaków, inne niż domyślne; domyślne jest dozwolone tylko w ENV=dev).",
                MIN_OFFICIAL_PASSWORD_LENGTH,
            )
            return
    password_hash: str | None = None
    for o in OFFICIALS:
        if await store.get("users", o["id"]) is not None:
            continue
        password_hash = password_hash or hash_password(password)
        doc = {**o, "role": "official", "persona_id": None, "family_id": None}
        await store.put("users", {**doc, "password_hash": password_hash})
