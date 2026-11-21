"""MOCK planu 08 — `app/mail/provider.py` (strona wysyłki skrzynki).

Plan 08 definiuje `MailProvider` (send + list_messages) i `SimMailProvider(store)` zapisujący do
`mail_messages` (folder `sent`). Plan 09 rozszerza go o skrzynkę odbiorczą — patrz `app/mail/sim_inbox.py`.
"""

import uuid
from datetime import datetime, timezone
from typing import Protocol

from fastapi import Request
from pydantic import BaseModel

from ..models.mail import MailMessage
from ..storage import Store


class SentMessage(BaseModel):
    thread_id: str
    message_id: str


class MailProvider(Protocol):
    async def send(
        self, family_id: str, from_user_id: str, to: str | None, subject: str, body: str,
        attachments: list[tuple[str, bytes]],
    ) -> SentMessage: ...

    async def list_messages(self, family_id: str) -> list[MailMessage]: ...


class SimMailProvider:
    """Symulowana skrzynka rodziny: wysłane i odebrane maile w kolekcji `mail_messages`."""

    def __init__(self, store: Store) -> None:
        self.store = store

    async def _address(self, family_id: str, user_id: str) -> str:
        user = await self.store.get("users", user_id)
        name = (user or {}).get("name", "rodzic").lower().replace(" ", ".")
        return f"{name}@gmail.com"

    async def send(self, family_id, from_user_id, to, subject, body, attachments) -> SentMessage:
        now = datetime.now(timezone.utc)
        message_id = f"<{uuid.uuid4().hex}@mrodzina.sim>"
        thread_id = f"thread-{uuid.uuid4().hex[:12]}"
        msg = MailMessage(
            id=f"mail-{uuid.uuid4().hex[:12]}",
            family_id=family_id,
            folder="sent",
            from_addr=await self._address(family_id, from_user_id),
            to_addr=to or "",
            subject=subject,
            body=body,
            thread_id=thread_id,
            message_id=message_id,
            received_at=now,
            classified=True,
        )
        await self.store.put("mail_messages", msg.model_dump(mode="json"))
        return SentMessage(thread_id=thread_id, message_id=message_id)

    async def list_messages(self, family_id: str) -> list[MailMessage]:
        docs = await self.store.find("mail_messages", family_id=family_id)
        msgs = [MailMessage.model_validate(d) for d in docs]
        msgs.sort(key=lambda m: (m.received_at, m.id))
        return msgs


def get_mail(request: Request) -> SimMailProvider:
    """Zależność FastAPI (w planie 08: `app.mail.get_mail`)."""
    return SimMailProvider(request.app.state.store)
