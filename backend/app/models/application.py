"""Wniosek składany przez rodzica (kolekcja `applications`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["employer_email", "portal_agent", "pdf_download"]
Status = Literal[
    "draft",  # dane kompletne, czeka na zatwierdzenie
    "needs_input",  # brakuje danych — rodzic odpowiada na pytania
    "ready",  # kompletny i podpisany (kanały PDF) — można wysłać
    "sent",
    "received",
    "more_info",
    "accepted",
    "rejected",
    "cancelled",  # np. dziecko w trybie straty
]

# Statusy, po których wniosek jest już „zamknięty” dla edycji i wysyłki.
FINAL_STATUSES: frozenset[str] = frozenset(
    {"sent", "received", "more_info", "accepted", "rejected", "cancelled"}
)


class MissingField(BaseModel):
    field_id: str
    label: str
    type: Literal["text", "date", "bool", "choice"] = "text"
    choices: list[str] | None = None


class Application(BaseModel):
    id: str
    family_id: str
    applicant_id: str
    form_code: str
    child_id: str | None = None
    channel: Channel
    status: Status = "draft"
    values: dict[str, Any] = Field(default_factory=dict)
    missing: list[MissingField] = Field(default_factory=list)
    # odpowiedzi rodzica dla tego wniosku (pierwszeństwo przed danymi z profilu)
    answers: dict[str, Any] = Field(default_factory=dict)
    recipient_email: str | None = None
    recipient_domain: str | None = None
    thread_id: str | None = None
    signed_at: datetime | None = None
    signed_digest: str | None = None  # odcisk danych w chwili podpisu (zmiana danych unieważnia podpis)
    sent_at: datetime | None = None
    created_at: datetime


class ApplicationCreate(BaseModel):
    form_code: str
    child_id: str | None = None
    channel: Channel | None = None


class ApplicationPatch(BaseModel):
    """Edycja pól w podglądzie (tylko dla tego wniosku) i/lub zmiana kanału."""

    values: dict[str, Any] | None = None
    channel: Channel | None = None


class AnswersIn(BaseModel):
    answers: dict[str, Any]
