"""Pokrycie jednostek samorządu: czy jednostka obejmuje dany adres."""

from ..models.profile import Address


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def covers(unit: dict, address: Address) -> bool:
    """Gmina: ta sama gmina (i województwo); powiat: ten sam powiat; województwo: całe; kraj: każdy."""
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
        if _norm(unit.get("gmina")) != _norm(address.gmina):
            return False
        return not unit.get("powiat") or _norm(unit["powiat"]) == _norm(address.powiat)
    return False


def units_for(address: Address, units: list[dict]) -> list[str]:
    return [u["id"] for u in units if covers(u, address)]
