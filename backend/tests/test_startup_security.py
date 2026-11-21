import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.security import hash_password, verify_password
from app.seed import seed_all
from app.seed.officials import OFFICIALS, seed_officials
from app.storage import MemoryStore

LONG_SECRET = "x" * 40


def _boot(store=None):
    with TestClient(create_app(store or MemoryStore())):
        pass


def test_prod_rejects_default_secret(monkeypatch):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "session_secret", "dev-secret-change-me")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _boot()


def test_prod_rejects_short_secret(monkeypatch):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "session_secret", "a" * 31)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _boot()


def test_prod_accepts_long_secret(monkeypatch):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "session_secret", LONG_SECRET)
    monkeypatch.setattr(settings, "official_default_password", "inne-haslo-123")
    _boot()


def test_cosmos_endpoint_counts_as_production(monkeypatch):
    monkeypatch.setattr(settings, "env", "dev")
    monkeypatch.setattr(settings, "cosmos_endpoint", "https://x.documents.azure.com:443/")
    monkeypatch.setattr(settings, "session_secret", "dev-secret-change-me")
    # store podany jawnie, więc Cosmos nie jest naprawdę używany; walidacja i tak ma zadziałać
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _boot()


def test_dev_default_secret_only_warns(monkeypatch, caplog):
    monkeypatch.setattr(settings, "env", "dev")
    monkeypatch.setattr(settings, "session_secret", "dev-secret-change-me")
    with caplog.at_level(logging.WARNING):
        _boot()
    assert "SESSION_SECRET" in caplog.text


def test_seed_does_not_overwrite_existing_password():
    store = MemoryStore()
    asyncio.run(seed_all(store))
    doc = asyncio.run(store.get("users", OFFICIALS[0]["id"]))
    doc["password_hash"] = "scrypt$00$00"  # hasło zmienione przez administratora
    asyncio.run(store.put("users", doc))
    asyncio.run(seed_all(store))
    assert asyncio.run(store.get("users", OFFICIALS[0]["id"]))["password_hash"] == "scrypt$00$00"


def test_seed_creates_missing_official_with_working_password():
    store = MemoryStore()
    asyncio.run(seed_officials(store))
    doc = asyncio.run(store.get("users", OFFICIALS[0]["id"]))
    assert verify_password(settings.official_default_password, doc["password_hash"])


def test_prod_with_default_password_skips_officials(monkeypatch, caplog):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "official_default_password", "demo1234")
    store = MemoryStore()
    with caplog.at_level(logging.WARNING):
        asyncio.run(seed_officials(store))
    assert asyncio.run(store.find("users", role="official")) == []
    assert "OFFICIAL_DEFAULT_PASSWORD" in caplog.text


def test_prod_with_custom_password_seeds_officials(monkeypatch):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "official_default_password", "inne-haslo-123")
    store = MemoryStore()
    asyncio.run(seed_officials(store))
    assert len(asyncio.run(store.find("users", role="official"))) == len(OFFICIALS)


def _set_prod(monkeypatch, password="bardzo-dlugie-haslo-1"):
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "official_default_password", password)


def test_prod_disables_existing_default_password_account(monkeypatch, caplog):
    store = MemoryStore()
    asyncio.run(seed_officials(store))  # tryb dev: konta z hasłem demo1234
    other = asyncio.run(store.get("users", OFFICIALS[1]["id"]))
    other["password_hash"] = hash_password("zmienione-przez-admina")
    asyncio.run(store.put("users", other))
    _set_prod(monkeypatch)
    with caplog.at_level(logging.WARNING):
        asyncio.run(seed_officials(store))
    assert asyncio.run(store.get("users", OFFICIALS[0]["id"]))["disabled"] is True
    assert not asyncio.run(store.get("users", OFFICIALS[1]["id"])).get("disabled")
    assert "wyłączono" in caplog.text.lower()
    assert "demo1234" not in caplog.text


def test_prod_disables_default_password_even_when_seeding_skipped(monkeypatch):
    store = MemoryStore()
    asyncio.run(seed_officials(store))
    _set_prod(monkeypatch, password="demo1234")
    asyncio.run(seed_officials(store))
    users = asyncio.run(store.find("users", role="official"))
    assert users and all(u["disabled"] is True for u in users)


def test_disabled_official_cannot_login(client, store):
    creds = {"email": OFFICIALS[0]["email"], "password": "demo1234"}
    ok = client.post("/api/auth/official", json=creds)
    assert ok.status_code == 200
    token = ok.json()["token"]
    doc = asyncio.run(store.get("users", OFFICIALS[0]["id"]))
    asyncio.run(store.put("users", {**doc, "disabled": True}))
    bad = client.post("/api/auth/official", json=creds)
    wrong = client.post("/api/auth/official", json={**creds, "password": "zle"})
    assert bad.status_code == wrong.status_code == 401
    assert bad.json() == wrong.json()
    # istniejący token wyłączonego konta też przestaje działać
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_prod_rejects_short_official_password(monkeypatch, caplog):
    _set_prod(monkeypatch, password="krotkie-1234")  # 12 znaków = ok
    store = MemoryStore()
    asyncio.run(seed_officials(store))
    assert len(asyncio.run(store.find("users", role="official"))) == len(OFFICIALS)
    _set_prod(monkeypatch, password="krotkie-123")  # 11 znaków
    store = MemoryStore()
    with caplog.at_level(logging.WARNING):
        asyncio.run(seed_officials(store))
    assert asyncio.run(store.find("users", role="official")) == []
    assert "12" in caplog.text
