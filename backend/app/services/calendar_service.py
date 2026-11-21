"""Kalendarz rodziny z bazy (plan 09): zbiera dane, generuje wpisy, zachowuje `done` i zapisuje wynik."""

from __future__ import annotations

from datetime import date

from ..errors import DomainError
from ..models.calendar import CalendarEvent
from ..storage import Store
from .applications import list_family_applications
from .benefit_service import BenefitService
from .calendar_gen import BenefitWithMatch, generate_events, merge_done
from .contracts import family_risks
from .families import FamilyService

NO_FAMILY = "Najpierw załóż rodzinę albo dołącz do niej, bo kalendarz jest wspólny dla rodziny."


async def family_calendar(store: Store, user_id: str, today: date) -> list[CalendarEvent]:
    try:
        view = await FamilyService(store).get_family_view(user_id)
    except DomainError as e:
        if e.status_code == 404:
            raise DomainError(404, NO_FAMILY) from None
        raise
    fid = view.family.id
    matches = await BenefitService(store).list_matches(user_id, today)
    benefits = [BenefitWithMatch(benefit=m.benefit, status=m.match.status) for m in matches]
    applications = await list_family_applications(store, fid)
    risks = await family_risks(store, user_id, fid, today)

    events = generate_events(view, benefits, applications, risks, today)
    stored = {d["id"]: d for d in await store.find("calendar_events", family_id=fid)}
    events = merge_done(events, stored)
    new_ids = {e.id for e in events}
    for e in events:
        doc = e.model_dump(mode="json")
        if stored.get(e.id) != doc:
            await store.put("calendar_events", doc)
    for old_id in stored.keys() - new_ids:
        await store.delete("calendar_events", old_id)
    return events


async def set_done(store: Store, user_id: str, family_id: str | None, event_id: str, done: bool) -> CalendarEvent:
    doc = await store.get("calendar_events", event_id)
    if doc is None or not family_id or doc.get("family_id") != family_id:
        raise DomainError(404, "Nie znaleziono takiego wpisu w kalendarzu.")
    event = CalendarEvent.model_validate({**doc, "done": done})
    if done:
        event.overdue = False
    await store.put("calendar_events", event.model_dump(mode="json"))
    return event
