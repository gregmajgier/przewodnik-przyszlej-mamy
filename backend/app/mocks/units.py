"""MOCK planu 03 — `app/services/units.py` (`covers`, `units_for`)."""

from ..models.profile import Address


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def covers(unit: dict, address: Address) -> bool:
    """Gmina: ta sama gmina; powiat: ten sam powiat; województwo: całe; brak jednostki/kraj: każdy."""
    level = unit.get("level")
    if level in ("national", None):
        return True
    if _norm(unit.get("voivodeship")) != _norm(address.voivodeship):
        return False
    if level == "voivodeship":
        return True
    if level == "powiat":
        return _norm(unit.get("powiat")) == _norm(address.powiat)
    if level == "gmina":
        return _norm(unit.get("gmina")) == _norm(address.gmina)
    return False


def units_for(address: Address, units: list[dict]) -> list[str]:
    return [u["id"] for u in units if covers(u, address)]
