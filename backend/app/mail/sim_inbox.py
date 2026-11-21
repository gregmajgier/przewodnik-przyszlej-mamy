"""Symulowana skrzynka odbiorcza rodziny (plan 09): predefiniowane odpowiedzi urzędów po wysyłce wniosku.

- `schedule_reply(store, app, now)` — wołane po wysyłce wniosku (plan 08 `submit`):
  zapisuje oczekującą odpowiedź (`mail_pending`) z terminem `now + MAIL_SIM_REPLY_DELAY_S`.
- `SimInbox.deliver_due(family_id, now, force)` — dostarcza odpowiedzi, którym minął termin (albo wszystkie
  przy `force=True`, „Symuluj odpowiedzi” w demo).
Reguły: pracodawca -> „otrzymaliśmy”, potem „zatwierdzony”; ZUS -> „wezwanie do uzupełnienia”;
gmina/urząd -> „decyzja pozytywna”.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from ..config import settings
from ..models.application import Application
from ..models.mail import MailMessage
from .provider import SimMailProvider
from ..services.mail_filter import domain_of, is_institutional
from ..storage import Store

PENDING = "mail_pending"


def _mid(*parts: str) -> str:
    return hashlib.sha1(":".join(parts).encode()).hexdigest()[:16]


def recipient_kind(app: Application) -> str:
    domain = (app.recipient_domain or domain_of(app.recipient_email)).lower()
    if domain == "zus.pl" or domain.endswith(".zus.pl"):
        return "zus"
    if is_institutional(domain):
        return "office"
    return "employer"


def reply_templates(app: Application) -> list[dict]:
    kind = recipient_kind(app)
    code = app.form_code
    if kind == "employer":
        sender = app.recipient_email or "kadry@pracodawca.example.pl"
        return [
            {
                "from_addr": sender,
                "subject": f"Re: Wniosek {code}",
                "body": "Dzień dobry,\npotwierdzamy otrzymanie wniosku. Dział kadr rozpatrzy go w ciągu 7 dni.\n"
                "Pozdrawiamy, Dział Kadr",
                "in_thread": True,
            },
            {
                "from_addr": sender,
                "subject": f"Re: Wniosek {code}: zatwierdzony",
                "body": "Dzień dobry,\ninformujemy, że wniosek został zatwierdzony. Urlop został ujęty w ewidencji.\n"
                "Pozdrawiamy, Dział Kadr",
                "in_thread": True,
            },
        ]
    if kind == "zus":
        return [
            {
                "from_addr": "zasilki@zus.pl",
                "subject": f"ZUS: wezwanie do uzupełnienia wniosku {code}",
                "body": "Szanowna Pani / Szanowny Panie,\nw celu rozpatrzenia wniosku prosimy o uzupełnienie "
                "dokumentów: zaświadczenia płatnika składek (Z-3a). Termin: 14 dni.\nZakład Ubezpieczeń Społecznych",
                "in_thread": False,
            }
        ]
    return [
        {
            "from_addr": f"swiadczenia@{(app.recipient_domain or 'um.krakow.pl')}",
            "subject": f"Decyzja w sprawie wniosku {code}",
            "body": "Szanowni Państwo,\nuprzejmie informujemy, że wydano decyzję pozytywną. Świadczenie zostanie "
            "wypłacone na wskazany rachunek.\nUrząd",
            "in_thread": False,
        }
    ]


async def schedule_reply(store: Store, app: Application, now: datetime) -> None:
    """Hak dla wysyłki wniosku (plan 08): zaplanuj predefiniowaną odpowiedź. Idempotentne po `app.id`."""
    if await store.get(PENDING, app.id) is not None:
        return
    due = now + timedelta(seconds=settings.mail_sim_reply_delay_s)
    await store.put(
        PENDING,
        {"id": app.id, "family_id": app.family_id, "due_at": due.isoformat(), "delivered": False},
    )


class SimInbox(SimMailProvider):
    async def deliver_reply(self, app: Application, now: datetime) -> list[MailMessage]:
        """Wkłada do skrzynki odpowiedzi na wniosek (stałe `id`/`message_id` — ponowne wywołanie nic nie dubluje)."""
        out: list[MailMessage] = []
        for i, t in enumerate(reply_templates(app)):
            mid = _mid(app.id, str(i))
            msg = MailMessage(
                id=f"mail-reply-{mid}",
                family_id=app.family_id,
                folder="inbox",
                from_addr=t["from_addr"],
                to_addr="",
                subject=t["subject"],
                body=t["body"],
                thread_id=app.thread_id if t["in_thread"] else None,
                message_id=f"<{mid}@sim.reply>",
                received_at=now + timedelta(seconds=i),
                related_application_id=app.id,  # odpowiedź ZUS/urzędu nie ma wątku — wiązanie wprost
            )
            if await self.store.get("mail_messages", msg.id) is None:
                await self.store.put("mail_messages", msg.model_dump(mode="json"))
                out.append(msg)
        return out

    async def deliver_due(self, family_id: str, now: datetime, *, force: bool = False) -> int:
        delivered = 0
        for p in await self.store.find(PENDING, family_id=family_id, delivered=False):
            if not force and datetime.fromisoformat(p["due_at"]) > now:
                continue
            doc = await self.store.get("applications", p["id"])
            if doc is not None:
                delivered += len(await self.deliver_reply(Application.model_validate(doc), now))
            await self.store.put(PENDING, {**p, "delivered": True})
        return delivered
