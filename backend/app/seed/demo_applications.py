"""Przykładowe wnioski „w toku” dla rodziny demo: widać od razu cały cykl — PDF do pracodawcy z odpowiedzią
kadr, decyzję ZUS i szkic formularza online, który wypełni agent.

Wnioski powstają przez prawdziwy `ApplicationService` (prefill, PDF, wysyłka e-mailem), a potem dostają wcześniejsze
daty i odpowiedzi w skrzynce. Jedna odpowiedź („zatwierdzony”) czeka w kolejce poczty i przychodzi kilkadziesiąt
sekund po pierwszym wejściu — synchronizacja Gmaila sama zmienia wtedy status wniosku.

Wkładane leniwie przy pierwszym pobraniu listy wniosków, tylko gdy rodzina ma dzieci i nie ma jeszcze żadnych
wniosków. Wyłączane `DEMO_APPLICATIONS=0` (testy).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..errors import DomainError
from ..mail import MailProvider
from ..mail.sim_inbox import PENDING, _mid
from ..models.application import Application, ApplicationCreate
from ..models.mail import MailMessage
from ..services import prefill as pf
from ..services.applications import ApplicationService
from ..storage import Store

logger = logging.getLogger("mrodzina.demo")

MARKERS = "demo_seeds"
LIVE_REPLY_DELAY_S = 75

_TEXT_DEFAULTS = {
    "employer_email": "kadry@kcuw.pl",
    "street": "Floriańska",
    "house_no": "12",
    "flat_no": "4",
    "bank_account": "12102028920000540201234567",
    "account_number": "12102028920000540201234567",
    "phone": "600 100 200",
}


def _pesel(born: date, serial: int = 4021) -> str:
    """Poprawny (sumą kontrolną) PESEL dla daty urodzenia — dane przykładowe."""
    month = born.month + (20 if born.year >= 2000 else 0)
    digits = f"{born.year % 100:02d}{month:02d}{born.day:02d}{serial:04d}"
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    check = (10 - sum(int(d) * w for d, w in zip(digits, weights)) % 10) % 10
    return f"{digits}{check}"


def _defaults(app: Application, child_birth: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for q in app.missing:
        if q.field_id.endswith("pesel") and child_birth:
            out[q.field_id] = _pesel(date.fromisoformat(child_birth))
        elif q.type == "bool":
            out[q.field_id] = True
        elif q.type == "date":
            out[q.field_id] = date.today().isoformat()
        elif q.type == "choice" and q.choices:
            out[q.field_id] = q.choices[0]
        else:
            out[q.field_id] = _TEXT_DEFAULTS.get(q.field_id, "nie dotyczy")
    return out


async def _fill(svc: ApplicationService, user_id: str, app: Application, child_birth: str | None = None) -> Application:
    for _ in range(4):  # odpowiedzi mogą odsłonić kolejne pytania
        if not app.missing:
            break
        app = await svc.answer(user_id, app.id, _defaults(app, child_birth))
    return app


async def _put_app(store: Store, app: Application) -> None:
    await store.put("applications", app.model_dump(mode="json"))


async def _employer_leave(store: Store, svc: ApplicationService, user_id: str, child_id: str, now: datetime) -> None:
    app = await svc.create(user_id, ApplicationCreate(form_code="URLOP-MAC-ROD", child_id=child_id, channel="employer_email"))
    app = await _fill(svc, user_id, app)
    app = await svc.sign(user_id, app.id)
    app = await svc.submit(user_id, app.id)
    sent_at = now - timedelta(days=3, hours=2)
    # wysłany e-mail z PDF — z datą sprzed trzech dni
    for m in await store.find("mail_messages", family_id=app.family_id, folder="sent"):
        if m.get("thread_id") == app.thread_id:
            await store.put("mail_messages", {**m, "received_at": sent_at.isoformat()})
    # odpowiedź kadr: ten sam identyfikator, co pierwsza odpowiedź z szablonu — kolejka poczty jej nie zdubluje
    reply = MailMessage(
        id=f"mail-reply-{_mid(app.id, '0')}",
        family_id=app.family_id,
        folder="inbox",
        from_addr=app.recipient_email or "kadry@kcuw.pl",
        to_addr="",
        subject=f"Re: Wniosek {app.form_code}",
        body="Dzień dobry,\npotwierdzamy otrzymanie wniosku. Dział kadr rozpatrzy go w ciągu 7 dni.\nPozdrawiamy, Dział Kadr",
        thread_id=app.thread_id,
        message_id=f"<{_mid(app.id, '0')}@sim.reply>",
        received_at=now - timedelta(days=2, hours=5),
        related_application_id=app.id,
        classified=True,
        classification_status="received",
        classification_confidence=0.94,
        classification_summary="Kadry potwierdziły otrzymanie wniosku i rozpatrzą go w ciągu 7 dni.",
    )
    await store.put("mail_messages", reply.model_dump(mode="json"))
    app.status, app.sent_at = "received", sent_at
    app.created_at = sent_at - timedelta(minutes=12)
    await _put_app(store, app)
    # druga odpowiedź („zatwierdzony”) przyjdzie na żywo
    await store.put(
        PENDING,
        {
            "id": app.id,
            "family_id": app.family_id,
            "due_at": (now + timedelta(seconds=LIVE_REPLY_DELAY_S)).isoformat(),
            "delivered": False,
        },
    )


async def _zus_800plus(store: Store, svc: ApplicationService, user_id: str, child_id: str, now: datetime) -> None:
    app = await svc.create(user_id, ApplicationCreate(form_code="800PLUS", child_id=child_id, channel="portal_agent"))
    child = await store.get("children", child_id)
    app = await _fill(svc, user_id, app, (child or {}).get("birth_date"))
    app = await svc.portal_submitted(user_id, app.id)
    await store.delete(PENDING, app.id)
    sent_at = now - timedelta(days=12, hours=3)
    decision = MailMessage(
        id=f"mail-demo-{app.id}",
        family_id=app.family_id,
        folder="inbox",
        from_addr="powiadomienia@zus.pl",
        to_addr="",
        subject="Informacja o przyznaniu świadczenia wychowawczego",
        body=(
            "Szanowna Pani,\nuprzejmie informujemy, że przyznaliśmy świadczenie wychowawcze w wysokości 800 zł "
            "miesięcznie. Pierwsza wypłata nastąpi na wskazany rachunek bankowy.\nZakład Ubezpieczeń Społecznych"
        ),
        message_id=f"<demo-{app.id}@zus.pl>",
        received_at=now - timedelta(days=5, hours=1),
        related_application_id=app.id,
        classified=True,
        classification_status="accepted",
        classification_confidence=0.97,
        classification_summary="ZUS przyznał 800+ — 800 zł miesięcznie na wskazane konto.",
    )
    await store.put("mail_messages", decision.model_dump(mode="json"))
    app.status, app.sent_at = "accepted", sent_at
    app.created_at = sent_at - timedelta(minutes=8)
    await _put_app(store, app)


async def _zam_draft(store: Store, svc: ApplicationService, user_id: str, child_id: str, now: datetime) -> None:
    app = await svc.create(user_id, ApplicationCreate(form_code="ZAM", child_id=child_id, channel="portal_agent"))
    app.created_at = now - timedelta(hours=20)
    await _put_app(store, app)


async def ensure_demo_applications(store: Store, mail: MailProvider, user_id: str) -> None:
    if not settings.demo_applications:
        return
    svc = ApplicationService(store, mail)
    try:
        family_id = await svc._family_id(user_id)
    except DomainError:
        return
    marker = f"demo-apps-{family_id}"
    if await store.get(MARKERS, marker) is not None:
        return
    view, _ = await svc._context(user_id)
    active = [c for c in view.children if c.situation is None]
    unborn = next((c for c in active if c.status == "expected"), None)
    born = sorted((c for c in active if c.status == "born" and c.birth_date), key=lambda c: c.birth_date, reverse=True)
    if unborn is None or not born:
        return  # poczekaj, aż rodzina doda dzieci
    await store.put(MARKERS, {"id": marker, "family_id": family_id})
    if await store.find("applications", family_id=family_id):
        return  # prawdziwe wnioski mają pierwszeństwo — nie mieszamy z przykładami
    now = datetime.now(timezone.utc)
    steps = [
        (_employer_leave, unborn.id),
        (_zus_800plus, born[0].id),
        (_zam_draft, unborn.id),
    ]
    for step, child_id in steps:
        try:
            await step(store, svc, user_id, child_id, now)
        except Exception as e:  # noqa: BLE001 — przykład się nie udał; lista wniosków działa dalej
            logger.warning("Nie utworzono przykładowego wniosku (%s): %s", step.__name__, type(e).__name__)


__all__ = ["ensure_demo_applications", "pf"]
