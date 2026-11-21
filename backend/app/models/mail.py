from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MailMessage(BaseModel):
    """Wiadomość w (symulowanej) skrzynce rodziny. Treść nigdy nie trafia do logów."""

    id: str
    family_id: str
    folder: Literal["inbox", "sent"]
    from_addr: str
    to_addr: str
    subject: str
    body: str
    thread_id: str | None = None
    message_id: str
    in_reply_to: str | None = None
    received_at: datetime
    related_application_id: str | None = None
    classified: bool = False
    # wynik klasyfikacji (plan 09) — tylko dla wiadomości powiązanych z wnioskiem
    classification_status: str | None = None
    classification_confidence: float | None = None
    classification_summary: str | None = None
    needs_review: bool = False
