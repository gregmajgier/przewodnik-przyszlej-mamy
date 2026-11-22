from datetime import datetime, timedelta, timezone

from conftest import login, login_official
from test_situations import ANNA, PIOTR, make_family

from app.services import situations


def test_report_status_and_mode_returned_to_both_parents(client, store):
    anna, piotr, ids, _, (ha, hp) = make_family(client, store)
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"

    r = client.post(f"/api/families/me/children/{ids['Dziecko w drodze']}/situation", json={"kind": "poronienie"}, headers=ha)
    assert r.status_code == 200 and r.json()["situation"] == "loss" and r.json()["situation_kind"] == "poronienie"

    for h in (ha, hp):  # oboje rodzice widzą ten sam tryb
        mode = client.get("/api/me/mode", headers=h).json()
        assert mode["mode"] == "jaskolka" and mode["child_id"] == ids["Dziecko w drodze"] and mode["undo_until"]
    assert client.get("/api/notifications", headers=hp).status_code in (200, 404)  # plan 09 może jeszcze nie istnieć
    # zgłoszenie sytuacji nie tworzy powiadomień (jest tylko to o dołączeniu Piotra do rodziny)
    assert {n["kind"] for n in store._data.get("notifications", {}).values()} <= {"family"}


def test_report_is_idempotent(client, store):
    _, _, ids, _, (ha, hp) = make_family(client, store)
    url = f"/api/families/me/children/{ids['Maja']}/situation"
    first = client.post(url, json={"kind": "smierc-dziecka"}, headers=ha).json()
    second = client.post(url, json={"kind": "smierc-dziecka"}, headers=hp)
    assert second.status_code == 200 and second.json()["situation_at"] == first["situation_at"]


def test_invalid_kind_422_and_unauthorized(client, store):
    _, _, ids, _, (ha, _) = make_family(client, store)
    url = f"/api/families/me/children/{ids['Maja']}/situation"
    assert client.post(url, json={"kind": "nieznane"}, headers=ha).status_code == 422
    assert client.post(url, json={"kind": "poronienie"}).status_code == 401
    official = login_official(client, "urzednik.krakow@mrodzina.local")
    assert client.post(url, json={"kind": "poronienie"}, headers=official).status_code == 403
    assert client.get("/api/me/mode", headers=official).status_code == 403


def test_other_family_parent_gets_404(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    client.post("/api/families", json={}, headers=ha)
    child = client.post("/api/families/me/children", json={"name": "Maja", "birth_date": "2019-02-01"}, headers=ha).json()
    client.post("/api/families", json={}, headers=hp)  # Piotr ma własną, osobną rodzinę
    base = f"/api/families/me/children/{child['id']}"
    assert client.post(f"{base}/situation", json={"kind": "poronienie"}, headers=hp).status_code == 404
    assert client.delete(f"{base}/situation", headers=hp).status_code == 404
    assert client.patch(f"{base}/serious-illness", json={"value": True}, headers=hp).status_code == 404
    assert client.get("/api/me/mode", headers=hp).json()["mode"] == "normal"
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"  # nic się nie zmieniło


def test_parent_without_family_gets_404_and_normal_mode(client):
    h = login(client, ANNA)
    assert client.get("/api/me/mode", headers=h).json()["mode"] == "normal"
    r = client.post("/api/families/me/children/x/situation", json={"kind": "poronienie"}, headers=h)
    assert r.status_code == 404


def test_undo_over_api_and_409_after_window(client, store, monkeypatch):
    _, _, ids, _, (ha, hp) = make_family(client, store)
    url = f"/api/families/me/children/{ids['Maja']}/situation"
    client.post(url, json={"kind": "smierc-dziecka"}, headers=ha)
    r = client.delete(url, headers=hp)  # każde z rodziców może cofnąć
    assert r.status_code == 200 and r.json()["situation"] is None
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"
    assert client.delete(url, headers=ha).status_code == 409  # nic do cofnięcia

    client.post(url, json={"kind": "poronienie"}, headers=ha)
    monkeypatch.setattr(situations, "_now", lambda: datetime.now(timezone.utc) + timedelta(days=8))
    r = client.delete(url, headers=ha)
    assert r.status_code == 409 and "Czas na cofnięcie" in r.json()["detail"]
    mode = client.get("/api/me/mode", headers=ha).json()
    assert mode["mode"] == "jaskolka" and mode["undo_until"] is None


def test_exit_mode_over_api(client, store):
    _, _, ids, _, (ha, hp) = make_family(client, store)
    client.post(f"/api/families/me/children/{ids['Antek']}/situation", json={"kind": "smierc-dziecka"}, headers=ha)
    assert client.post("/api/families/me/mode/exit", headers=hp).status_code == 204
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"
    child = next(c for c in client.get("/api/families/me/children", headers=ha).json() if c["id"] == ids["Antek"])
    assert child["situation"] == "loss" and child["name"] == "Antek"  # dziecko zostaje w profilu


def test_serious_illness_over_api_does_not_change_mode(client, store):
    _, _, ids, _, (ha, hp) = make_family(client, store)
    r = client.patch(f"/api/families/me/children/{ids['Maja']}/serious-illness", json={"value": True}, headers=hp)
    assert r.status_code == 200 and r.json()["serious_illness"] is True and r.json()["situation"] is None
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"


def test_generic_patch_cannot_bypass_situation_service(client, store):
    _, _, ids, _, (ha, _) = make_family(client, store)
    r = client.patch(f"/api/families/me/children/{ids['Maja']}", json={"situation": "loss", "situation_kind": "poronienie", "name": "Maja Nowak"}, headers=ha)
    assert r.status_code == 200 and r.json()["name"] == "Maja Nowak" and r.json()["situation"] is None
    assert client.get("/api/me/mode", headers=ha).json()["mode"] == "normal"
