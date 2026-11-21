"""Dane startowe. `seed_all` jest idempotentne (stałe id, `put` = upsert)."""

from ..storage import Store


async def seed_all(store: Store) -> None:
    pass
