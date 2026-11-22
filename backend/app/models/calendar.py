from datetime import date
from typing import Literal

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    """Wpis kalendarza rodziny. Generowany (stałe `id` z rodzaju, źródła i dziecka); `done` przechowywane."""

    id: str
    family_id: str
    kind: Literal["deadline", "application", "child", "warning"]
    title: str
    summary: str
    due_date: date | None = None
    # For application events this labels the start/submission date, not a deadline.
    date_label: Literal["Utworzono", "Złożono"] | None = None
    effect_until: date | None = None
    done: bool = False
    overdue: bool = False
    source_ref: str
    child_id: str | None = None
    actor_user_id: str | None = None
    actor_name: str | None = None
    recipient: str | None = None
    status: str | None = None
    severity: Literal["info", "medium", "high"] | None = None
    # termin ze świadczenia: kod wniosku do złożenia (frontend prowadzi z kalendarza prosto do kreatora)
    form_code: str | None = None
    # tryb jaskółki: terminy innych dzieci są wyciszone (pokazywane spokojnie, bez przypominania)
    muted: bool = False
