from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Address(BaseModel):
    city: str
    gmina: str
    powiat: str
    voivodeship: str
    postal_code: str


class Insurance(BaseModel):
    kind: Literal["employment", "mandate", "jdg"]
    payer: str
    contribution_base: float
    voluntary_sickness: bool | None = None
    since: date
    # Ilu ubezpieczonych płatnik zgłasza do ubezpieczenia chorobowego (dane ZUS, stan na 30 listopada poprzedniego roku).
    # Powyżej progu `platnik.prog_ubezpieczonych` (20) zasiłki wypłaca płatnik, inaczej ZUS; None = nie wiemy.
    payer_insured_count: int | None = Field(default=None, ge=0)


class Ezla(BaseModel):
    code: str
    from_date: date
    to_date: date


class Debt(BaseModel):
    amount: float
    since: date


class KnownChild(BaseModel):
    name: str
    birth_date: date | None = None
    due_date: date | None = None


class ParentProfile(BaseModel):
    """Profil „Moje dane” jednego rodzica; `id` = `user_id` (klucz w kolekcji `profiles`)."""

    user_id: str
    first_name: str
    last_name: str
    pesel: str
    birth_date: date
    address: Address
    insurance: list[Insurance] = Field(default_factory=list)
    ezla: list[Ezla] = Field(default_factory=list)
    contribution_debt: Debt | None = None
    known_children: list[KnownChild] = Field(default_factory=list)
    answers: dict[str, bool | str] = Field(default_factory=dict)


class MemberProfile(ParentProfile):
    user_name: str
