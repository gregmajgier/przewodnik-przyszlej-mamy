import asyncio
from datetime import date

import pytest
from conftest import login

from app.ai.tools import ToolContext, ToolError, call_tool
from app.models.benefit import Benefit
from app.security import Principal

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


def _family(client, persona=ANNA):
    h = login(client, persona)
    client.post("/api/families", json={}, headers=h)
    for k in client.get("/api/profile/me", headers=h).json()["known_children"]:
        client.post("/api/families/me/children", json=k, headers=h)
    return h


def _by_id(rows):
    return {r["benefit"]["id"]: r for r in rows}


def _local_benefit(store, bid, unit_id, scope="municipal", **kw):
    b = Benefit(
        id=bid,
        name=f"Lokalne {bid}",
        scope=scope,
        unit_id=unit_id,
        category="benefit",
        description="opis",
        how_to_apply="w urzędzie",
        source_url="https://example.gov.pl/x",
        **kw,
    )
    asyncio.run(store.put("benefits", b.model_dump(mode="json")))


# ---------- autoryzacja ----------


@pytest.mark.parametrize(
    "path", ["/api/benefits", "/api/benefits/nat-800plus", "/api/analysis", "/api/summary"]
)
def test_endpoints_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_benefits_list_requires_parent(client):
    from app.security import issue_token

    asyncio.run(
        client.app.state.store.put(
            "users", {"id": "official-x", "role": "official", "name": "Urzędnik", "unit_id": "unit-krakow"}
        )
    )
    token = issue_token(Principal("official-x", "official", None, "unit-krakow"))
    for path in ("/api/benefits", "/api/analysis", "/api/summary"):
        assert client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_parent_without_family_gets_polish_404(client):
    h = login(client, ANNA)
    r = client.get("/api/benefits", headers=h)
    assert r.status_code == 404
    assert "rodzin" in r.json()["detail"].lower()


# ---------- lista ----------


def test_list_contains_only_published_with_matches_sorted(client, store):
    h = _family(client)
    _local_benefit(store, "draft-1", "unit-krakow", status="draft")
    rows = client.get("/api/benefits", headers=h).json()
    ids = [r["benefit"]["id"] for r in rows]
    assert "draft-1" not in ids and "nat-800plus" in ids
    order = {"fits": 0, "maybe": 1, "no": 2}
    statuses = [order[r["match"]["status"]] for r in rows]
    assert statuses == sorted(statuses)
    r800 = _by_id(rows)["nat-800plus"]["match"]
    assert r800["status"] == "fits" and r800["reasons"]


def test_response_never_contains_pesel(client):
    h = _family(client)
    pesel = client.get("/api/profile/me", headers=h).json()["pesel"]
    for path in ("/api/benefits", "/api/analysis", "/api/summary"):
        assert pesel not in client.get(path, headers=h).text


def test_get_single_benefit_and_404(client):
    h = _family(client)
    assert client.get("/api/benefits/nat-kdr", headers=h).json()["benefit"]["id"] == "nat-kdr"
    assert client.get("/api/benefits/nie-ma", headers=h).status_code == 404


def test_local_benefit_visible_only_in_area(client, store):
    h = _family(client)
    _local_benefit(store, "loc-krakow", "unit-krakow")
    _local_benefit(store, "reg-malopolska", "unit-malopolskie", scope="regional")
    _local_benefit(store, "loc-inna", "unit-wieliczka")
    ids = {r["benefit"]["id"] for r in client.get("/api/benefits", headers=h).json()}
    assert {"loc-krakow", "reg-malopolska"} <= ids
    assert "loc-inna" not in ids
    assert client.get("/api/benefits/loc-inna", headers=h).status_code == 404


# ---------- odpowiedzi ----------


def test_answer_changes_maybe_to_fits(client):
    h = _family(client)
    before = _by_id(client.get("/api/benefits", headers=h).json())["nat-dobry-start"]["match"]
    assert before["status"] == "maybe"
    qid = before["questions"][0]["condition_id"]
    r = client.post("/api/benefits/nat-dobry-start/answers", json={"condition_id": qid, "answer": True}, headers=h)
    assert r.status_code == 200
    assert r.json()["match"]["status"] == "fits"
    again = _by_id(client.get("/api/benefits", headers=h).json())["nat-dobry-start"]["match"]
    assert again["status"] == "fits" and again["questions"] == []


def test_answer_false_gives_no_and_is_saved_in_profile(client):
    h = _family(client)
    r = client.post("/api/benefits/nat-dobry-start/answers", json={"condition_id": "school", "answer": False}, headers=h)
    assert r.json()["match"]["status"] == "no"
    answers = client.get("/api/profile/me", headers=h).json()["answers"]
    assert answers["benefit:nat-dobry-start:school"] is False


def test_income_question_answerable(client):
    h = _family(client)
    r = client.post("/api/benefits/nat-zasilek-rodzinny/answers", json={"condition_id": "income", "answer": True}, headers=h)
    assert r.json()["match"]["status"] == "fits"


def test_answer_rejects_unknown_condition(client):
    h = _family(client)
    r = client.post("/api/benefits/nat-800plus/answers", json={"condition_id": "x", "answer": True}, headers=h)
    assert r.status_code == 422


def test_answer_to_unknown_or_invisible_benefit_404(client, store):
    h = _family(client)
    _local_benefit(store, "loc-inna", "unit-wieliczka")
    for bid in ("nie-ma", "loc-inna"):
        r = client.post(f"/api/benefits/{bid}/answers", json={"condition_id": "a", "answer": True}, headers=h)
        assert r.status_code == 404


def test_other_family_answers_not_shared(client):
    ha = _family(client, ANNA)
    hp = login(client, PIOTR)
    client.post("/api/families", json={}, headers=hp)  # osobna rodzina Piotra
    for k in client.get("/api/profile/me", headers=hp).json()["known_children"]:
        client.post("/api/families/me/children", json=k, headers=hp)
    client.post("/api/benefits/nat-dobry-start/answers", json={"condition_id": "school", "answer": True}, headers=ha)
    mine = _by_id(client.get("/api/benefits", headers=ha).json())["nat-dobry-start"]["match"]["status"]
    theirs = _by_id(client.get("/api/benefits", headers=hp).json())["nat-dobry-start"]["match"]["status"]
    assert mine == "fits" and theirs == "maybe"


def test_answers_shared_between_parents_of_same_family(client):
    ha = _family(client, ANNA)
    hp = login(client, PIOTR)
    code = client.get("/api/families/me", headers=ha).json()["family"]["invite_code"]
    req = client.post("/api/families/join", json={"code": code}, headers=hp).json()
    client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha)
    client.post("/api/benefits/nat-dobry-start/answers", json={"condition_id": "school", "answer": True}, headers=ha)
    status = _by_id(client.get("/api/benefits", headers=hp).json())["nat-dobry-start"]["match"]["status"]
    assert status == "fits"


# ---------- analiza i podsumowanie ----------


def test_analysis_counts_match_list(client, store):
    h = _family(client)
    _local_benefit(store, "loc-krakow", "unit-krakow")
    rows = client.get("/api/benefits", headers=h).json()
    a = client.get("/api/analysis", headers=h).json()
    t = a["totals"]
    assert t["fits"] == sum(r["match"]["status"] == "fits" for r in rows)
    assert t["maybe"] == sum(r["match"]["status"] == "maybe" for r in rows)
    assert t["no"] == sum(r["match"]["status"] == "no" for r in rows)
    assert t["national"] + t["local"] == len(rows)
    assert t["local"] == 1
    results = next(s for s in a["steps"] if s["key"] == "results")
    assert f"pasuje do was: {t['fits']}" in results["detail"] and f"może przysługiwać: {t['maybe']}" in results["detail"]


def test_analysis_steps_use_real_data(client):
    h = _family(client)
    a = client.get("/api/analysis", headers=h).json()
    keys = [s["key"] for s in a["steps"]]
    assert keys == ["zus", "contracts", "catalog", "results", "deadlines"]
    zus = a["steps"][0]["detail"]
    assert "umowa o pracę" in zus and "7 850" in zus
    assert a["estimated_annual_total"] > 0


def test_estimated_total_counts_per_child_benefits(client):
    h = _family(client)
    a = client.get("/api/analysis", headers=h).json()
    # 800+ na dwoje dzieci (9600 × 2) + ulga prorodzinna (1112 × 2)
    assert a["estimated_annual_total"] == 9600 * 2 + 1112 * 2


def test_nearest_deadline_and_warning_for_dobry_start(client):
    h = _family(client)
    client.post("/api/benefits/nat-dobry-start/answers", json={"condition_id": "school", "answer": True}, headers=h)
    from app.main import create_app  # noqa: F401  (dzień „dziś” ustawiamy przez zależność)

    from app.routers.benefits import get_today

    client.app.dependency_overrides[get_today] = lambda: date(2026, 11, 21)
    try:
        a = client.get("/api/analysis", headers=h).json()
        nd = a["nearest_deadline"]
        assert nd["benefit_id"] == "nat-dobry-start" and nd["date"] == "2026-11-30" and nd["days_left"] == 9
        deadlines = next(s for s in a["steps"] if s["key"] == "deadlines")
        assert deadlines["status"] == "warning" and "1 termin" in deadlines["detail"]
        s = client.get("/api/summary", headers=h).json()
        assert any("Dobry Start" in w for w in s["warnings"])
    finally:
        client.app.dependency_overrides.pop(get_today, None)


def test_summary_has_parameters_label_and_totals(client):
    h = _family(client)
    s = client.get("/api/summary", headers=h).json()
    assert s["parameters_label"] == f"Parametry ZUS {date.today().year} – aktywne"
    assert s["totals"]["fits"] >= 1 and s["family_name"]


# ---------- narzędzie MCP ----------


@pytest.fixture
def tool_registry(monkeypatch):
    import importlib

    from app.ai import tools as reg

    import app.tools.benefits as mod  # pierwszy import rejestruje narzędzie w prawdziwym rejestrze

    monkeypatch.setattr(reg, "_REGISTRY", {})
    importlib.reload(mod)  # i rejestruje ponownie w pustym rejestrze testu
    return reg


def test_tool_swiadczenia_returns_matches(client, store, tool_registry):
    h = _family(client)
    user = client.get("/api/me", headers=h).json()
    ctx = ToolContext(Principal(user["id"], "parent", user["family_id"]), store, date.today())
    all_rows = asyncio.run(call_tool("swiadczenia", {}, ctx))
    fits = asyncio.run(call_tool("swiadczenia", {"status": "fits"}, ctx))
    assert {r["status"] for r in fits} == {"fits"}
    assert len(fits) < len(all_rows)
    row = next(r for r in all_rows if r["id"] == "nat-800plus")
    assert row["zrodlo"].startswith("https://") and row["dlaczego"]


def test_tool_rejects_bad_status_and_family_less_user(client, store, tool_registry):
    h = login(client, ANNA)
    user = client.get("/api/me", headers=h).json()
    ctx = ToolContext(Principal(user["id"], "parent", None), store, date.today())
    with pytest.raises(ToolError):
        asyncio.run(call_tool("swiadczenia", {"status": "x"}, ctx))
    with pytest.raises(ToolError):
        asyncio.run(call_tool("swiadczenia", {}, ctx))


def test_tool_is_scoped_to_callers_family(client, store, tool_registry):
    ha = _family(client, ANNA)
    ua = client.get("/api/me", headers=ha).json()
    _local_benefit(store, "loc-inna", "unit-wieliczka")
    ctx = ToolContext(Principal(ua["id"], "parent", ua["family_id"]), store, date.today())
    ids = {r["id"] for r in asyncio.run(call_tool("swiadczenia", {}, ctx))}
    assert "loc-inna" not in ids
