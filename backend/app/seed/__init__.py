"""Dane startowe. `seed_all` jest idempotentne (stałe id, `put` = upsert)."""

from ..storage import Store
from .benefits import seed_benefits
from .officials import seed_officials
from .units import seed_units


async def seed_all(store: Store) -> None:
    await seed_units(store)
    await seed_officials(store)
    await seed_benefits(store)
