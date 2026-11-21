import asyncio
import os

os.environ.setdefault("MAIL_POLL_S", "0")  # plan 09: bez pętli poczty w tle w testach

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def store():
    """MemoryStore z danymi startowymi (jednostki, urzędnicy)."""
    from app.seed import seed_all
    from app.storage import MemoryStore

    s = MemoryStore()
    asyncio.run(seed_all(s))
    return s


@pytest.fixture
def client(store):
    from app.main import create_app

    with TestClient(create_app(store)) as c:
        yield c


def login(client: TestClient, persona_id: str) -> dict[str, str]:
    """Loguje personę mObywatel i zwraca nagłówki z tokenem."""
    r = client.post("/api/auth/mobywatel", json={"persona_id": persona_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def login_official(client: TestClient, email: str, password: str = "demo1234") -> dict[str, str]:
    r = client.post("/api/auth/official", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
