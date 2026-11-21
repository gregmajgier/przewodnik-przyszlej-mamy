import logging

from conftest import login

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


def _join(client, ha, hp):
    code = client.post("/api/families", json={}, headers=ha).json()["family"]["invite_code"]
    req = client.post("/api/families/join", json={"code": code}, headers=hp).json()
    client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha)


def test_login_creates_profile_from_zus(client, store):
    import asyncio

    h = login(client, ANNA)
    assert asyncio.run(store.get("profiles", "user-nowak-anna")) is not None
    me = client.get("/api/profile/me", headers=h).json()
    assert me["user_id"] == "user-nowak-anna"
    assert me["ezla"][0]["code"] == "B"
    assert me["insurance"][0]["kind"] == "employment"
    assert len(me["known_children"]) == 3
    assert me["answers"] == {}


def test_second_login_does_not_reset_answers(client):
    h = login(client, ANNA)
    client.patch("/api/profile/me/answers", json={"foster": True}, headers=h)
    h2 = login(client, ANNA)
    assert client.get("/api/profile/me", headers=h2).json()["answers"] == {"foster": True}


def test_profile_visible_to_both_parents_after_join(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    _join(client, ha, hp)
    for h in (ha, hp):
        members = client.get("/api/profile", headers=h).json()["members"]
        assert {m["first_name"] for m in members} == {"Anna", "Piotr"}
        assert {m["user_name"] for m in members} == {"Anna Nowak", "Piotr Nowak"}


def test_profile_not_visible_to_other_family(client):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    client.post("/api/families", json={}, headers=ha)
    client.post("/api/families", json={}, headers=hp)  # osobna rodzina
    members = client.get("/api/profile", headers=hp).json()["members"]
    assert [m["first_name"] for m in members] == ["Piotr"]
    assert "Anna" not in client.get("/api/profile", headers=hp).text


def test_profile_without_family_shows_only_self(client):
    h = login(client, ANNA)
    members = client.get("/api/profile", headers=h).json()["members"]
    assert [m["first_name"] for m in members] == ["Anna"]


def test_patch_answers_merges_and_persists(client):
    h = login(client, ANNA)
    r = client.patch("/api/profile/me/answers", json={"foster": False, "gmina": "Kraków"}, headers=h)
    assert r.status_code == 200
    r = client.patch("/api/profile/me/answers", json={"foster": True}, headers=h)
    assert r.json()["answers"] == {"foster": True, "gmina": "Kraków"}
    assert client.get("/api/profile/me", headers=h).json()["answers"] == {
        "foster": True,
        "gmina": "Kraków",
    }


def test_patch_answers_rejects_non_scalar_values(client):
    h = login(client, ANNA)
    r = client.patch("/api/profile/me/answers", json={"x": {"a": 1}}, headers=h)
    assert r.status_code == 422


def test_zus_preview(client):
    h = login(client, ANNA)
    r = client.get("/api/profile/me/zus", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True
    assert body["insured"] is True
    assert body["ezla"][0]["code"] == "B"
    assert len(body["contributions"]) == 3
    assert body["contributions"][0]["base"] == 7850.0


def test_profile_requires_parent_token(client):
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile/me").status_code == 401


def test_pesel_not_in_logs(client, caplog):
    with caplog.at_level(logging.DEBUG):
        h = login(client, ANNA)
        pesel = client.get("/api/profile/me", headers=h).json()["pesel"]
        client.get("/api/profile", headers=h)
        client.get("/api/profile/me/zus", headers=h)
        client.patch("/api/profile/me/answers", json={"k": "v"}, headers=h)
    assert pesel and pesel not in caplog.text
