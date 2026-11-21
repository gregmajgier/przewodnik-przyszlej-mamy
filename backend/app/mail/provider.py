"""Poczta: interfejs `MailProvider` i symulowana skrzynka (`SimMailProvider`).

Aplikacja nigdy nie wysyła prawdziwych e-maili — `SimMailProvider` zapisuje wiadomość w kolekcji
`mail_messages` (folder `sent`). Prawdziwego dostawcę można podpiąć, implementując ten sam protokół.

Treść wiadomości i załączniki to dane wrażliwe: nie trafiają do logów. W magazynie zapisujemy tylko
metadane załączników (nazwa, rozmiar), nie ich zawartość.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

from fastapi import Depends
from pydantic import BaseModel, Field

from ..storage import Store, get_store


class SentMessage(BaseModel):
    thread_id: str
    message_id: str


class AttachmentInfo(BaseModel):
    filename: str
    size: int


class MailMessage(BaseModel):
    id: str
    family_id: str
    user_id: str  # rodzic, który wysłał wiadomość
    folder: str = "sent"
    thread_id: str
    to: str
    subject: str
    body: str
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    created_at: datetime


class MailProvider(Protocol):
    async def send(
        self,
        family_id: str,
        from_user_id: str,
        to: str,
        subject: str,
        body: str,
        attachments: list[tuple[str, bytes]],
    ) -> SentMessage: ...

    async def list_messages(self, family_id: str) -> list[MailMessage]: ...


class SimMailProvider:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def send(
        self,
        family_id: str,
        from_user_id: str,
        to: str,
        subject: str,
        body: str,
        attachments: list[tuple[str, bytes]],
    ) -> SentMessage:
        message_id = f"mail-{uuid.uuid4().hex[:12]}"
        thread_id = f"thread-{uuid.uuid4().hex[:12]}"
        msg = MailMessage(
            id=message_id,
            family_id=family_id,
            user_id=from_user_id,
            thread_id=thread_id,
            to=to,
            subject=subject,
            body=body,
            attachments=[AttachmentInfo(filename=name, size=len(data)) for name, data in attachments],
            created_at=datetime.now(timezone.utc),
        )
        await self._store.put("mail_messages", msg.model_dump(mode="json"))
        return SentMessage(thread_id=thread_id, message_id=message_id)

    async def list_messages(self, family_id: str) -> list[MailMessage]:
        docs = await self._store.find("mail_messages", family_id=family_id)
        return sorted((MailMessage.model_validate(d) for d in docs), key=lambda m: m.created_at, reverse=True)


def get_mail(store: Store = Depends(get_store)) -> MailProvider:
    """Zależność FastAPI. Testy podmieniają ją przez `app.dependency_overrides[get_mail]`."""
    return SimMailProvider(store)
