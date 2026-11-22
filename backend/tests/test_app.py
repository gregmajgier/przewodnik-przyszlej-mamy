import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import MemoryStore


@pytest.mark.parametrize("origin", ["http://localhost:5174", "http://127.0.0.1:5174"])
def test_landing_origins_are_allowed_for_calculator(origin):
    with TestClient(create_app(store=MemoryStore())) as c:
        response = c.options(
            "/api/silnik/ocena",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_existing_wnioski_router_still_mounted(client):
    r = client.get("/api/wnioski")
    assert r.status_code == 200
    assert isinstance(r.json(), list) and r.json()


def test_create_app_without_store_uses_memory_store():
    app = create_app()
    assert isinstance(app.state.store, MemoryStore)
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
