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
Scope = Literal["user", "ip", "budget", "busy"]

MSG_RATE = "Zbyt wiele zapytań do asystenta. Spróbuj za chwilę."
MSG_BUDGET = "Asystent AI jest dziś przeciążony. Spróbuj jutro — reszta aplikacji działa normalnie."
MSG_BUSY = "Asystent AI jest teraz mocno obciążony. Spróbuj za chwilę."
MSG_UNAVAILABLE = "Asystent AI jest chwilowo niedostępny. Spróbuj ponownie za chwilę."


class AILimitExceeded(Exception):
    def __init__(self, scope: Scope, retry_after: int) -> None:
        super().__init__(scope)
        self.scope: Scope = scope
        self.retry_after = max(1, int(retry_after))

    @property
    def detail(self) -> str:
        return {"budget": MSG_BUDGET, "busy": MSG_BUSY}.get(self.scope, MSG_RATE)


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
        """Dolicza zużycie bez rezerwacji (np. gdy wywołujący nie użył `ai_guard`)."""
        if tokens > 0:
            await self._adjust(tokens)

    async def _adjust(self, delta: int, *, reserve_limit: int | None = None) -> None:
        """Atomowo (pod blokadą procesu) zmienia licznik dnia. Z `reserve_limit`: odmawia, gdy
        po zmianie licznik przekroczyłby limit (check+increment w jednym kroku).

        Uwaga: `Store` nie ma atomowego inkrementu, więc atomowość dotyczy jednego procesu. Przy wielu
        replikach potrzebny jest inkrement po stronie bazy (Cosmos patch/ETag) — patrz docs/dev.md.
        """
        async with self._lock:
            day = self._today().isoformat()
            doc = await self._store.get("ai_usage", day) or {"id": day, "date": day, "tokens": 0}
            current = int(doc.get("tokens", 0))
            if reserve_limit is not None and current + delta > reserve_limit:
                raise AILimitExceeded("budget", self._seconds_to_reset())
            doc["tokens"] = max(0, current + delta)
            await self._store.put("ai_usage", doc)

    async def reserve(self, estimated_tokens: int) -> Reservation:
        """Atomowo sprawdza budżet i rezerwuje `estimated_tokens`; po odpowiedzi `settle(real)`,
        przy błędzie `release()`. Odmowa (`AILimitExceeded`) niczego nie obciąża."""
        n = max(0, int(estimated_tokens))
        await self._adjust(n, reserve_limit=self._limit)
        return Reservation(self, n)


class Reservation:
    """Zarezerwowane tokeny; rozliczane dokładnie raz (`settle` albo `release`)."""

    def __init__(self, budget: TokenBudget, tokens: int) -> None:
        self._budget = budget
        self.tokens = tokens
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    async def settle(self, actual_tokens: int) -> None:
        if self._done:
            return
        self._done = True  # także gdy zapis się nie uda: nie rozliczamy dwa razy
        await self._budget._adjust(max(0, int(actual_tokens)) - self.tokens)

    async def release(self) -> None:
        if self._done:
            return
        self._done = True
        await self._budget._adjust(-self.tokens)


class InflightGate:
    """Limit równoległych żądań AI (jeden proces; operacje bez `await`, więc atomowe w asyncio)."""

    def __init__(self) -> None:
        self.current = 0

    def acquire(self, max_inflight: int) -> None:
        if self.current >= max_inflight:
            raise AILimitExceeded("busy", 5)
        self.current += 1

    def release(self) -> None:
        self.current = max(0, self.current - 1)


@dataclass
class GuardContext:
    user_id: str
    ip: str
    feature: str
    budget: TokenBudget | None = None
    reservation: Reservation | None = None

    async def release(self) -> None:
        """Zwraca rezerwację tokenów (wołać, gdy wywołanie modelu się nie odbyło/nie powiodło)."""
        if self.reservation is not None:
            try:
                await self.reservation.release()
            except Exception as e:  # noqa: BLE001
                logger.error("Nie zwrócono rezerwacji tokenów (feature=%s): %s", self.feature, type(e).__name__)


def client_ip(request: Request) -> str:
    """IP klienta. `X-Forwarded-For` tylko przy TRUST_PROXY_HOPS=N>0: bierzemy N-ty wpis od PRAWEJ
    (dopisany przez nasze zaufane proxy); wpisy z lewej kontroluje klient i są ignorowane.
    Za mało wpisów lub niepoprawny adres -> adres połączenia."""
    peer = request.client.host if request.client else "unknown"
    hops = settings.trust_proxy_hops
    if hops <= 0:
        return peer
    parts = [p.strip() for line in request.headers.getlist("x-forwarded-for") for p in line.split(",")]
    if len(parts) < hops:
        return peer
    try:
        return str(ipaddress.ip_address(parts[-hops]))
    except ValueError:
        return peer


def get_limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "ai_limiter", None)
    if limiter is None:
        limiter = request.app.state.ai_limiter = RateLimiter()
    return limiter


def get_gate(request: Request) -> InflightGate:
    gate = getattr(request.app.state, "ai_inflight", None)
    if gate is None:
        gate = request.app.state.ai_inflight = InflightGate()
    return gate


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


def ai_guard(feature: str, reserve_tokens: int | None = None) -> Callable:
    """Zależność FastAPI (z `yield`): limit równoległych żądań -> rezerwacja tokenów budżetu -> limity
    użytkownika i IP. Fail-closed (503 przy dowolnym błędzie). Po żądaniu zwalnia slot równoległości;
    niezrealizowana rezerwacja tokenów zostaje (ostrożnie) — endpoint woła `record_usage` albo `ctx.release()`."""

    async def guard(request: Request, principal: Principal = Depends(current_principal)):
        ip = client_ip(request)
        gate = acquired = reservation = None
        try:
            gate = get_gate(request)
            gate.acquire(settings.ai_max_inflight)
            acquired = True
            budget = get_budget(request)
            # najpierw budżet: odmowa budżetu nie zużywa limitów użytkownika/IP
            reservation = await budget.reserve(
                settings.ai_reserve_tokens if reserve_tokens is None else reserve_tokens
            )
            await get_limiter(request).hit_all(
                [
                    (f"user:{principal.user_id}:m", settings.ai_user_rpm, 60, "user"),
                    (f"user:{principal.user_id}:d", settings.ai_user_daily, 86400, "user"),
                    (f"ip:{ip}:m", settings.ai_ip_rpm, 60, "ip"),
                    (f"ip:{ip}:d", settings.ai_ip_daily, 86400, "ip"),
                ]
            )
        except BaseException as e:
            # każda odmowa/błąd po drodze: zwróć rezerwację i slot
            if reservation is not None:
                try:
                    await reservation.release()
                except Exception as re:  # noqa: BLE001
                    logger.error("Nie zwrócono rezerwacji (feature=%s): %s", feature, type(re).__name__)
            if acquired:
                gate.release()
            if isinstance(e, AILimitExceeded) or not isinstance(e, Exception):
                raise
            # fail-closed: nieznany błąd limitera = odmowa
            logger.error("Błąd limitera AI (feature=%s): %s", feature, type(e).__name__)
            raise HTTPException(503, MSG_UNAVAILABLE, headers={"Retry-After": "30"}) from None
        try:
            yield GuardContext(principal.user_id, ip, feature, budget, reservation)
        finally:
            gate.release()

    return guard


async def record_usage(ctx: GuardContext, usage: Usage) -> None:
    """Rozlicza zużycie tokenów: dopasowuje rezerwację do rzeczywistości (albo dolicza, gdy brak
    rezerwacji). Nie rzuca (odpowiedź jest już policzona)."""
    if ctx.budget is None:
        return
    total = usage.prompt_tokens + usage.completion_tokens
    try:
        if ctx.reservation is not None:
            await ctx.reservation.settle(total)
        else:
            await ctx.budget.record(total)
    except Exception as e:  # noqa: BLE001
        logger.error("Nie zapisano zużycia tokenów (feature=%s): %s", ctx.feature, type(e).__name__)
