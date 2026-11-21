"""Powiadomienia w aplikacji (plan 09). Prototyp: tylko w aplikacji (e-mail/SMS — wizja)."""

from fastapi import APIRouter, Depends

from ..errors import DomainError
from ..models.notification import Notification
from ..security import Principal, require_parent
from ..storage import Store, get_store

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _view(doc: dict, user_id: str) -> Notification:
    n = Notification.model_validate(doc)
    n.read = user_id in n.read_by
    return n


@router.get("")
async def list_notifications(
    p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> list[Notification]:
    if not p.family_id:
        return []
    docs = [d for d in await store.find("notifications", family_id=p.family_id) if p.user_id in d.get("user_ids", [])]
    items = [_view(d, p.user_id) for d in docs]
    items.sort(key=lambda n: (n.created_at, n.id), reverse=True)
    return items[:100]


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str, p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> Notification:
    doc = await store.get("notifications", notification_id)
    if doc is None or doc.get("family_id") != p.family_id or p.user_id not in doc.get("user_ids", []):
        raise DomainError(404, "Nie znaleziono powiadomienia.")
    if p.user_id not in doc.get("read_by", []):
        doc["read_by"] = [*doc.get("read_by", []), p.user_id]
        await store.put("notifications", doc)
    return _view(doc, p.user_id)
