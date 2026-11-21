"""Modele umów (plan 04): wynik ekstrakcji (`ContractDraft`), zapisana umowa (`Contract`) i ostrzeżenie (`Risk`)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ContractKind = Literal["employment", "mandate", "jdg"]

MAX_TEXT = 300


class ContractDraft(BaseModel):
    """Dane wyciągnięte z umowy. Każde pole może być `None` — wtedy rodzic uzupełnia je w formularzu."""

    kind: ContractKind | None = None
    employer_name: str | None = None
    employer_address: str | None = None
    employer_email: str | None = None
    position: str | None = None
    fte: float | None = None  # wymiar etatu 0–1
    gross_monthly: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    indefinite: bool | None = None
    voluntary_sickness: bool | None = None
    missing: list[str] = Field(default_factory=list)

    @field_validator("employer_name", "employer_address", "employer_email", "position", mode="before")
    @classmethod
    def _clean_text(cls, v):
        """Przycina białe znaki i długość; pusty tekst = brak wartości (model często zwraca „”)."""
        if v is None:
            return None
        if not isinstance(v, str):
            v = str(v)
        v = " ".join(v.split())[:MAX_TEXT]
        return v or None

    @field_validator("fte", mode="after")
    @classmethod
    def _fte_range(cls, v):
        # wartość spoza 0–1 to prawie na pewno błąd odczytu — traktujemy jak brak (rodzic poprawi)
        return v if v is not None and 0 < v <= 1 else None

    @field_validator("gross_monthly", mode="after")
    @classmethod
    def _gross_range(cls, v):
        return v if v is not None and 0 < v < 10_000_000 else None


class Contract(ContractDraft):
    id: str
    user_id: str
    family_id: str
    filename: str | None = None  # widoczna tylko dla właściciela; samego pliku nie przechowujemy
    confirmed: bool = False
    created_at: datetime


class Risk(BaseModel):
    id: str
    severity: Literal["info", "medium", "high"]
    title: str
    explanation: str
    action: str | None = None
    deadline: date | None = None
    user_id: str
    source_ref: str
