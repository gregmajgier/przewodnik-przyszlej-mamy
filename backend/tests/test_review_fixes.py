"""Regresje z końcowego przeglądu integracji planów 03–10."""

import asyncio
from datetime import date, timedelta

from app.tools.chat_tools import _safe_answers
from conftest import login, send_application


def _family(client, name="persona-nowak-anna"):
    h = login(client, name)
    client.post("/api/families", headers=h)
    return h


def test_replies_attach_to_their_own_applications(client):
    h = _family(client)
    a = send_application(client, h, "ZAM")
    b = send_application(client, h, "ZAM")
    client.post("/api/mail/simulate-replies", headers=h)
    statuses = {x["id"]: x["status"] for x in client.get("/api/applications", headers=h).json()}
    assert statuses[a["id"]] == "more_info" and statuses[b["id"]] == "more_info"


def test_chat_profile_never_includes_wizard_answers():
    safe = _safe_answers({"benefit:nat-dobry-start:szkola": True, "account_number": "PL611090", "phone": "500", "street": "X"})
    assert safe == {"benefit:nat-dobry-start:szkola": True}


def test_calendar_hides_applications_of_lost_child(client):
    h = _family(client)
    app = send_application(client, h, "ZAM")
    assert any(e["source_ref"] == f"application:{app['id']}" for e in client.get("/api/calendar", headers=h).json())
    client.post(f"/api/families/me/children/{app['child_id']}/situation", json={"kind": "poronienie"}, headers=h)
    assert not any(e["source_ref"] == f"application:{app['id']}" for e in client.get("/api/calendar", headers=h).json())


def test_deleting_child_cancels_its_drafts(client, store):
    h = _family(client)
    due = (date.today() + timedelta(days=60)).isoformat()
    child = client.post("/api/families/me/children", json={"name": "M", "due_date": due}, headers=h).json()
    draft = client.post("/api/applications", json={"form_code": "ZAM", "child_id": child["id"]}, headers=h).json()
    assert client.delete(f"/api/families/me/children/{child['id']}", headers=h).status_code == 204
    assert asyncio.run(store.get("applications", draft["id"]))["status"] == "cancelled"


def test_client_cannot_create_child_in_loss_state(client):
    h = _family(client)
    body = {"name": "M", "due_date": (date.today() + timedelta(days=60)).isoformat(), "situation": "loss",
            "situation_kind": "poronienie", "situation_at": "2099-01-01T00:00:00Z"}
    child = client.post("/api/families/me/children", json=body, headers=h).json()
    assert child["situation"] is None and child["situation_at"] is None
