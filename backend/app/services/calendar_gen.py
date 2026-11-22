"""Kalendarz rodziny (plan 09, spec §10): terminy świadczeń, złożone wnioski, oś dziecka i ostrzeżenia.

Czysta funkcja `generate_events`. `id` wpisu = hash(rodzaj + źródło + dziecko), więc zmiana daty porodu
przelicza daty bez duplikowania wpisów, a odkliknięcie (`done`) przeżywa regenerację.
"""

from __future__ import annotations

import calendar as _cal
import hashlib
from datetime import date, timedelta

from typing import Literal

from pydantic import BaseModel, Field

from ..models.application import Application
from ..models.benefit import Benefit
from ..models.calendar import CalendarEvent
from ..models.contract import Risk
from ..models.family import Child, FamilyView
from .milestones import milestones_for
from .situations import event_policy, family_mode

class BenefitWithMatch(BaseModel):
    """Świadczenie + wynik dopasowania dla rodziny (z `BenefitService.list_matches`)."""

    benefit: Benefit
    status: Literal["fits", "maybe", "no"]
    child_ids: list[str] = Field(default_factory=list)


STALE_DAYS = 365  # terminów sprzed ponad roku nie pokazujemy (np. 800+ dla 7-latka)

APP_STATUS_LABEL = {
    "draft": "szkic",
    "needs_input": "brakuje danych",
    "ready": "gotowy do wysłania",
    "sent": "wysłany",
    "received": "otrzymany przez adresata",
    "more_info": "wezwanie do uzupełnienia",
    "accepted": "zaakceptowany",
    "rejected": "odrzucony",
    "cancelled": "anulowany",
}


def event_id(kind: str, source_ref: str, child_id: str | None) -> str:
    return "ev-" + hashlib.sha1(f"{kind}|{source_ref}|{child_id or ''}".encode()).hexdigest()[:16]


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, _cal.monthrange(year, month)[1]))


def _fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _shift(base: date, days: int | None, months: int | None) -> date:
    return add_months(base, months or 0) + timedelta(days=days or 0)


def _benefit_events(family_id: str, bm: BenefitWithMatch, children: list[Child], today: date) -> list[CalendarEvent]:
    b = bm.benefit
    dl = b.deadline
    if dl is None or bm.status == "no":
        return []
    out: list[CalendarEvent] = []
    src = f"benefit:{b.id}"
    form_code = b.form_codes[0] if b.form_codes else None
    maybe = " Może Ci przysługiwać. Sprawdź warunki." if bm.status == "maybe" else ""
    how = f" {b.how_to_apply}" if b.how_to_apply else ""

    if dl.anchor == "fixed":
        if dl.fixed_date:
            out.append(
                CalendarEvent(
                    id=event_id("deadline", src, None), family_id=family_id, kind="deadline",
                    title=f"{b.name}: ostatni dzień na wniosek", summary=(dl.note or "Złóż wniosek przed terminem.") + how + maybe,
                    due_date=dl.fixed_date, source_ref=src, form_code=form_code,
                )
            )
        return out

    concerned_ids = set(bm.child_ids)
    target_children = [ch for ch in children if not b.per_child or ch.id in concerned_ids]
    for ch in target_children:
        if dl.anchor == "due":
            if ch.status != "expected" or not ch.due_date:
                continue
            base = ch.due_date
            when = "przed porodem" if (dl.offset_days or 0) + (dl.offset_months or 0) * 30 < 0 else "po terminie porodu"
            title = f"{b.name}: wniosek ({when}, {ch.name})"
        elif dl.anchor == "birth" and ch.status == "expected" and ch.due_date:
            # dziecko jeszcze w drodze: termin liczony od przewidywanego porodu, więc tylko orientacyjnie
            base = ch.due_date
            title = f"{b.name}: wniosek po porodzie ({ch.name})"
        else:  # birth / child_age — dopiero po urodzeniu
            if ch.status != "born" or not ch.birth_date:
                continue
            base = ch.birth_date
            title = f"{b.name}: wniosek dla {ch.name}"
        due = _shift(base, dl.offset_days, dl.offset_months)
        if due < today - timedelta(days=STALE_DAYS):
            continue
        effect_until = None
        if ch.birth_date and b.criteria.child_age_max_months is not None:
            effect_until = add_months(ch.birth_date, b.criteria.child_age_max_months + 1) - timedelta(days=1)
        summary = (dl.note or f"Złóż wniosek do {_fmt(due)}.") + how + maybe
        if ch.status == "expected" and dl.anchor == "birth":
            summary += f" Termin orientacyjny: liczony od przewidywanego porodu ({_fmt(ch.due_date)}), zmieni się z datą urodzenia."
        if effect_until:
            summary += f" Świadczenie przysługuje do {_fmt(effect_until)}."
        out.append(
            CalendarEvent(
                id=event_id("deadline", src, ch.id), family_id=family_id, kind="deadline", title=title,
                summary=summary, due_date=due, effect_until=effect_until, source_ref=src, child_id=ch.id,
                form_code=form_code,
            )
        )
    return out


def generate_events(
    family_view: FamilyView,
    benefits_with_match: list[BenefitWithMatch],
    applications: list[Application],
    risks: list[Risk],
    today: date,
) -> list[CalendarEvent]:
    fid = family_view.family.id
    names = {u.id: u.name for u in family_view.members}
    children = family_view.children
    events: list[CalendarEvent] = []

    for ch in children:
        if ch.status == "expected" and ch.due_date and ch.situation != "loss":
            src = f"child:{ch.id}"
            events.append(
                CalendarEvent(
                    id=event_id("child", src, ch.id), family_id=fid, kind="child",
                    title=f"Przewidywany termin porodu ({ch.name})",
                    summary="Od tej daty liczymy terminy wniosków. Po porodzie uzupełnij datę urodzenia w „Rodzina”.",
                    due_date=ch.due_date, source_ref=src, child_id=ch.id,
                )
            )

    for m in milestones_for(children, today):
        src = f"milestone:{m.key}"
        events.append(
            CalendarEvent(
                id=event_id("deadline", src, m.child_id), family_id=fid, kind="deadline", title=m.title,
                summary=m.summary, due_date=m.due, source_ref=src, child_id=m.child_id,
            )
        )

    active_children = [c for c in children if c.situation != "loss"]
    for bm in benefits_with_match:
        events.extend(_benefit_events(fid, bm, active_children, today))

    skip_children = {cid for cid, mode in event_policy(children).items() if mode == "skip"}
    for a in applications:
        if a.child_id in skip_children:  # wnioski o dziecko w sytuacji straty nie wracają w kalendarzu
            continue
        src = f"application:{a.id}"
        who = names.get(a.applicant_id, "Rodzic")
        when = (a.sent_at.date() if a.sent_at else a.created_at.date())
        status = APP_STATUS_LABEL.get(a.status, a.status)
        to = a.recipient_email or "portal / urząd"
        date_label = "Złożono" if a.sent_at else "Utworzono"
        if a.status in ("accepted", "rejected", "cancelled"):
            end_note = " Sprawa zakończona; data zakończenia nie jest zapisana."
        elif a.sent_at:
            end_note = " Termin zakończenia nie jest znany."
        else:
            end_note = " To data rozpoczęcia wniosku, nie termin końcowy."
        actor_note = f" Złożył(a): {who}." if a.sent_at else f" Przygotowuje: {who}."
        summary = f"{date_label}: {_fmt(when)}.{end_note}{actor_note} Do: {to}. Status: {status}."
        events.append(
            CalendarEvent(
                id=event_id("application", src, a.child_id), family_id=fid, kind="application",
                title=f"Wniosek {a.form_code}", summary=summary, due_date=when, date_label=date_label, source_ref=src,
                child_id=a.child_id, actor_user_id=a.applicant_id, actor_name=who, recipient=a.recipient_email,
                status=a.status, done=bool(a.sent_at) or a.status in ("accepted", "rejected", "cancelled"),
            )
        )

    for r in risks:
        src = f"risk:{r.id}"
        summary = r.explanation + (f" Co zrobić: {r.action}" if r.action else "")
        events.append(
            CalendarEvent(
                id=event_id("warning", src, None), family_id=fid, kind="warning", title=r.title,
                summary=summary, due_date=r.deadline, source_ref=src, actor_user_id=r.user_id,
                actor_name=names.get(r.user_id), severity=r.severity,
            )
        )

    # tryb jaskółki: wpisy innych dzieci i ostrzeżenia są wyciszone — widoczne, ale bez alarmów o terminie
    policy = event_policy(children)
    jaskolka = family_mode(children) == "jaskolka"
    for e in events:
        e.muted = policy.get(e.child_id or "") == "mute" or (jaskolka and e.kind == "warning")
        e.overdue = bool(e.due_date and e.due_date < today and e.kind in ("deadline", "warning")) and not e.muted
    events.sort(key=lambda e: (e.due_date or date.max, e.kind, e.id))
    return events


def merge_done(generated: list[CalendarEvent], stored: dict[str, dict]) -> list[CalendarEvent]:
    """Zachowuje `done` z bazy (regeneracja przy odczycie nie kasuje odkliknięć)."""
    for e in generated:
        prev = stored.get(e.id)
        if prev is not None and prev.get("done") and not e.done:
            e.done = True
        if e.done:
            e.overdue = False
    return generated
