import pytest
from fastapi.testclient import TestClient

from app.ai.llm import FakeLLM, get_llm
from app.config import settings
from app.main import create_app
from app.services.mail_classify import Classification
from conftest import login, send_application


def family(client, persona="persona-nowak-anna"):
    h = login(client, persona)
    client.post("/api/families", headers=h)
    return h


def submit(client, h, **body):
    return send_application(client, h, **body)


def test_status_connected_by_default(client):
    h = family(client)
    s = client.get("/api/mail/status", headers=h).json()
    assert s["connected"] is True and s["provider"] == "gmail-sim"
    assert s["address"].endswith("@gmail.com")
    assert "gmail.com" in s["scope_note"] and "tylko" in s["scope_note"]


def test_threads_only_application_related(client):
    h = family(client)
    assert client.get("/api/mail/threads", headers=h).json() == []  # skrzynka ma maile niezwiązane
    app = submit(client, h)
    [t] = client.get("/api/mail/threads", headers=h).json()
    assert t["application"]["id"] == app["id"]
    assert [m["folder"] for m in t["messages"]] == ["sent"]
    assert t["application"]["applicant_name"] == "Anna Nowak"


def test_submit_then_simulate_replies_changes_application_status(client):
    h = family(client)
    app = submit(client, h)
    assert app["status"] == "sent"
    r = client.post("/api/mail/simulate-replies", headers=h).json()
    assert r["delivered"] == 2 and r["status_changes"] == 2
    [t] = client.get("/api/mail/threads", headers=h).json()
    assert t["application"]["status"] == "accepted"
    assert len(t["messages"]) == 3
    statuses = [m["classification_status"] for m in t["messages"] if m["folder"] == "inbox"]
    assert statuses == ["received", "accepted"]
    notes = client.get("/api/notifications", headers=h).json()
    assert len(notes) == 2 and all(n["kind"] == "status_change" for n in notes)


def test_zus_reply_more_info(client):
    h = family(client)
    submit(client, h, form_code="ZAM")
    client.post("/api/mail/simulate-replies", headers=h)
    [t] = client.get("/api/mail/threads", headers=h).json()
    assert t["application"]["status"] == "more_info"


def test_sync_before_delay_delivers_nothing(client):
    h = family(client)
    submit(client, h)
    r = client.post("/api/mail/sync", headers=h).json()
    assert r == {"new_messages": 0, "status_changes": 0, "to_review": 0}


def test_family_isolation(client):
    anna = family(client)
    submit(client, anna)
    piotr = family(client, "persona-nowak-piotr")
    assert client.get("/api/mail/threads", headers=piotr).json() == []
    client.post("/api/mail/simulate-replies", headers=piotr)
    [t] = client.get("/api/mail/threads", headers=anna).json()
    assert t["application"]["status"] == "sent"


def test_partner_sees_family_threads(client):
    anna = login(client, "persona-nowak-anna")
    code = client.post("/api/families", headers=anna).json()["family"]["invite_code"]
    piotr = login(client, "persona-nowak-piotr")
    assert client.post("/api/families/join", json={"code": code}, headers=piotr).status_code == 201
    submit(client, anna)
    [t] = client.get("/api/mail/threads", headers=piotr).json()
    assert t["application"]["applicant_name"] == "Anna Nowak"


def test_sync_rate_limited(client, monkeypatch):
    h = family(client)
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    assert client.post("/api/mail/sync", headers=h).status_code == 200
    assert client.post("/api/mail/sync", headers=h).status_code == 429


def test_low_confidence_reply_marked_for_review(store):
    app = create_app(store)
    fake = FakeLLM().script(*[Classification(status="other", confidence=0.4, summary="?")] * 2)
    app.dependency_overrides[get_llm] = lambda: fake
    with TestClient(app) as c:
        h = family(c)
        submit(c, h)
        c.post("/api/mail/simulate-replies", headers=h)
        [t] = c.get("/api/mail/threads", headers=h).json()
        assert t["needs_review"] is True and t["application"]["status"] == "sent"


def test_poll_loop_disabled_in_tests(store):
    assert settings.mail_poll_s == 0
    with TestClient(create_app(store)) as c:
        assert c.app.state.mail_poll_task is None


@pytest.mark.asyncio
async def test_poll_once_syncs_active_families(store):
    from datetime import datetime, timezone

    from app.mail.poller import poll_once
    from app.mail.sim_inbox import SimInbox, schedule_reply
    from app.models.application import Application

    await store.put("families", {"id": "fam-x", "name": "X", "owner_id": "u", "member_ids": ["u"]})
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = Application(id="a-x", family_id="fam-x", applicant_id="u", form_code="ZAM", channel="portal_agent",
                    status="sent", recipient_email="wnioski@zus.pl", recipient_domain="zus.pl", sent_at=now,
                    created_at=now)
    await store.put("applications", a.model_dump(mode="json"))
    await schedule_reply(store, a, now)
    app = create_app(store)
    assert await poll_once(app) == 1  # termin odpowiedzi minął (data w przeszłości)
    assert (await store.get("applications", "a-x"))["status"] == "more_info"
