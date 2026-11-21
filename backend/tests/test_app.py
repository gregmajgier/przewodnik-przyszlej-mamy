from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import MemoryStore


def test_existing_wnioski_router_still_mounted(client):
    r = client.get("/api/wnioski")
    assert r.status_code == 200
    assert isinstance(r.json(), list) and r.json()


def test_create_app_without_store_uses_memory_store():
    app = create_app()
    assert isinstance(app.state.store, MemoryStore)
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
