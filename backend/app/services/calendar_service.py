"""Kalendarz rodziny z bazy (plan 09): zbiera dane, generuje wpisy, zachowuje `done` i zapisuje wynik."""

from __future__ import annotations

from datetime import date

from ..errors import DomainError
from ..mocks.application import list_family_applications  # MOCK planu 08 — patrz NOTES-MOCKS.md
from ..mocks.benefit_catalog import BenefitWithMatch, naive_match, visible_benefits  # MOCK planu 03
from ..models.calendar import CalendarEvent
from ..models.profile import ParentProfile
from ..storage import Store
from .calendar_gen import generate_events, merge_done
from .contracts import family_risks
from .families import FamilyService

NO_FAMILY = "Najpierw załóż rodzinę albo dołącz do niej — kalendarz jest wspólny dla rodziny."


async def family_calendar(store: Store, user_id: str, today: date) -> list[CalendarEvent]:
    try:
        view = await FamilyService(store).get_family_view(user_id)
    except DomainError as e:
        if e.status_code == 404:
            raise DomainError(404, NO_FAMILY) from None
        raise
    fid = view.family.id
    profile_doc = await store.get("profiles", user_id) or await store.get("profiles", view.family.owner_id)
    benefits: list[BenefitWithMatch] = []
    if profile_doc is not None:
        address = ParentProfile.model_validate({**profile_doc, "user_id": user_id}).address
        for b in await visible_benefits(store, address):
            benefits.append(BenefitWithMatch(benefit=b, status=naive_match(b, view.children, today)))
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
