import pytest
from conftest import login, login_official
from fastapi import Depends
from fastapi.testclient import TestClient

from app.main import create_app
from app.security import (
    AuthError,
    Principal,
    issue_token,
    require_official,
    require_parent,
    verify_token,
)

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"
OFFICIAL = "urzednik.krakow@mrodzina.local"


def test_list_personas(client):
    r = client.get("/api/auth/personas")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert {ANNA, PIOTR} <= ids
    anna = next(p for p in r.json() if p["id"] == ANNA)
    assert set(anna) == {"id", "name", "role_label"}
    assert anna["name"] == "Anna Nowak"


def test_login_persona_creates_user_once(client, store):
    r1 = client.post("/api/auth/mobywatel", json={"persona_id": ANNA})
    r2 = client.post("/api/auth/mobywatel", json={"persona_id": ANNA})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["user"]["id"] == r2.json()["user"]["id"]
    assert r1.json()["user"]["role"] == "parent"
    assert r1.json()["user"]["persona_id"] == ANNA
    assert r1.json()["token"]


def test_unknown_persona_404(client):
    r = client.post("/api/auth/mobywatel", json={"persona_id": "persona-nie-ma"})
    assert r.status_code == 404
    assert "persony" in r.json()["detail"].lower()


def test_me_returns_user(client):
    h = login(client, ANNA)
    r = client.get("/api/me", headers=h)
    assert r.status_code == 200
    assert r.json()["name"] == "Anna Nowak"
    assert "password_hash" not in r.json()


def test_me_requires_token_401(client):
    assert client.get("/api/me").status_code == 401


def test_tampered_token_401(client):
    token = login(client, ANNA)["Authorization"].removeprefix("Bearer ")
    payload, sig = token.split(".")
    bad = f"{payload}.{'A' * len(sig)}"
    r = client.get("/api/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401
    assert r.json()["detail"]


def test_token_with_modified_payload_401(client):
    t_anna = login(client, ANNA)["Authorization"].removeprefix("Bearer ")
    t_piotr = login(client, PIOTR)["Authorization"].removeprefix("Bearer ")
    forged = f"{t_piotr.split('.')[0]}.{t_anna.split('.')[1]}"
    r = client.get("/api/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_garbage_authorization_header_401(client):
    for value in ("Bearer", "Bearer a.b.c", "Basic abc", "Bearer ???"):
        assert client.get("/api/me", headers={"Authorization": value}).status_code == 401


def test_expired_token_401(client):
    token = issue_token(Principal("user-nowak-anna", "parent", None, None), ttl_hours=-1)
    r = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_verify_token_roundtrip_and_errors():
    p = Principal("u1", "parent", "f1", None)
    assert verify_token(issue_token(p)) == p
    with pytest.raises(AuthError):
        verify_token("nie-token")
    with pytest.raises(AuthError):
        verify_token(issue_token(p, ttl_hours=-1))


def test_token_for_deleted_user_401(client, store):
    import asyncio

    h = login(client, ANNA)
    asyncio.run(store.delete("users", "user-nowak-anna"))
    assert client.get("/api/me", headers=h).status_code == 401


def _app_with_role_routes(store):
    app = create_app(store)

    @app.get("/_t/official")
    def only_official(p: Principal = Depends(require_official)):
        return {"role": p.role}

    @app.get("/_t/parent")
    def only_parent(p: Principal = Depends(require_parent)):
        return {"role": p.role}

    return app


def test_parent_token_forbidden_on_official_dep_403(store):
    with TestClient(_app_with_role_routes(store)) as c:
        h = login(c, ANNA)
        r = c.get("/_t/official", headers=h)
        assert r.status_code == 403
        assert r.json()["detail"]
        assert c.get("/_t/parent", headers=h).status_code == 200


def test_official_token_forbidden_on_parent_dep_403(store):
    with TestClient(_app_with_role_routes(store)) as c:
        h = login_official(c, OFFICIAL)
        assert c.get("/_t/parent", headers=h).status_code == 403
        assert c.get("/_t/official", headers=h).status_code == 200
        assert c.get("/_t/official").status_code == 401


def test_official_login_ok_and_wrong_password_401(client):
    r = client.post("/api/auth/official", json={"email": OFFICIAL, "password": "demo1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "official"
    assert body["user"]["unit_id"] == "unit-krakow"
    assert "password_hash" not in body["user"]
    bad = client.post("/api/auth/official", json={"email": OFFICIAL, "password": "zle"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/official", json={"email": "x@y.pl", "password": "demo1234"})
    assert unknown.status_code == 401


def test_seed_units_and_officials(store):
    import asyncio

    krakow = asyncio.run(store.get("units", "unit-krakow"))
    assert krakow["level"] == "gmina"
    assert krakow["gmina"] == "Kraków" and krakow["voivodeship"] == "Małopolskie"
    mp = asyncio.run(store.get("units", "unit-malopolskie"))
    assert mp["level"] == "voivodeship"
    users = asyncio.run(store.find("users", role="official"))
    assert {u["email"] for u in users} == {
        "urzednik.krakow@mrodzina.local",
        "urzednik.malopolska@mrodzina.local",
    }
    assert all(u["password_hash"].startswith("scrypt$") for u in users)
