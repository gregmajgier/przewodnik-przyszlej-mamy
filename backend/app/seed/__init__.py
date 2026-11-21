"""Dane startowe. `seed_all` jest idempotentne (stałe id, `put` = upsert)."""

from ..storage import Store
from . import demo_agent  # noqa: F401  (rejestruje odpowiedź demo planu agenta)
from .benefits import seed_benefits
from . import demo_conditions  # noqa: F401 - odpowiedzi trybu demo (plan 07)
from . import demo_handlers  # noqa: F401 - rejestruje odpowiedzi trybu demo (plan 04)
from . import demo_mail  # noqa: F401 - odpowiedzi trybu demo (plan 09)
from .benefits_local import seed_local_benefits
from .officials import seed_officials
from .units import seed_units


async def seed_all(store: Store) -> None:
    await seed_units(store)
    await seed_officials(store)
    await seed_benefits(store)
    await seed_local_benefits(store)
