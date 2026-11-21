"""MOCK planu 08 (tylko demo planu 09): „złóż” przykładowy wniosek bez kreatora wniosków.

Do usunięcia po scaleniu planu 08 — patrz docs/superpowers/plans/NOTES-MOCKS.md. Niedostępne poza ENV=dev.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..config import settings
from ..errors import DomainError
from ..mail.sim_inbox import SimInbox, schedule_reply
from ..mocks.application import Application, list_family_applications, mock_submit
from ..security import Principal, require_parent
from ..storage import Store, get_store

router = APIRouter(prefix="/api/mock/applications", tags=["mock"])

# kod formularza -> (adres odbiorcy, kanał); pracodawca: adres z zatwierdzonej umowy, jeśli jest
DEFAULT_RECIPIENTS = {
    "ZAM": ("wnioski@zus.pl", "portal_agent"),
    "BECIKOWE": ("swiadczenia@um.krakow.pl", "pdf_download"),
}
EMPLOYER_FALLBACK = "kadry@kcuw.example.pl"


class MockSubmitIn(BaseModel):
    form_code: str = Field(default="URLOP-MAC-ROD", pattern=r"^[A-Z0-9\-]{2,30}$")
    recipient_email: str | None = Field(default=None, max_length=200)


def _dev_only() -> None:
    if settings.is_production:
        raise DomainError(404, "Nie znaleziono.")


async def _employer_email(store: Store, user_id: str) -> str:
    for c in await store.find("contracts", user_id=user_id, confirmed=True):
        if c.get("employer_email"):
            return c["employer_email"]
    return EMPLOYER_FALLBACK


@router.get("")
async def list_apps(p: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> list[Application]:
    _dev_only()
    return await list_family_applications(store, p.family_id) if p.family_id else []


@router.post("", status_code=201)
async def submit(
    request: Request,
    body: MockSubmitIn,
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> Application:
    _dev_only()
    if not p.family_id:
        raise DomainError(404, "Najpierw załóż rodzinę.")
    to, channel = DEFAULT_RECIPIENTS.get(body.form_code, (None, "employer_email"))
    to = body.recipient_email or to or await _employer_email(store, p.user_id)
    now = datetime.now(timezone.utc)
    app = Application(
        id=f"app-{uuid.uuid4().hex[:12]}", family_id=p.family_id, applicant_id=p.user_id,
        form_code=body.form_code, channel=channel, status="draft", recipient_email=to,
        recipient_domain=to.rsplit("@", 1)[-1].lower(), created_at=now,
    )
    inbox = SimInbox(request.app.state.store)
    app = await mock_submit(
        store, inbox, app, subject=f"Wniosek {body.form_code}",
        body="Dzień dobry, w załączeniu przesyłam wniosek. (symulacja)", now=now,
    )
    await schedule_reply(store, app, now)
    return app
