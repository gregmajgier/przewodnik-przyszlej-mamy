"""Publiczne API /api/jaskolka/* — bez tokenu, treść z backend/app/data/jaskolka.json."""

SITUATIONS = {"martwe-urodzenie", "poronienie", "wczesniak", "ciezka-choroba", "smierc-dziecka"}
KINDS = {"right", "document", "step"}


def test_situations_public_no_token(client):
    r = client.get("/api/jaskolka/situations")
    assert r.status_code == 200
    data = r.json()
    assert {s["id"] for s in data} == SITUATIONS
    for s in data:
        assert s["label"] and s["intro"]
        assert set(s) == {"id", "label", "intro"}


def test_each_situation_has_checklist_and_source(client):
    for sid in SITUATIONS:
        r = client.get(f"/api/jaskolka/situations/{sid}")
        assert r.status_code == 200, sid
        data = r.json()
        assert data["id"] == sid
        assert len(data["checklist"]) >= 3, sid
        ids = [i["id"] for i in data["checklist"]]
        assert len(ids) == len(set(ids)), f"powtórzone id w {sid}"
        for item in data["checklist"]:
            assert item["title"] and item["body"]
            assert item["kind"] in KINDS
            assert item["source_url"].startswith("https://"), item["id"]
            assert isinstance(item["verify"], bool)
            assert isinstance(item["form_codes"], list)
            assert item["deadline_text"] is None or isinstance(item["deadline_text"], str)


def test_intros_are_calm(client):
    """Bez wykrzykników i „gratulacji” w treści."""
    for sid in SITUATIONS:
        data = client.get(f"/api/jaskolka/situations/{sid}").json()
        texts = [data["intro"]] + [i["title"] + " " + i["body"] for i in data["checklist"]]
        for t in texts:
            assert "!" not in t
            assert "gratulac" not in t.lower()


def test_unknown_situation_404(client):
    r = client.get("/api/jaskolka/situations/nie-ma-takiej")
    assert r.status_code == 404
    assert "sytuacj" in r.json()["detail"].lower()


def test_foundations_list_is_large_enough(client):
    r = client.get("/api/jaskolka/foundations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 15
    for f in data:
        assert set(f) >= {"id", "name", "description", "url", "situations", "region"}
        assert f["situations"], f["id"]
        assert set(f["situations"]) <= SITUATIONS


def test_foundations_filter(client):
    allf = client.get("/api/jaskolka/foundations").json()
    r = client.get("/api/jaskolka/foundations", params={"situation": "wczesniak"})
    assert r.status_code == 200
    data = r.json()
    assert data and len(data) < len(allf)
    assert all("wczesniak" in f["situations"] for f in data)
    for sid in SITUATIONS:
        assert client.get("/api/jaskolka/foundations", params={"situation": sid}).json(), sid


def test_foundations_unknown_situation_404(client):
    r = client.get("/api/jaskolka/foundations", params={"situation": "xyz"})
    assert r.status_code == 404


def test_all_foundation_urls_https(client):
    for f in client.get("/api/jaskolka/foundations").json():
        assert f["url"].startswith("https://"), f["id"]
    ids = [f["id"] for f in client.get("/api/jaskolka/foundations").json()]
    assert len(ids) == len(set(ids))


def test_no_auth_header_needed_and_no_cookies(client):
    r = client.get("/api/jaskolka/situations")
    assert "set-cookie" not in {k.lower() for k in r.headers}
