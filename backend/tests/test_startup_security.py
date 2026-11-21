import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.security import verify_password
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
