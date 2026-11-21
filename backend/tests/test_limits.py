import asyncio
from datetime import date

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.ai.limits import (
    AILimitExceeded,
    GuardContext,
    RateLimiter,
    TokenBudget,
    ai_guard,
    enforce_max_input,
    record_usage,
)
from app.ai.llm import Usage
from app.config import settings
from app.main import create_app
from app.storage import MemoryStore
from conftest import login


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


# --- RateLimiter -------------------------------------------------------------------------------


async def test_allows_up_to_limit_then_raises():
    rl = RateLimiter(Clock())
    for _ in range(3):
        await rl.hit("u1", 3, 60)
    with pytest.raises(AILimitExceeded) as e:
        await rl.hit("u1", 3, 60)
    assert e.value.scope == "user"
    assert 1 <= e.value.retry_after <= 60


async def test_window_slides_after_expiry():
    clock = Clock()
    rl = RateLimiter(clock)
    await rl.hit("u1", 2, 60)
    clock.now += 30
    await rl.hit("u1", 2, 60)
    with pytest.raises(AILimitExceeded) as e:
        await rl.hit("u1", 2, 60)
    assert e.value.retry_after == 30  # najstarsze trafienie wygasa za 30 s
    clock.now += 31  # pierwsze trafienie wypadło z okna
    await rl.hit("u1", 2, 60)


async def test_keys_isolated():
    rl = RateLimiter(Clock())
    await rl.hit("a", 1, 60)
    await rl.hit("b", 1, 60)
    with pytest.raises(AILimitExceeded):
        await rl.hit("a", 1, 60)


async def test_zero_limit_always_blocks():
    with pytest.raises(AILimitExceeded):
        await RateLimiter(Clock()).hit("a", 0, 60)


async def test_concurrent_hits_never_exceed_limit():
    rl = RateLimiter(Clock())

    async def one():
        try:
            await rl.hit("u1", 20, 60)
            return True
        except AILimitExceeded:
            return False

    results = await asyncio.gather(*(one() for _ in range(50)))
    assert sum(results) == 20


async def test_hit_all_is_all_or_nothing():
    rl = RateLimiter(Clock())
    await rl.hit("ip", 1, 60, scope="ip")
    with pytest.raises(AILimitExceeded) as e:
        await rl.hit_all([("user", 5, 60, "user"), ("ip", 1, 60, "ip")])
    assert e.value.scope == "ip"
    # klucz "user" nie został obciążony przez odrzucone żądanie
    for _ in range(5):
        await rl.hit("user", 5, 60)


async def test_empty_keys_are_pruned():
    clock = Clock()
    rl = RateLimiter(clock)
    for i in range(50):
        await rl.hit(f"k{i}", 1, 60)
    clock.now += 120
    await rl.sweep()
    assert rl.size() == 0


# --- TokenBudget -------------------------------------------------------------------------------


async def test_budget_blocks_after_limit_and_resets_next_day():
    day = {"d": date(2026, 11, 21)}
    budget = TokenBudget(MemoryStore(), 100, lambda: day["d"])
    await budget.check()
    await budget.record(60)
    await budget.check()
    await budget.record(40)
    with pytest.raises(AILimitExceeded) as e:
        await budget.check()
    assert e.value.scope == "budget"
    assert e.value.retry_after > 0
    day["d"] = date(2026, 11, 22)
    await budget.check()  # nowy dzień — świeży budżet


async def test_budget_persists_in_store():
    store = MemoryStore()
    d = lambda: date(2026, 11, 21)  # noqa: E731
    await TokenBudget(store, 100, d).record(100)
    with pytest.raises(AILimitExceeded):
        await TokenBudget(store, 100, d).check()  # „po restarcie” — nowa instancja, ten sam store
    assert (await store.get("ai_usage", "2026-11-21"))["tokens"] == 100


async def test_budget_concurrent_records_do_not_lose_updates():
    budget = TokenBudget(MemoryStore(), 10_000, lambda: date(2026, 11, 21))
    await asyncio.gather(*(budget.record(10) for _ in range(40)))
    assert await budget.used() == 400


def test_default_today_uses_warsaw_timezone():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.ai.limits import warsaw_today

    assert warsaw_today() == datetime.now(ZoneInfo("Europe/Warsaw")).date()


# --- ai_guard (HTTP) ---------------------------------------------------------------------------


@pytest.fixture
def app_and_client(store):
    app = create_app(store)

    @app.post("/api/_t/ai")
    async def guarded(ctx: GuardContext = Depends(ai_guard("t"))):
        return {"user": ctx.user_id, "ip": ctx.ip, "feature": ctx.feature}

    @app.post("/api/_t/text")
    async def text(body: dict, ctx: GuardContext = Depends(ai_guard("t"))):
        enforce_max_input(body["text"])
        return {"ok": True}

    with TestClient(app) as c:
        yield app, c


def test_guard_requires_login(app_and_client):
    _, c = app_and_client
    assert c.post("/api/_t/ai").status_code == 401


def test_guard_returns_context(app_and_client):
    _, c = app_and_client
    h = login(c, "persona-nowak-anna")
    r = c.post("/api/_t/ai", headers=h)
    assert r.status_code == 200
    assert r.json()["feature"] == "t"
    assert r.json()["user"]


def test_guard_returns_429_with_retry_after_and_polish_detail(app_and_client, monkeypatch):
    _, c = app_and_client
    monkeypatch.setattr(settings, "ai_user_rpm", 2)
    h = login(c, "persona-nowak-anna")
    assert c.post("/api/_t/ai", headers=h).status_code == 200
    assert c.post("/api/_t/ai", headers=h).status_code == 200
    r = c.post("/api/_t/ai", headers=h)
    assert r.status_code == 429
    assert r.json()["detail"] == "Zbyt wiele zapytań do asystenta. Spróbuj za chwilę."
    assert int(r.headers["Retry-After"]) >= 1


def test_guard_daily_user_limit(app_and_client, monkeypatch):
    app, c = app_and_client
    clock = Clock()
    app.state.ai_limiter = RateLimiter(clock)
    monkeypatch.setattr(settings, "ai_user_daily", 3)
    h = login(c, "persona-nowak-anna")
    for _ in range(3):
        clock.now += 120  # poza oknem minutowym
        assert c.post("/api/_t/ai", headers=h).status_code == 200
    clock.now += 120
    r = c.post("/api/_t/ai", headers=h)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 60


def test_guard_ip_limit_applies_across_users(app_and_client, monkeypatch):
    _, c = app_and_client
    monkeypatch.setattr(settings, "ai_ip_rpm", 2)
    a = login(c, "persona-nowak-anna")
    p = login(c, "persona-nowak-piotr")
    assert c.post("/api/_t/ai", headers=a).status_code == 200
    assert c.post("/api/_t/ai", headers=p).status_code == 200
    assert c.post("/api/_t/ai", headers=a).status_code == 429


def test_users_have_separate_user_limits(app_and_client, monkeypatch):
    _, c = app_and_client
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    a = login(c, "persona-nowak-anna")
    p = login(c, "persona-nowak-piotr")
    assert c.post("/api/_t/ai", headers=a).status_code == 200
    assert c.post("/api/_t/ai", headers=p).status_code == 200
    assert c.post("/api/_t/ai", headers=a).status_code == 429


def test_ip_from_forwarded_for_only_when_trusted(app_and_client, monkeypatch):
    _, c = app_and_client
    h = {**login(c, "persona-nowak-anna"), "X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    monkeypatch.setattr(settings, "trust_proxy", False)
    assert c.post("/api/_t/ai", headers=h).json()["ip"] != "203.0.113.7"
    monkeypatch.setattr(settings, "trust_proxy", True)
    assert c.post("/api/_t/ai", headers=h).json()["ip"] == "203.0.113.7"


def test_garbage_forwarded_for_falls_back_to_peer(app_and_client, monkeypatch):
    _, c = app_and_client
    monkeypatch.setattr(settings, "trust_proxy", True)
    h = {**login(c, "persona-nowak-anna"), "X-Forwarded-For": "nie-ip"}
    assert c.post("/api/_t/ai", headers=h).json()["ip"] != "nie-ip"


def test_budget_exhausted_returns_429_with_gentle_message(app_and_client):
    app, c = app_and_client
    budget = TokenBudget(app.state.store, 10, warsaw_today_fixed)
    asyncio.run(budget.record(10))
    app.state.ai_budget = budget
    r = c.post("/api/_t/ai", headers=login(c, "persona-nowak-anna"))
    assert r.status_code == 429
    assert r.json()["detail"] == (
        "Asystent AI jest dziś przeciążony. Spróbuj jutro — reszta aplikacji działa normalnie."
    )
    assert int(r.headers["Retry-After"]) > 0
    # reszta aplikacji działa
    assert c.get("/health").status_code == 200


def warsaw_today_fixed() -> date:
    return date(2026, 11, 21)


def test_budget_rejection_does_not_consume_user_quota(app_and_client, monkeypatch):
    app, c = app_and_client
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    budget = TokenBudget(app.state.store, 10, warsaw_today_fixed)
    asyncio.run(budget.record(10))
    app.state.ai_budget = budget
    h = login(c, "persona-nowak-anna")
    for _ in range(3):
        assert c.post("/api/_t/ai", headers=h).status_code == 429
    app.state.ai_budget = TokenBudget(app.state.store, 10_000, warsaw_today_fixed)
    assert c.post("/api/_t/ai", headers=h).status_code == 200  # limit użytkownika nietknięty


def test_limiter_error_fails_closed(app_and_client):
    app, c = app_and_client

    class BrokenLimiter:
        async def hit_all(self, *_a, **_k):
            raise RuntimeError("boom")

    app.state.ai_limiter = BrokenLimiter()
    r = c.post("/api/_t/ai", headers=login(c, "persona-nowak-anna"))
    assert r.status_code == 503
    assert "Retry-After" in r.headers


def test_budget_store_error_fails_closed(app_and_client):
    app, c = app_and_client

    class BrokenStore:
        async def get(self, *_a, **_k):
            raise RuntimeError("cosmos down")

        async def put(self, *_a, **_k):
            raise RuntimeError("cosmos down")

    app.state.ai_budget = TokenBudget(BrokenStore(), 100, warsaw_today_fixed)
    r = c.post("/api/_t/ai", headers=login(c, "persona-nowak-anna"))
    assert r.status_code == 503


def test_max_input_chars_rejected_422(app_and_client, monkeypatch):
    _, c = app_and_client
    monkeypatch.setattr(settings, "ai_max_input_chars", 10)
    h = login(c, "persona-nowak-anna")
    assert c.post("/api/_t/text", json={"text": "a" * 10}, headers=h).status_code == 200
    r = c.post("/api/_t/text", json={"text": "a" * 11}, headers=h)
    assert r.status_code == 422
    assert "10" in r.json()["detail"]


async def test_record_usage_adds_to_budget():
    budget = TokenBudget(MemoryStore(), 1000, warsaw_today_fixed)
    ctx = GuardContext(user_id="u", ip="1.2.3.4", feature="t", budget=budget)
    await record_usage(ctx, Usage(prompt_tokens=30, completion_tokens=12))
    assert await budget.used() == 42


async def test_record_usage_never_raises_into_request():
    class BrokenStore:
        async def get(self, *_a, **_k):
            raise RuntimeError("x")

    ctx = GuardContext("u", "ip", "t", budget=TokenBudget(BrokenStore(), 10, warsaw_today_fixed))
    await record_usage(ctx, Usage(prompt_tokens=1))  # nie rzuca


def test_ai_status_endpoint(app_and_client):
    _, c = app_and_client
    h = login(c, "persona-nowak-anna")
    r = c.get("/api/ai/status", headers=h)
    assert r.status_code == 200
    assert r.json() == {"mode": "demo", "available": True}
    assert c.get("/api/ai/status").status_code == 401
