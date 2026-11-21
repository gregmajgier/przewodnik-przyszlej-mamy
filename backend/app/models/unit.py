from typing import Literal

from pydantic import BaseModel


class Unit(BaseModel):
    """Jednostka samorządu: gmina, powiat lub województwo."""

    id: str
    name: str
    level: Literal["gmina", "powiat", "voivodeship"]
    gmina: str | None = None
    powiat: str | None = None
    voivodeship: str
