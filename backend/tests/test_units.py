from app.models.profile import Address
from app.services.units import covers, units_for

KRAKOW = Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001")
WIELICZKA = Address(
    city="Wieliczka", gmina="Wieliczka", powiat="wielicki", voivodeship="Małopolskie", postal_code="32-020"
)
KATOWICE = Address(city="Katowice", gmina="Katowice", powiat="Katowice", voivodeship="Śląskie", postal_code="40-001")

U_KRAKOW = {"id": "unit-krakow", "level": "gmina", "gmina": "Kraków", "powiat": "Kraków", "voivodeship": "Małopolskie"}
U_POWIAT = {"id": "unit-wielicki", "level": "powiat", "gmina": None, "powiat": "wielicki", "voivodeship": "Małopolskie"}
U_MALOPOLSKIE = {"id": "unit-malopolskie", "level": "voivodeship", "voivodeship": "Małopolskie"}


def test_gmina_covers_only_own_gmina():
    assert covers(U_KRAKOW, KRAKOW)
    assert not covers(U_KRAKOW, WIELICZKA)
    assert not covers(U_KRAKOW, KATOWICE)


def test_gmina_name_must_match_voivodeship_too():
    same_name_elsewhere = Address(
        city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Śląskie", postal_code="40-001"
    )
    assert not covers(U_KRAKOW, same_name_elsewhere)


def test_matching_ignores_case_and_whitespace():
    addr = Address(city="kraków", gmina=" kraków ", powiat="KRAKÓW", voivodeship="małopolskie", postal_code="30-001")
    assert covers(U_KRAKOW, addr)


def test_powiat_covers_its_gminas():
    assert covers(U_POWIAT, WIELICZKA)
    assert not covers(U_POWIAT, KRAKOW)


def test_voivodeship_covers_all_gminas_in_it():
    assert covers(U_MALOPOLSKIE, KRAKOW)
    assert covers(U_MALOPOLSKIE, WIELICZKA)
    assert not covers(U_MALOPOLSKIE, KATOWICE)


def test_national_covers_everyone():
    national = {"id": "x", "level": "national"}
    assert covers(national, KRAKOW)
    assert covers(national, KATOWICE)


def test_units_for_returns_ids_of_covering_units():
    units = [U_KRAKOW, U_POWIAT, U_MALOPOLSKIE]
    assert units_for(KRAKOW, units) == ["unit-krakow", "unit-malopolskie"]
    assert units_for(KATOWICE, units) == []
