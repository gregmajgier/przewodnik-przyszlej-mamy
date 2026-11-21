"""MOCK planu 03 — `app/models/benefit.py` (Criteria, Condition, Deadline, Benefit).

Różnica względem planu 03 (wymagana przez plan 07): `Benefit.status` ma dodatkowo `awaiting_approval`,
a `deadline_text`/`apply_url` są opcjonalnymi polami edytora urzędnika. Przy scalaniu dopisać je do
prawdziwego modelu.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

EmploymentKind = Literal["employment", "mandate", "jdg"]


class Criteria(BaseModel):
    """Kryteria strukturalne. Wiek w pełnych miesiącach, obie granice włącznie."""

    child_age_min_months: int | None = None
    child_age_max_months: int | None = None
    max_income_per_person: float | None = None
    min_children: int | None = None
    requires_pregnancy: bool | None = None
    requires_disability: bool | None = None
    requires_foster: bool | None = None
    employment_kinds: list[EmploymentKind] | None = None


class Condition(BaseModel):
    """`auto` — sprawdzany po `profile_key`; `ask` — pytanie tak/nie do rodzica."""

    id: str
    text: str
    kind: Literal["auto", "ask"]
    question: str | None = None
    profile_key: str | None = None


class Deadline(BaseModel):
    anchor: Literal["birth", "due", "child_age", "fixed"]
    offset_days: int | None = None
    offset_months: int | None = None
    fixed_date: date | None = None
    note: str | None = None


class Benefit(BaseModel):
    id: str
    name: str
    scope: Literal["national", "regional", "municipal"]
    unit_id: str | None = None
    category: Literal["benefit", "perk"] = "benefit"
    description: str
    amount_text: str | None = None
    annual_value_estimate: int | None = None
    deadline: Deadline | None = None
    how_to_apply: str = ""
    form_codes: list[str] = Field(default_factory=list)
    source_url: str = ""
    criteria: Criteria = Field(default_factory=Criteria)
    extra_conditions: list[Condition] = Field(default_factory=list)
    extra_text: str | None = None
    status: Literal["draft", "awaiting_approval", "published"] = "published"
    verify: bool = False
    tags: list[str] = Field(default_factory=list)
    # pola edytora urzędnika (plan 07)
    deadline_text: str | None = None
    apply_url: str | None = None
