"""Limity zapytań AI (spec §14): okna czasowe na użytkownika i IP + dzienny budżet tokenów aplikacji.

Zasady:
- Fail-closed: każdy błąd wewnątrz limitera/budżetu kończy się 503, nigdy cichym przepuszczeniem.
- Limiter jest w pamięci procesu (jedna replika = dokładne limity; N replik = do N× więcej).
  Budżet tokenów jest w `Store` (`ai_usage`), więc przeżywa restart.
- Nie logujemy treści zapytań — tylko typy błędów.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request

from ..config import settings
from ..security import Principal, current_principal
from ..storage import Store
from .llm import Usage

logger = logging.getLogger("mrodzina.ai.limits")

WARSAW = ZoneInfo("Europe/Warsaw")
Scope = Literal["user", "ip", "budget"]

MSG_RATE = "Zbyt wiele zapytań do asystenta. Spróbuj za chwilę."
MSG_BUDGET = "Asystent AI jest dziś przeciążony. Spróbuj jutro — reszta aplikacji działa normalnie."
MSG_UNAVAILABLE = "Asystent AI jest chwilowo niedostępny. Spróbuj ponownie za chwilę."


class AILimitExceeded(Exception):
    def __init__(self, scope: Scope, retry_after: int) -> None:
        super().__init__(scope)
        self.scope: Scope = scope
        self.retry_after = max(1, int(retry_after))

    @property
    def detail(self) -> str:
        return MSG_BUDGET if self.scope == "budget" else MSG_RATE


Rule = tuple[str, int, int, Scope]  # (key, limit, window_s, scope)


class RateLimiter:
    """Okno przesuwne (log znaczników czasu) z atomowym sprawdzeniem i zapisem pod `asyncio.Lock`."""

    _SWEEP_EVERY = 512

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = asyncio.Lock()
        self._hits: dict[str, tuple[deque[float], int]] = {}
        self._ops = 0

    def _purge(self, key: str, now: float) -> deque[float] | None:
        entry = self._hits.get(key)
        if entry is None:
            return None
        q, window = entry
        while q and q[0] <= now - window:
            q.popleft()
        if not q:
            del self._hits[key]
            return None
        return q

    async def hit(self, key: str, limit: int, window_s: int, scope: Scope = "user") -> None:
        await self.hit_all([(key, limit, window_s, scope)])

    async def hit_all(self, rules: list[Rule]) -> None:
        """Sprawdza wszystkie reguły i dopiero wtedy obciąża wszystkie (wszystko albo nic)."""
        async with self._lock:
            now = self._clock()
            for key, limit, window_s, scope in rules:
                q = self._purge(key, now)
                count = len(q) if q else 0
                if count >= limit:
                    retry = math.ceil(q[0] + window_s - now) if q else window_s
                    raise AILimitExceeded(scope, retry)
            for key, _limit, window_s, _scope in rules:
                self._hits.setdefault(key, (deque(), window_s))[0].append(now)
            self._ops += 1
            if self._ops % self._SWEEP_EVERY == 0:
                self._sweep_locked(now)

    def _sweep_locked(self, now: float) -> None:
        for key in list(self._hits):
            self._purge(key, now)

    async def sweep(self) -> None:
        async with self._lock:
            self._sweep_locked(self._clock())

    def size(self) -> int:
        return len(self._hits)


def warsaw_today() -> date:
    return datetime.now(WARSAW).date()


def seconds_to_warsaw_midnight() -> int:
    now = datetime.now(WARSAW)
    nxt = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=WARSAW)
    return max(1, math.ceil((nxt - now).total_seconds()))


class TokenBudget:
    """Dzienny budżet tokenów całej aplikacji; licznik w `ai_usage` (id = data, strefa Europe/Warsaw)."""

    def __init__(
        self,
        store: Store,
        daily_limit: int,
        today: Callable[[], date] = warsaw_today,
        seconds_to_reset: Callable[[], int] = seconds_to_warsaw_midnight,
    ) -> None:
        self._store = store
        self._limit = daily_limit
        self._today = today
        self._seconds_to_reset = seconds_to_reset
        self._lock = asyncio.Lock()

    async def used(self) -> int:
        doc = await self._store.get("ai_usage", self._today().isoformat())
        return int(doc["tokens"]) if doc else 0

    async def check(self) -> None:
        if await self.used() >= self._limit:
            raise AILimitExceeded("budget", self._seconds_to_reset())

    async def record(self, tokens: int) -> None:
        if tokens <= 0:
            return
        async with self._lock:
            day = self._today().isoformat()
            doc = await self._store.get("ai_usage", day) or {"id": day, "date": day, "tokens": 0}
            doc["tokens"] = int(doc.get("tokens", 0)) + tokens
            await self._store.put("ai_usage", doc)


@dataclass
class GuardContext:
    user_id: str
    ip: str
    feature: str
    budget: TokenBudget | None = None


def client_ip(request: Request) -> str:
    """IP klienta; `X-Forwarded-For` (pierwszy poprawny adres) tylko gdy TRUST_PROXY=true."""
    peer = request.client.host if request.client else "unknown"
    if settings.trust_proxy:
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(first))
        except ValueError:
            return peer
    return peer


def get_limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "ai_limiter", None)
    if limiter is None:
        limiter = request.app.state.ai_limiter = RateLimiter()
    return limiter


def get_budget(request: Request) -> TokenBudget:
    budget = getattr(request.app.state, "ai_budget", None)
    if budget is None:
        budget = request.app.state.ai_budget = TokenBudget(request.app.state.store, settings.ai_daily_tokens)
    return budget


def enforce_max_input(*texts: str | None) -> None:
    """422, gdy łączna długość wejścia przekracza AI_MAX_INPUT_CHARS."""
    if sum(len(t or "") for t in texts) > settings.ai_max_input_chars:
        raise HTTPException(
            422, f"Wiadomość jest za długa (maksymalnie {settings.ai_max_input_chars} znaków)."
        )


def ai_guard(feature: str) -> Callable:
    """Zależność FastAPI: budżet tokenów -> limity użytkownika i IP. Fail-closed (503 przy błędzie)."""

    async def guard(
        request: Request, principal: Principal = Depends(current_principal)
    ) -> GuardContext:
        ip = client_ip(request)
        try:
            budget = get_budget(request)
            await budget.check()  # najpierw budżet: odrzucone żądanie nie zużywa limitu użytkownika
            await get_limiter(request).hit_all(
                [
                    (f"user:{principal.user_id}:m", settings.ai_user_rpm, 60, "user"),
                    (f"user:{principal.user_id}:d", settings.ai_user_daily, 86400, "user"),
                    (f"ip:{ip}:m", settings.ai_ip_rpm, 60, "ip"),
                    (f"ip:{ip}:d", settings.ai_ip_daily, 86400, "ip"),
                ]
            )
        except AILimitExceeded:
            raise
        except Exception as e:  # noqa: BLE001 - fail-closed: nieznany błąd limitera = odmowa
            logger.error("Błąd limitera AI (feature=%s): %s", feature, type(e).__name__)
            raise HTTPException(503, MSG_UNAVAILABLE, headers={"Retry-After": "30"}) from None
        return GuardContext(principal.user_id, ip, feature, budget)

    return guard


async def record_usage(ctx: GuardContext, usage: Usage) -> None:
    """Dolicza zużycie tokenów do dziennego budżetu. Nie rzuca (odpowiedź jest już policzona)."""
    if ctx.budget is None:
        return
    try:
        await ctx.budget.record(usage.prompt_tokens + usage.completion_tokens)
    except Exception as e:  # noqa: BLE001
        logger.error("Nie zapisano zużycia tokenów (feature=%s): %s", ctx.feature, type(e).__name__)
