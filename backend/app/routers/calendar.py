"""Kalendarz rodziny (plan 09): terminy, wnioski (kto złożył), oś dziecka i ostrzeżenia."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..models.calendar import CalendarEvent
from ..security import Principal, require_parent
from ..services.calendar_service import family_calendar, set_done
from ..storage import Store, get_store

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class DoneIn(BaseModel):
    done: bool


@router.get("")
async def list_events(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> list[CalendarEvent]:
    events = await family_calendar(store, p.user_id, date.today())
    return [
        e
        for e in events
        if e.due_date is None
        or ((from_ is None or e.due_date >= from_) and (to is None or e.due_date <= to))
    ]


@router.patch("/{event_id}")
async def patch_event(
    event_id: str, body: DoneIn, p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> CalendarEvent:
    return await set_done(store, p.user_id, p.family_id, event_id, body.done)
