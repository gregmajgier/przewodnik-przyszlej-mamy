"""Cykliczne sprawdzanie poczty (plan 09): co `MAIL_POLL_S` sekund synchronizuje skrzynki rodzin, które mają
wnioski w toku. Uruchamiane w `lifespan` (gdy `MAIL_POLL_S > 0`; w testach 0). Zużycie tokenów idzie z
dziennego budżetu aplikacji (rezerwacja na każdą klasyfikację)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from ..ai.limits import TokenBudget
from ..ai.llm import get_llm
from ..config import settings
from ..services.mail_sync import sync_family_mail
from .sim_inbox import SimInbox

logger = logging.getLogger("mrodzina.mail")

ACTIVE = {"sent", "received", "more_info"}


async def poll_once(app: FastAPI) -> int:
    store = app.state.store
    budget = getattr(app.state, "ai_budget", None)
    if budget is None:
        budget = app.state.ai_budget = TokenBudget(store, settings.ai_daily_tokens)
    families = {d["family_id"] for d in await store.find("applications") if d.get("status") in ACTIVE}
    now = datetime.now(timezone.utc)
    changed = 0
    for fid in sorted(families):
        try:
            report = await sync_family_mail(store, SimInbox(store), get_llm(), fid, now, budget=budget)
            changed += report.status_changes
        except Exception as e:  # noqa: BLE001 - jedna rodzina nie zatrzymuje pętli; bez treści w logu
            logger.error("Synchronizacja poczty nie powiodła się: %s", type(e).__name__)
    return changed


async def poll_loop(app: FastAPI) -> None:
    interval = max(5, settings.mail_poll_s)
    while True:
        await asyncio.sleep(interval)
        try:
            await poll_once(app)
        except Exception as e:  # noqa: BLE001
            logger.error("Pętla poczty: %s", type(e).__name__)
