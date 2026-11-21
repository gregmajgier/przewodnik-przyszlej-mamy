"""Cykl pobierania poczty rodziny (plan 09): nowe wiadomości -> dopasowanie do wniosku -> klasyfikacja LLM
-> zmiana statusu (pewność >= 0.8) albo „do sprawdzenia”, plus powiadomienia w aplikacji.

Idempotentne: przetworzona wiadomość ma `classified=True`, a powiadomienie stałe `id` (po wiadomości).
LLM nie jest wołany dla maili niezwiązanych z wnioskami.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from ..ai.llm import LLM, track_usage
from ..models.application import Application
from ..models.mail import MailMessage
from ..models.notification import Notification
from ..storage import Store
from .mail_classify import STATUS_LABEL, classify
from .mail_filter import find_application

logger = logging.getLogger("mrodzina.mail")

CONFIDENCE_THRESHOLD = 0.8
MAX_CLASSIFY_PER_SYNC = 20
ESTIMATED_TOKENS = 1200
STATUS_CHANGES = {"received", "more_info", "accepted", "rejected"}


class SyncReport(BaseModel):
    new_messages: int = 0
    status_changes: int = 0
    to_review: int = 0


async def _members(store: Store, family_id: str) -> list[str]:
    fam = await store.get("families", family_id)
    return list(fam["member_ids"]) if fam else []


async def notify(store: Store, n: Notification) -> None:
    if await store.get("notifications", n.id) is None:
        await store.put("notifications", n.model_dump(mode="json"))


async def sync_family_mail(
    store: Store, mail, llm: LLM, family_id: str, now: datetime, *, budget=None
) -> SyncReport:
    """`mail` — MailProvider (z opcjonalnym `deliver_due` symulacji). `budget` — TokenBudget dla pracy w tle."""
    report = SyncReport()
    if hasattr(mail, "deliver_due"):
        await mail.deliver_due(family_id, now)
    apps = [
        Application.model_validate(d)
        for d in await store.find("applications", family_id=family_id)
        if d.get("sent_at")
    ]
    if not apps:
        return report
    members = await _members(store, family_id)
    # tryb jaskółki: o sprawach dziecka w sytuacji straty nie wysyłamy powiadomień (status i tak się aktualizuje)
    loss_children = {c["id"] for c in await store.find("children", family_id=family_id) if c.get("situation") == "loss"}

    async def emit(store_: Store, n: Notification) -> None:
        if app.child_id not in loss_children:
            await notify(store_, n)

    msgs: list[MailMessage] = await mail.list_messages(family_id)
    pending = [m for m in msgs if m.folder == "inbox" and not m.classified]
    for msg in sorted(pending, key=lambda m: (m.received_at, m.id)):
        app = find_application(msg, apps)
        if app is None:
            continue  # niezwiązana — nie czytamy jej treści
        if report.new_messages >= MAX_CLASSIFY_PER_SYNC:
            break
        reservation = await budget.reserve(ESTIMATED_TOKENS) if budget is not None else None
        try:
            with track_usage() as usage:
                result = await classify(llm, msg)
        finally:
            if reservation is not None:
                await reservation.settle(usage.total)
        report.new_messages += 1
        msg.related_application_id = app.id
        msg.classified = True
        msg.classification_status = result.status
        msg.classification_confidence = result.confidence
        msg.classification_summary = result.summary or None

        if result.confidence >= CONFIDENCE_THRESHOLD and result.status in STATUS_CHANGES:
            if app.status != result.status:
                app.status = result.status
                await store.put("applications", app.model_dump(mode="json"))
                report.status_changes += 1
                await emit(
                    store,
                    Notification(
                        id=f"notif-{msg.id}",
                        family_id=family_id,
                        user_ids=members,
                        kind="status_change",
                        text=f"Wniosek {app.form_code}: {STATUS_LABEL[result.status]}."
                        + (f" {result.summary}" if result.summary else ""),
                        link=f"/wnioski/{app.id}",
                        created_at=now,
                    ),
                )
        else:
            msg.needs_review = True
            report.to_review += 1
            await emit(
                store,
                Notification(
                    id=f"notif-{msg.id}",
                    family_id=family_id,
                    user_ids=members,
                    kind="mail_review",
                    text=f"Nowa wiadomość w sprawie wniosku {app.form_code} — sprawdź.",
                    link=f"/wnioski/{app.id}",
                    created_at=now,
                ),
            )
        await store.put("mail_messages", msg.model_dump(mode="json"))
    return report
