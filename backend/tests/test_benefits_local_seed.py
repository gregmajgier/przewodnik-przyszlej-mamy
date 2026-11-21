import asyncio

from app.mocks.benefit_catalog import visible_benefits  # MOCK planu 03
from app.models.profile import Address
from app.seed import seed_all
from app.seed.benefits_local import load_local_samples
from app.services.conditions import PROFILE_KEYS


def test_samples_valid_and_marked():
    items = load_local_samples()
    assert 3 <= len(items) <= 4
    assert len({b.id for b in items}) == len(items)
    for b in items:
        assert b.name.endswith("(przykład)")
        assert b.status == "published" and b.verify is True
        assert b.source_url.startswith("https://")
        assert b.unit_id in ("unit-krakow", "unit-malopolskie")
        for c in b.extra_conditions:
            assert c.kind == "ask" or c.profile_key in PROFILE_KEYS
        assert not b.extra_text or b.conditions_approved


def test_seed_loads_and_is_idempotent(store):
    docs = asyncio.run(store.find("benefits"))
    assert len(docs) == len(load_local_samples())
    edited = {**docs[0], "name": "Zmienione przez urzędnika"}
    asyncio.run(store.put("benefits", edited))
    asyncio.run(seed_all(store))
    assert asyncio.run(store.get("benefits", edited["id"]))["name"] == "Zmienione przez urzędnika"


def test_samples_visible_in_krakow(store):
    addr = Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001")
    ids = {b.id for b in asyncio.run(visible_benefits(store, addr))}
    assert {b.id for b in load_local_samples()} <= ids
