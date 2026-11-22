"""Przykładowe wnioski „w toku” dla rodziny demo (seed/demo_applications.py)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from tests.conftest import login


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "demo_applications", True)


def _family_with_children(client, headers):
    assert client.post("/api/families", json={}, headers=headers).status_code == 201
    profile = client.get("/api/profile/me", headers=headers).json()
    for k in profile["known_children"]:
        r = client.post(
            "/api/families/me/children",
            json={"name": k["name"], "birth_date": k["birth_date"], "due_date": k["due_date"]},
            headers=headers,
        )
        assert r.status_code == 201, r.text


def test_demo_applications_cover_the_whole_cycle(client, demo_on):
    h = login(client, "persona-nowak-anna")
    _family_with_children(client, h)

    apps = client.get("/api/applications", headers=h).json()
    by_code = {a["form_code"]: a for a in apps}
    assert set(by_code) == {"URLOP-MAC-ROD", "800PLUS", "ZAM"}
    assert by_code["URLOP-MAC-ROD"]["status"] == "received"
    assert by_code["800PLUS"]["status"] == "accepted"
    assert by_code["ZAM"]["status"] in {"draft", "needs_input"}

    threads = {t["application"]["form_code"]: t for t in client.get("/api/mail/threads", headers=h).json()}
    leave = threads["URLOP-MAC-ROD"]["messages"]
    assert [m["folder"] for m in leave] == ["sent", "inbox"]  # PDF do kadr i potwierdzenie otrzymania
    assert threads["800PLUS"]["messages"][-1]["classification_status"] == "accepted"

    # drugie wejście nic nie dubluje
    assert len(client.get("/api/applications", headers=h).json()) == 3


def test_live_reply_updates_status_after_sync(client, store, demo_on):
    h = login(client, "persona-nowak-anna")
    _family_with_children(client, h)
    leave = next(a for a in client.get("/api/applications", headers=h).json() if a["form_code"] == "URLOP-MAC-ROD")

    # kolejka poczty: termin odpowiedzi „zatwierdzony” mija
    pending = asyncio.run(store.get("mail_pending", leave["id"]))
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    asyncio.run(store.put("mail_pending", {**pending, "due_at": past}))

    assert client.post("/api/mail/sync", headers=h).status_code == 200
    after = client.get(f"/api/applications/{leave['id']}", headers=h).json()
    assert after["status"] == "accepted"
    messages = next(t for t in client.get("/api/mail/threads", headers=h).json() if t["application"]["id"] == leave["id"])["messages"]
    assert len([m for m in messages if m["folder"] == "inbox"]) == 2  # bez duplikatu potwierdzenia


def test_no_demo_without_children_or_when_disabled(client):
    h = login(client, "persona-nowak-anna")
    _family_with_children(client, h)
    assert client.get("/api/applications", headers=h).json() == []  # DEMO_APPLICATIONS=0 w testach


def test_demo_applications_are_read_only(client, demo_on):
    """Przykłady widać na liście, ale nie da się ich wypełnić, podpisać ani złożyć (poprawka 26)."""
    h = login(client, "persona-nowak-anna")
    _family_with_children(client, h)
    apps = client.get("/api/applications", headers=h).json()
    assert apps and all(a["demo"] is True for a in apps)
    draft = next(a for a in apps if a["form_code"] == "ZAM")
    for method, path, body in (
        ("post", f"/api/applications/{draft['id']}/answers", {"answers": {"street": "Floriańska"}}),
        ("patch", f"/api/applications/{draft['id']}", {"channel": "pdf_download"}),
        ("post", f"/api/applications/{draft['id']}/sign", None),
        ("post", f"/api/applications/{draft['id']}/submit", None),
    ):
        r = getattr(client, method)(path, json=body, headers=h) if body else getattr(client, method)(path, headers=h)
        assert r.status_code == 403, (path, r.text)
        assert "przykładowy wniosek" in r.json()["detail"]
    # podgląd nadal działa
    assert client.get(f"/api/applications/{draft['id']}", headers=h).status_code == 200


def test_own_applications_are_not_marked_demo(client, demo_on):
    h = login(client, "persona-nowak-anna")
    _family_with_children(client, h)
    kids = client.get("/api/families/me", headers=h).json()["children"]
    unborn = next(c for c in kids if c["status"] == "expected")
    r = client.post("/api/applications", json={"form_code": "ZAM", "child_id": unborn["id"]}, headers=h)
    assert r.status_code == 201 and r.json()["demo"] is False
