from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Notification(BaseModel):
    """Powiadomienie w aplikacji (prototyp: tylko w aplikacji; e-mail/SMS to wizja)."""

    id: str
    family_id: str
    user_ids: list[str]
    kind: Literal["status_change", "mail_review", "deadline", "warning"]
    text: str
    link: str | None = None
    created_at: datetime
    read: bool = False
    read_by: list[str] = []
