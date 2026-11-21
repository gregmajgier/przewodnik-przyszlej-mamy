from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .user import User


class Family(BaseModel):
    id: str
    name: str
    owner_id: str
    member_ids: list[str]
    invite_code: str | None = None
    invite_expires_at: datetime | None = None


class JoinRequest(BaseModel):
    id: str
    family_id: str
    user_id: str
    status: Literal["pending", "accepted", "rejected"] = "pending"


class JoinRequestView(JoinRequest):
    user_name: str


class _ChildFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    birth_date: date | None = None
    due_date: date | None = None
    status: Literal["expected", "born"] | None = None
    pesel: str | None = None
    has_disability: bool = False
    foster: bool = False
    situation: Literal["loss"] | None = None
    situation_kind: Literal["poronienie", "martwe-urodzenie", "smierc-dziecka"] | None = None
    situation_at: datetime | None = None
    # Rodzic wyszedł z trybu jaskółki („Wróć do zwykłego widoku”); dziecko zachowuje `situation` (świadczenia
    # i przypomnienia o nim pozostają ukryte), ale rodzina nie jest już w trybie. Ustawia tylko plan 10.
    situation_exited_at: datetime | None = None
    serious_illness: bool = False

    @model_validator(mode="after")
    def _dates_and_status(self):
        if self.birth_date is None and self.due_date is None:
            raise ValueError("Podaj datę urodzenia albo przewidywany termin porodu")
        if self.status is None:
            self.status = "born" if self.birth_date else "expected"
        return self


class ChildIn(_ChildFields):
    """Dane dziecka przyjmowane z API."""


class Child(_ChildFields):
    id: str
    family_id: str


class ChildPatch(BaseModel):
    """Częściowa zmiana; pola nieprzesłane pozostają bez zmian."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_date: date | None = None
    due_date: date | None = None
    status: Literal["expected", "born"] | None = None
    pesel: str | None = None
    has_disability: bool | None = None
    foster: bool | None = None
    # `situation*` zmienia się tylko przez serwis sytuacji (plan 10: efekty uboczne, okno cofnięcia).
    serious_illness: bool | None = None


class FamilyView(BaseModel):
    family: Family
    members: list[User]
    children: list[Child]
    pending_requests: list[JoinRequestView] = []


class CreateFamilyIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)


class JoinIn(BaseModel):
    code: str
