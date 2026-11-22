from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Criteria(BaseModel):
    """Kryteria strukturalne sprawdzane kodem.

    Wiek dziecka liczony w pełnych ukończonych miesiącach; obie granice włącznie.
    Np. „do ukończenia 18 lat” = `child_age_max_months=215` (w dniu 18. urodzin wiek to już 216 → nie pasuje).
    """

    child_age_min_months: int | None = None
    child_age_max_months: int | None = None
    max_income_per_person: float | None = None
    min_children: int | None = None
    requires_pregnancy: bool | None = None
    # „w ciąży albo dziecko do N miesięcy włącznie” (np. zasiłek macierzyński: przed i po porodzie)
    pregnant_or_child_max_months: int | None = None
    # „w ciąży albo dziecko do końca roku kalendarzowego, w którym kończy N lat” (urlop rodzicielski: N = 6)
    pregnant_or_child_until_year_end_of_age: int | None = None
    # „w ciąży albo trwa urlop macierzyński” (20–37 tygodni od porodu, zależnie od liczby dzieci z jednego porodu)
    pregnant_or_in_maternity_leave: bool | None = None
    requires_disability: bool | None = None
    requires_foster: bool | None = None
    employment_kinds: list[Literal["employment", "mandate", "jdg"]] | None = None


class Condition(BaseModel):
    """Dodatkowy warunek. `auto` — sprawdzany po `profile_key`; `ask` — pytanie tak/nie do rodzica."""

    id: str
    text: str
    kind: Literal["auto", "ask"]
    question: str | None = None
    profile_key: str | None = None
    # Pytanie zadane twierdząco o coś, czego warunek wymaga braku („Czy przysługuje ci zasiłek…?”):
    # odpowiedź „tak” oznacza, że warunek NIE jest spełniony. Nie dotyczy faktów `auto` z profilu.
    negated_question: bool = False
    # Własny komunikat, gdy warunek nie jest spełniony (domyślnie „Warunek niespełniony: <text>.”).
    unmet_text: str | None = None


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
    category: Literal["benefit", "perk"]
    description: str
    amount_text: str | None = None
    annual_value_estimate: int | None = None
    deadline: Deadline | None = None
    how_to_apply: str
    form_codes: list[str] = Field(default_factory=list)
    source_url: str
    criteria: Criteria = Field(default_factory=Criteria)
    extra_conditions: list[Condition] = Field(default_factory=list)
    extra_text: str | None = None
    # `awaiting_approval`: urzędnik zatwierdził warunki, ale jeszcze nie opublikował (plan 07)
    status: Literal["draft", "awaiting_approval", "published"] = "published"
    verify: bool = False
    tags: list[str] = Field(default_factory=list)
    # Świadczenie „na dziecko”: silnik wskazuje, których dzieci dotyczy (`MatchResult.child_ids`),
    # a szacunek roczny liczy się osobno dla każdego z nich.
    per_child: bool = False
    # pola edytora urzędnika (plan 07)
    deadline_text: str | None = None
    apply_url: str | None = None
