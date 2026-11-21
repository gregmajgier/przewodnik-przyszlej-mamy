"""MOCK planu 08 — `app/models/application.py` (model wniosku) + pomocnicza wysyłka.

Prawdziwy plan 08 tworzy wniosek z prefill, podpis, kanały i `POST /api/applications/{id}/submit`.
Tu tylko model wg planu i `mock_submit`, który robi to, czego plan 09 potrzebuje od wysyłki:
mail w folderze `sent` (przez `MailProvider`), `thread_id`, `recipient_*`, `sent_at`, status `sent`.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..storage import Store

ApplicationStatus = Literal[
    "draft", "needs_input", "ready", "sent", "received", "more_info", "accepted", "rejected"
]


class Application(BaseModel):
    id: str
    family_id: str
    applicant_id: str
    form_code: str
    child_id: str | None = None
    channel: Literal["employer_email", "portal_agent", "pdf_download"] = "employer_email"
    status: ApplicationStatus = "draft"
    values: dict[str, Any] = Field(default_factory=dict)
    missing: list[Any] = Field(default_factory=list)
    recipient_email: str | None = None
    recipient_domain: str | None = None
    thread_id: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


async def list_family_applications(store: Store, family_id: str) -> list[Application]:
    apps = [Application.model_validate(d) for d in await store.find("applications", family_id=family_id)]
    apps.sort(key=lambda a: (a.created_at, a.id))
    return apps


async def mock_submit(store: Store, mail, app: Application, *, subject: str, body: str, now: datetime | None = None) -> Application:
    """Zastępuje `submit` z planu 08: wysyła mail przez `MailProvider` i zapisuje wątek. Idempotentne."""
    if app.status != "draft" and app.thread_id:
        return app
    now = now or datetime.now(timezone.utc)
    sent = await mail.send(app.family_id, app.applicant_id, app.recipient_email, subject, body, [])
    app.thread_id = sent.thread_id
    app.sent_at = now
    app.status = "sent"
    if app.recipient_email and not app.recipient_domain:
        app.recipient_domain = app.recipient_email.rsplit("@", 1)[-1].lower()
    await store.put("applications", app.model_dump(mode="json"))
    return app
