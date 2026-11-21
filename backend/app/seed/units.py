from ..models.unit import Unit
from ..storage import Store

UNITS = [
    Unit(
        id="unit-krakow",
        name="Gmina Miejska Kraków",
        level="gmina",
        gmina="Kraków",
        powiat="Kraków",
        voivodeship="Małopolskie",
    ),
    Unit(
        id="unit-malopolskie",
        name="Województwo Małopolskie",
        level="voivodeship",
        voivodeship="Małopolskie",
    ),
]


async def seed_units(store: Store) -> None:
    for unit in UNITS:
        await store.put("units", unit.model_dump(mode="json"))
