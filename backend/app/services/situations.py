"""Tryb jaskółki (strata dziecka) i flaga „Za życiem”: zmiana sytuacji dziecka wraz ze skutkami ubocznymi.

Zasady (spec §13.2–13.3):
- zgłosić może każde z rodziców; bez uzasadnień i „czy na pewno?”; operacja jest idempotentna;
- skutki dla obojga rodziców: szkice wniosków o to dziecko anulowane po cichu (status `cancelled`), wysłane
  wnioski dostają `child_loss_note`, **żadnych powiadomień** (drugi rodzic widzi tryb przy następnym wejściu);
- cofnięcie możliwe w każdej chwili (bez limitu czasu) — szkice anulowane przy zgłoszeniu nie wracają;
- dziecko nie jest usuwane z profilu; z trybu wychodzi się tylko ręcznie (`exit_mode`), nigdy automatycznie.

Efekty „pochodne” (ukrywanie świadczeń o dziecku, `loss_support`, wyciszanie terminów) liczą moduły dopasowania
i kalendarza na podstawie `situation` dziecka — wspólne reguły są tu jako czyste funkcje (`mode_of`,
`event_policy`, `loss_support_applies`), żeby nie powielać ich w innych planach.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, Literal

from ..errors import DomainError
from ..models.family import Child
from ..security import Principal
from ..storage import Store

SituationKind = Literal["poronienie", "martwe-urodzenie", "smierc-dziecka"]
KINDS: tuple[str, ...] = ("poronienie", "martwe-urodzenie", "smierc-dziecka")
Mode = Literal["normal", "jaskolka"]

DRAFT_STATUSES = ("draft", "needs_input", "ready")
CHILD_LOSS_NOTE = "Sytuacja dziecka zmieniła się po wysłaniu tego wniosku."
LOSS_SUPPORT_TAG = "loss_support"

NOT_FOUND_CHILD = "Nie znaleziono takiego dziecka."
NO_FAMILY = "Nie należysz jeszcze do żadnej rodziny."
NOTHING_TO_UNDO = "Nie ma zgłoszenia, które można cofnąć."

_locks: dict[str, asyncio.Lock] = {}


def _lock(family_id: str) -> asyncio.Lock:
    return _locks.setdefault(family_id, asyncio.Lock())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(child: Any, key: str) -> Any:
    return child.get(key) if isinstance(child, dict) else getattr(child, key, None)


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- czyste reguły (współdzielone z dopasowaniem i kalendarzem) -------------------------------------------


def in_loss(child: Any) -> bool:
    return _get(child, "situation") == "loss"


def mode_active(child: Any) -> bool:
    """Dziecko w sytuacji straty, a rodzic nie wyszedł jeszcze z trybu."""
    return in_loss(child) and _get(child, "situation_exited_at") is None


def family_mode(children: Iterable[Any]) -> Mode:
    return "jaskolka" if any(mode_active(c) for c in children) else "normal"


def event_policy(children: Iterable[Any]) -> dict[str, Literal["skip", "mute"]]:
    """Polityka dla kalendarza: `skip` — dziecko w sytuacji (bez wpisów o nim), `mute` — inne dzieci, gdy
    rodzina jest w trybie (krytyczne terminy wyciszone, nie usunięte). Dzieci bez wpisu w mapie: bez zmian."""
    kids = list(children)
    mode = family_mode(kids)
    out: dict[str, Literal["skip", "mute"]] = {}
    for c in kids:
        if in_loss(c):
            out[_get(c, "id")] = "skip"
        elif mode == "jaskolka":
            out[_get(c, "id")] = "mute"
    return out


def loss_support_applies(benefit_tags: Iterable[str], children: Iterable[Any]) -> bool:
    """Świadczenia z tagiem `loss_support` pokazujemy tylko rodzinie w trybie jaskółki; pozostałe zawsze."""
    if LOSS_SUPPORT_TAG not in set(benefit_tags):
        return True
    return family_mode(children) == "jaskolka"


# --- dostęp do danych ------------------------------------------------------------------------------------


def _family_id(principal: Principal) -> str:
    if not principal.family_id:
        raise DomainError(404, NO_FAMILY)
    return principal.family_id


async def _children(store: Store, family_id: str) -> list[dict]:
    return await store.find("children", family_id=family_id)


async def _own_child(store: Store, principal: Principal, child_id: str) -> dict:
    family_id = _family_id(principal)
    doc = await store.get("children", child_id)
    if doc is None or doc.get("family_id") != family_id:
        raise DomainError(404, NOT_FOUND_CHILD)
    return doc


async def _save(store: Store, doc: dict) -> Child:
    child = Child.model_validate(doc)
    await store.put("children", child.model_dump(mode="json"))
    return child


# --- skutki uboczne wniosków -----------------------------------------------------------------------------


async def cancel_drafts_for_child(store: Store, family_id: str, child_id: str, now: datetime | None = None) -> int:
    """Szkice (draft/needs_input/ready) o dziecko → `cancelled`; wysłane wnioski → `child_loss_note`.
    Zwraca liczbę anulowanych szkiców. Cicho: bez powiadomień."""
    stamp = (now or _now()).isoformat()
    cancelled = 0
    for app in await store.find("applications", family_id=family_id, child_id=child_id):
        if app.get("status") in DRAFT_STATUSES:
            await store.put("applications", {**app, "status": "cancelled", "cancelled_at": stamp, "cancelled_reason": "child_situation"})
            cancelled += 1
        elif app.get("status") != "cancelled":
            await store.put("applications", {**app, "child_loss_note": CHILD_LOSS_NOTE})
    return cancelled


async def _clear_loss_notes(store: Store, family_id: str, child_id: str) -> None:
    for app in await store.find("applications", family_id=family_id, child_id=child_id):
        if app.get("child_loss_note"):
            await store.put("applications", {k: v for k, v in app.items() if k != "child_loss_note"})


# --- operacje --------------------------------------------------------------------------------------------


async def set_situation(
    store: Store, principal: Principal, child_id: str, kind: SituationKind, *, now: datetime | None = None
) -> Child:
    """Zgłoszenie straty dziecka (idempotentne: drugie zgłoszenie nic nie zmienia i zwraca pierwotne)."""
    if kind not in KINDS:
        raise DomainError(422, "Nieznany rodzaj sytuacji.")
    family_id = _family_id(principal)
    async with _lock(family_id):
        doc = await _own_child(store, principal, child_id)
        if doc.get("situation") == "loss":
            return Child.model_validate(doc)
        stamp = now or _now()
        doc.update(
            situation="loss", situation_kind=kind, situation_at=stamp.isoformat(), situation_exited_at=None
        )
        child = await _save(store, doc)
        await cancel_drafts_for_child(store, family_id, child_id, stamp)
        return child


async def undo_situation(store: Store, principal: Principal, child_id: str) -> Child:
    """Cofnięcie zgłoszenia, w każdej chwili (także po wyjściu z trybu). Anulowane szkice nie wracają."""
    family_id = _family_id(principal)
    async with _lock(family_id):
        doc = await _own_child(store, principal, child_id)
        if doc.get("situation") != "loss":
            raise DomainError(409, NOTHING_TO_UNDO)
        doc.update(situation=None, situation_kind=None, situation_at=None, situation_exited_at=None)
        child = await _save(store, doc)
        await _clear_loss_notes(store, family_id, child_id)
        return child


async def exit_mode(store: Store, principal: Principal, *, now: datetime | None = None) -> None:
    """„Wróć do zwykłego widoku”: kończy tryb, ale dziecko zostaje w sytuacji (jego świadczenia/terminy dalej ukryte)."""
    family_id = _family_id(principal)
    stamp = (now or _now()).isoformat()
    async with _lock(family_id):
        for doc in await _children(store, family_id):
            if mode_active(doc):
                await _save(store, {**doc, "situation_exited_at": stamp})


async def set_serious_illness(store: Store, principal: Principal, child_id: str, value: bool) -> Child:
    """Flaga „Za życiem”: dodaje świadczenia (4000 zł, wsparcie), **bez** przełączania w tryb jaskółki."""
    doc = await _own_child(store, principal, child_id)
    return await _save(store, {**doc, "serious_illness": bool(value)})


async def mode_info(store: Store, principal: Principal) -> dict:
    """Dane dla `GET /api/me/mode`: tryb rodziny, od kiedy, którego dziecka dotyczy i czy można cofnąć zgłoszenie."""
    normal = {"mode": "normal", "since": None, "child_id": None, "can_undo": False}
    if not principal.family_id:
        return normal
    active = [d for d in await _children(store, principal.family_id) if mode_active(d)]
    if not active:
        return normal
    first = min(active, key=lambda d: (_as_dt(d.get("situation_at")) or datetime.max.replace(tzinfo=timezone.utc), d["id"]))
    since = _as_dt(first.get("situation_at"))
    return {
        "mode": "jaskolka",
        "since": since.isoformat() if since else None,
        "child_id": first["id"],
        # dziecko w trybie zawsze ma `situation == "loss"`, więc zgłoszenie da się cofnąć bez limitu czasu
        "can_undo": True,
    }
