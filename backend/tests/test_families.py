from datetime import date, datetime, timedelta, timezone

import pytest
from conftest import login

from app.errors import DomainError
from app.services.families import FamilyService

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


# ---------- pomocnicze (API) ----------


def create_family(client, h, **body):
    r = client.post("/api/families", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def family_with_both_parents(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    fam = create_family(client, ha)
    code = fam["family"]["invite_code"]
    r = client.post("/api/families/join", json={"code": code}, headers=hp)
    assert r.status_code == 201, r.text
    req_id = r.json()["id"]
    r = client.post(f"/api/families/me/join-requests/{req_id}/accept", headers=ha)
    assert r.status_code == 200, r.text
    return ha, hp, fam["family"]["id"], code


# ---------- API ----------


def test_create_family_sets_owner_and_code(client):
    h = login(client, ANNA)
    view = create_family(client, h)
    fam = view["family"]
    assert fam["owner_id"] == "user-nowak-anna"
    assert fam["member_ids"] == ["user-nowak-anna"]
    assert fam["name"] == "Rodzina Nowak"
    import re

    assert re.fullmatch(r"[A-Z2-9]{8}", fam["invite_code"])
    assert [m["id"] for m in view["members"]] == ["user-nowak-anna"]
    # /api/me odzwierciedla rodzinę
    assert client.get("/api/me", headers=h).json()["family_id"] == fam["id"]


def test_second_family_for_same_user_409(client):
    h = login(client, ANNA)
    create_family(client, h)
    r = client.post("/api/families", json={}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]


def test_me_without_family_404(client):
    h = login(client, ANNA)
    r = client.get("/api/families/me", headers=h)
    assert r.status_code == 404
    assert "rodziny" in r.json()["detail"]


def test_join_flow_pending_then_accept_adds_member(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    fam = create_family(client, ha)["family"]
    r = client.post("/api/families/join", json={"code": fam["invite_code"]}, headers=hp)
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    # przed akceptacją Piotr nie jest członkiem i nie widzi rodziny
    assert client.get("/api/me", headers=hp).json()["family_id"] is None
    assert client.get("/api/families/me", headers=hp).status_code == 404
    mine = client.get("/api/families/join-requests/mine", headers=hp).json()
    assert [m["status"] for m in mine] == ["pending"]
    # założyciel widzi prośbę
    pending = client.get("/api/families/me/join-requests", headers=ha).json()
    assert len(pending) == 1 and pending[0]["user_name"] == "Piotr Nowak"
    view = client.get("/api/families/me", headers=ha).json()
    assert len(view["pending_requests"]) == 1
    # akceptacja
    r = client.post(f"/api/families/me/join-requests/{pending[0]['id']}/accept", headers=ha)
    assert r.status_code == 200
    assert r.json()["family"]["member_ids"] == ["user-nowak-anna", "user-nowak-piotr"]
    assert client.get("/api/me", headers=hp).json()["family_id"] == fam["id"]
    view_p = client.get("/api/families/me", headers=hp).json()
    assert {m["name"] for m in view_p["members"]} == {"Anna Nowak", "Piotr Nowak"}
    assert view_p["pending_requests"] == []


def test_reject_keeps_user_out(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    fam = create_family(client, ha)["family"]
    req = client.post("/api/families/join", json={"code": fam["invite_code"]}, headers=hp).json()
    r = client.post(f"/api/families/me/join-requests/{req['id']}/reject", headers=ha)
    assert r.status_code == 200
    assert client.get("/api/me", headers=hp).json()["family_id"] is None
    assert client.get("/api/families/me", headers=ha).json()["family"]["member_ids"] == [
        "user-nowak-anna"
    ]
    # po odrzuceniu nie można ponownie rozstrzygnąć
    r = client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha)
    assert r.status_code == 409


def test_only_owner_can_decide_403(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    fam = create_family(client, ha)["family"]
    req = client.post("/api/families/join", json={"code": fam["invite_code"]}, headers=hp).json()
    # wnioskujący nie może sam siebie zaakceptować
    r = client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=hp)
    assert r.status_code in (403, 404)
    assert client.get("/api/me", headers=hp).json()["family_id"] is None


def test_invalid_code_404(client):
    h = login(client, PIOTR)
    r = client.post("/api/families/join", json={"code": "ZZZZZZZZ"}, headers=h)
    assert r.status_code == 404
    assert "kod" in r.json()["detail"].lower()
    assert client.post("/api/families/join", json={"code": ""}, headers=h).status_code == 404


def test_code_is_case_and_space_insensitive(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    code = create_family(client, ha)["family"]["invite_code"]
    r = client.post("/api/families/join", json={"code": f" {code.lower()} "}, headers=hp)
    assert r.status_code == 201


def test_join_own_family_409(client):
    h = login(client, ANNA)
    code = create_family(client, h)["family"]["invite_code"]
    r = client.post("/api/families/join", json={"code": code}, headers=h)
    assert r.status_code == 409


def test_duplicate_join_request_409(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    code = create_family(client, ha)["family"]["invite_code"]
    assert client.post("/api/families/join", json={"code": code}, headers=hp).status_code == 201
    assert client.post("/api/families/join", json={"code": code}, headers=hp).status_code == 409


def test_rotate_invite_code_invalidates_old(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    old = create_family(client, ha)["family"]["invite_code"]
    r = client.post("/api/families/me/invite-code", headers=ha)
    assert r.status_code == 200
    new = r.json()["invite_code"]
    assert new != old
    assert client.post("/api/families/join", json={"code": old}, headers=hp).status_code == 404
    assert client.post("/api/families/join", json={"code": new}, headers=hp).status_code == 201


def test_only_owner_can_rotate_code(client):
    ha, hp, _, _ = family_with_both_parents(client)
    assert client.post("/api/families/me/invite-code", headers=hp).status_code == 403


def test_endpoints_require_parent_token(client):
    assert client.get("/api/families/me").status_code == 401
    assert client.post("/api/families", json={}).status_code == 401


def test_single_parent_family_view_ok(client):
    h = login(client, ANNA)
    create_family(client, h)
    r = client.post(
        "/api/families/me/children",
        json={"name": "Maja", "birth_date": "2018-05-01"},
        headers=h,
    )
    assert r.status_code == 201
    view = client.get("/api/families/me", headers=h).json()
    assert len(view["members"]) == 1
    assert [c["name"] for c in view["children"]] == ["Maja"]
    assert view["pending_requests"] == []


def test_child_requires_birth_or_due_date_422(client):
    h = login(client, ANNA)
    create_family(client, h)
    r = client.post("/api/families/me/children", json={"name": "Bez daty"}, headers=h)
    assert r.status_code == 422


def test_expected_child_allowed_with_due_date(client):
    h = login(client, ANNA)
    create_family(client, h)
    due = (date.today() + timedelta(days=60)).isoformat()
    r = client.post(
        "/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=h
    )
    assert r.status_code == 201
    child = r.json()
    assert child["status"] == "expected" and child["due_date"] == due
    assert child["birth_date"] is None
    assert child["situation"] is None and child["serious_illness"] is False


def test_born_child_status_default(client):
    h = login(client, ANNA)
    create_family(client, h)
    r = client.post(
        "/api/families/me/children", json={"name": "Jaś", "birth_date": "2022-01-02"}, headers=h
    )
    assert r.json()["status"] == "born"


def test_children_without_family_404(client):
    h = login(client, ANNA)
    assert client.get("/api/families/me/children", headers=h).status_code == 404
    r = client.post(
        "/api/families/me/children", json={"name": "A", "birth_date": "2020-01-01"}, headers=h
    )
    assert r.status_code == 404


def test_children_isolated_between_families(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    create_family(client, ha)
    create_family(client, hp)
    child = client.post(
        "/api/families/me/children", json={"name": "Maja", "birth_date": "2018-05-01"}, headers=ha
    ).json()
    assert client.get("/api/families/me/children", headers=hp).json() == []
    assert client.patch(
        f"/api/families/me/children/{child['id']}", json={"name": "Hak"}, headers=hp
    ).status_code == 404
    assert client.delete(f"/api/families/me/children/{child['id']}", headers=hp).status_code == 404
    assert client.get("/api/families/me/children", headers=ha).json()[0]["name"] == "Maja"


def test_patch_and_delete_child(client):
    h = login(client, ANNA)
    create_family(client, h)
    child = client.post(
        "/api/families/me/children",
        json={"name": "Maluszek", "due_date": "2026-12-31"},
        headers=h,
    ).json()
    url = f"/api/families/me/children/{child['id']}"
    r = client.patch(url, json={"birth_date": "2026-12-20", "pesel": "26122000000"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "born" and r.json()["pesel"] == "26122000000"
    # nie można odebrać obu dat
    assert client.patch(url, json={"birth_date": None, "due_date": None}, headers=h).status_code == 422
    assert client.delete(url, headers=h).status_code == 204
    assert client.get("/api/families/me/children", headers=h).json() == []
    assert client.delete(url, headers=h).status_code == 404


def test_both_parents_see_same_children_after_join(client):
    ha, hp, _, _ = family_with_both_parents(client)
    client.post(
        "/api/families/me/children", json={"name": "Maja", "birth_date": "2018-05-01"}, headers=ha
    )
    client.post(
        "/api/families/me/children", json={"name": "Jaś", "birth_date": "2022-01-02"}, headers=hp
    )
    names_a = sorted(c["name"] for c in client.get("/api/families/me/children", headers=ha).json())
    names_p = sorted(c["name"] for c in client.get("/api/families/me/children", headers=hp).json())
    assert names_a == names_p == ["Jaś", "Maja"]


# ---------- serwis ----------


async def _user(store, uid, name="Jan Test"):
    await store.put("users", {"id": uid, "role": "parent", "name": name, "family_id": None})


async def test_third_member_409(store):
    svc = FamilyService(store)
    for uid in ("u1", "u2", "u3"):
        await _user(store, uid)
    fam = await svc.create_family("u1")
    req = await svc.request_join("u2", fam.invite_code)
    await svc.decide("u1", req.id, True)
    with pytest.raises(DomainError) as e:
        await svc.request_join("u3", fam.invite_code)
    assert e.value.status_code == 409
    assert "dwoje" in e.value.detail


async def test_accept_when_family_filled_meanwhile_409(store):
    svc = FamilyService(store)
    for uid in ("u1", "u2", "u3"):
        await _user(store, uid)
    fam = await svc.create_family("u1")
    r2 = await svc.request_join("u2", fam.invite_code)
    r3 = await svc.request_join("u3", fam.invite_code)
    await svc.decide("u1", r2.id, True)
    with pytest.raises(DomainError) as e:
        await svc.decide("u1", r3.id, True)
    assert e.value.status_code == 409
    assert (await store.get("users", "u3"))["family_id"] is None


async def test_expired_code_404(store):
    svc = FamilyService(store)
    await _user(store, "u1")
    await _user(store, "u2")
    fam = await svc.create_family("u1")
    doc = await store.get("families", fam.id)
    doc["invite_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await store.put("families", doc)
    with pytest.raises(DomainError) as e:
        await svc.request_join("u2", fam.invite_code)
    assert e.value.status_code == 404
    assert "wygasł" in e.value.detail


async def test_user_in_other_family_cannot_join_409(store):
    svc = FamilyService(store)
    for uid in ("u1", "u2"):
        await _user(store, uid)
    f1 = await svc.create_family("u1")
    await svc.create_family("u2")
    with pytest.raises(DomainError) as e:
        await svc.request_join("u2", f1.invite_code)
    assert e.value.status_code == 409
