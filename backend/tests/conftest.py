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


def send_application(client, headers, form_code: str = "URLOP-MAC-ROD") -> dict:
    """Składa wniosek przez prawdziwy kreator (plan 08): dziecko w drodze → szkic → odpowiedzi → podpis → wysyłka.

    `URLOP-MAC-ROD` idzie e-mailem do pracodawcy, `ZAM` przez agenta w makiecie eZUS. Zwraca wysłany wniosek.
    """
    from datetime import date, timedelta

    children = client.get("/api/families/me/children", headers=headers).json()
    unborn = next((c for c in children if c["status"] == "expected"), None)
    if unborn is None:
        due = (date.today() + timedelta(days=60)).isoformat()
        unborn = client.post(
            "/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=headers
        ).json()
    draft = client.post("/api/applications", json={"form_code": form_code, "child_id": unborn["id"]}, headers=headers)
    assert draft.status_code == 201, draft.text
    app_id = draft.json()["id"]
    answers = {"employer_email": "kadry@kcuw.example.pl"} if form_code == "URLOP-MAC-ROD" else {"street": "Floriańska", "house_no": "12"}
    assert client.post(f"/api/applications/{app_id}/answers", json={"answers": answers}, headers=headers).status_code == 200
    if form_code == "URLOP-MAC-ROD":
        assert client.post(f"/api/applications/{app_id}/sign", headers=headers).status_code == 200
        sent = client.post(f"/api/applications/{app_id}/submit", headers=headers)
    else:
        sent = client.post(f"/api/applications/{app_id}/portal-submitted", headers=headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"
    return sent.json()
