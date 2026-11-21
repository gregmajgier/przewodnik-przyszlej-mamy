import asyncio
import importlib
import sys
from datetime import date, timedelta

import pytest
from conftest import login

from app.ai import tools as reg
from app.ai.tools import ToolContext, ToolError, call_tool
from app.models.benefit import Benefit, Criteria
from app.security import Principal


def _setup_family(client, persona="persona-nowak-anna", third_born=False):
    """Nowakowie: Maja (7 l.), Antek (3 l.) i trzecie dziecko (w drodze albo urodzone)."""
    h = login(client, persona)
    assert client.post("/api/families", json={}, headers=h).status_code == 201
    today = date.today()
    third = (
        {"name": "Hania", "birth_date": (today - timedelta(days=20)).isoformat()}
        if third_born
        else {"name": "Dziecko w drodze", "due_date": (today + timedelta(days=60)).isoformat()}
    )
    for body in (
        {"name": "Maja", "birth_date": (today - timedelta(days=7 * 365 + 90)).isoformat()},
        {"name": "Antek", "birth_date": (today - timedelta(days=3 * 365 + 120)).isoformat()},
        third,
    ):
        r = client.post("/api/families/me/children", json=body, headers=h)
        assert r.status_code == 201, r.text
    return h


def _by_id(client, h):
    r = client.get("/api/benefits", headers=h)
    assert r.status_code == 200, r.text
    return {x["benefit"]["id"]: x for x in r.json()}


def _municipal(id, unit_id, scope="municipal", status="published") -> dict:
    return Benefit(
        id=id,
        name=f"Lokalne {id}",
        scope=scope,
        unit_id=unit_id,
        category="benefit",
        description="opis",
        how_to_apply="w urzędzie",
        source_url="https://example.gov.pl",
        criteria=Criteria(),
        status=status,
    ).model_dump(mode="json")


# ---------- dostęp ----------


@pytest.mark.parametrize("path", ["/api/benefits", "/api/benefits/nat-800-plus", "/api/analysis", "/api/summary"])
def test_benefits_endpoints_require_login(client, path):
    assert client.get(path).status_code == 401


def test_benefits_list_requires_parent(client):
    from conftest import login_official

    h = login_official(client, "urzednik.krakow@mrodzina.local")
    assert client.get("/api/benefits", headers=h).status_code == 403
    assert client.get("/api/analysis", headers=h).status_code == 403


def test_benefits_without_family_404(client):
    h = login(client, "persona-nowak-anna")
    assert client.get("/api/benefits", headers=h).status_code == 404


# ---------- lista ----------


def test_nowak_family_fits_expected_benefits(client):
    h = _setup_family(client)
    items = _by_id(client, h)
    assert items["nat-zasilek-macierzynski"]["match"]["status"] == "fits"
    assert items["nat-zasilek-chorobowy-ciaza"]["match"]["status"] == "fits"
    assert items["nat-800-plus"]["match"]["status"] == "fits"
    assert items["nat-kdr"]["match"]["status"] == "no"
    assert items["nat-becikowe"]["match"]["status"] == "no"
    assert "reasons" in items["nat-800-plus"]["match"] and items["nat-800-plus"]["match"]["reasons"]


def test_third_child_born_unlocks_kdr(client):
    h = _setup_family(client, third_born=True)
    items = _by_id(client, h)
    assert items["nat-kdr"]["match"]["status"] == "fits"
    assert items["nat-becikowe"]["match"]["status"] == "maybe"  # dochód nieznany -> pytanie, nie "nie"


def test_updating_child_status_recalculates_matching(client):
    h = _setup_family(client)
    assert _by_id(client, h)["nat-kdr"]["match"]["status"] == "no"
    kids = client.get("/api/families/me/children", headers=h).json()
    expected = next(c for c in kids if c["status"] == "expected")
    r = client.patch(
        f"/api/families/me/children/{expected['id']}",
        json={"birth_date": (date.today() - timedelta(days=1)).isoformat()},
        headers=h,
    )
    assert r.status_code == 200
    assert _by_id(client, h)["nat-kdr"]["match"]["status"] == "fits"


def test_get_single_benefit_and_unknown_404(client):
    h = _setup_family(client)
    r = client.get("/api/benefits/nat-800-plus", headers=h)
    assert r.status_code == 200 and r.json()["benefit"]["id"] == "nat-800-plus"
    assert client.get("/api/benefits/nie-ma", headers=h).status_code == 404


# ---------- odpowiedzi na pytania ----------


def test_answer_changes_maybe_to_fits(client):
    h = _setup_family(client)
    benefit_id = "nat-zasilek-rodzinny"
    item = _by_id(client, h)[benefit_id]
    assert item["match"]["status"] == "maybe"
    qid = item["match"]["questions"][0]["condition_id"]
    assert qid == "income"
    r = client.post(
        f"/api/benefits/{benefit_id}/answers", json={"condition_id": qid, "answer": True}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["match"]["status"] == "fits"
    assert _by_id(client, h)[benefit_id]["match"]["status"] == "fits"


def test_answer_no_changes_maybe_to_no(client):
    h = _setup_family(client)
    r = client.post(
        "/api/benefits/nat-zasilek-rodzinny/answers",
        json={"condition_id": "income", "answer": False},
        headers=h,
    )
    assert r.json()["match"]["status"] == "no"


def test_answer_is_saved_in_profile_so_it_is_not_asked_again(client):
    h = _setup_family(client)
    client.post(
        "/api/benefits/nat-dobry-start/answers", json={"condition_id": "szkola", "answer": True}, headers=h
    )
    answers = client.get("/api/profile/me", headers=h).json()["answers"]
    assert answers["benefit:nat-dobry-start:szkola"] is True
    assert _by_id(client, h)["nat-dobry-start"]["match"]["questions"] == []


def test_answer_unknown_condition_404(client):
    h = _setup_family(client)
    r = client.post(
        "/api/benefits/nat-800-plus/answers", json={"condition_id": "x", "answer": True}, headers=h
    )
    assert r.status_code == 404


def test_other_family_answers_not_shared(client):
    ha = _setup_family(client, "persona-nowak-anna")
    hp = _setup_family(client, "persona-nowak-piotr")  # osobna rodzina
    client.post(
        "/api/benefits/nat-zasilek-rodzinny/answers", json={"condition_id": "income", "answer": True}, headers=ha
    )
    assert _by_id(client, ha)["nat-zasilek-rodzinny"]["match"]["status"] == "fits"
    assert _by_id(client, hp)["nat-zasilek-rodzinny"]["match"]["status"] == "maybe"


def test_partner_sees_answer_after_joining_family(client):
    ha = _setup_family(client, "persona-nowak-anna")
    client.post(
        "/api/benefits/nat-zasilek-rodzinny/answers", json={"condition_id": "income", "answer": True}, headers=ha
    )
    hp = login(client, "persona-nowak-piotr")
    code = client.get("/api/families/me", headers=ha).json()["family"]["invite_code"]
    assert client.post("/api/families/join", json={"code": code}, headers=hp).status_code == 201
    req = client.get("/api/families/me/join-requests", headers=ha).json()[0]
    assert client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha).status_code == 200
    assert _by_id(client, hp)["nat-zasilek-rodzinny"]["match"]["status"] == "fits"


# ---------- zasięg lokalny ----------


def test_local_benefit_visible_only_in_area(client, store):
    asyncio.run(store.put("units", {"id": "unit-gdansk", "name": "Gmina Gdańsk", "level": "gmina",
                                    "gmina": "Gdańsk", "powiat": "Gdańsk", "voivodeship": "Pomorskie"}))
    asyncio.run(store.put("benefits", _municipal("loc-krakow", "unit-krakow")))
    asyncio.run(store.put("benefits", _municipal("loc-gdansk", "unit-gdansk")))
    asyncio.run(store.put("benefits", _municipal("woj-mal", "unit-malopolskie", scope="regional")))
    asyncio.run(store.put("benefits", _municipal("loc-draft", "unit-krakow", status="draft")))
    h = _setup_family(client)
    ids = set(_by_id(client, h))
    assert {"loc-krakow", "woj-mal"} <= ids
    assert "loc-gdansk" not in ids  # cudza gmina nigdy się nie pojawia
    assert "loc-draft" not in ids  # tylko opublikowane
    assert client.get("/api/benefits/loc-gdansk", headers=h).status_code == 404


# ---------- analiza i podsumowanie ----------


def test_analysis_counts_match_list(client):
    h = _setup_family(client)
    items = client.get("/api/benefits", headers=h).json()
    a = client.get("/api/analysis", headers=h).json()
    by_status = {s: sum(1 for x in items if x["match"]["status"] == s) for s in ("fits", "maybe", "no")}
    assert a["totals"]["fits"] == by_status["fits"]
    assert a["totals"]["maybe"] == by_status["maybe"]
    assert a["totals"]["no"] == by_status["no"]
    assert a["totals"]["national"] + a["totals"]["local"] == len(items)
    assert [s["key"] for s in a["steps"]] == ["profile", "family", "national", "local", "match"]
    assert all(s["status"] == "done" and s["label"] and s["detail"] for s in a["steps"])
    assert str(by_status["fits"]) in a["steps"][-1]["detail"]
    assert a["parameters_label"] == "Parametry ZUS 2026 – aktywne"


def test_analysis_estimate_and_nearest_deadline(client):
    h = _setup_family(client)
    a = client.get("/api/analysis", headers=h).json()
    items = _by_id(client, h)
    expected = sum(
        x["benefit"]["annual_value_estimate"] or 0
        for x in items.values()
        if x["match"]["status"] == "fits" and x["benefit"]["category"] == "benefit"
    )
    assert a["estimated_annual_total"] == expected > 0
    nd = a["nearest_deadline"]
    assert nd is not None and date.fromisoformat(nd["date"]) >= date.today()
    assert nd["benefit_id"] in items


def test_summary_matches_analysis_aggregates(client):
    h = _setup_family(client)
    a = client.get("/api/analysis", headers=h).json()
    s = client.get("/api/summary", headers=h).json()
    assert s["totals"] == a["totals"]
    assert s["estimated_annual_total"] == a["estimated_annual_total"]
    assert s["nearest_deadline"] == a["nearest_deadline"]
    assert s["parameters_label"] == "Parametry ZUS 2026 – aktywne"
    assert "steps" not in s


# ---------- narzędzie MCP ----------


@pytest.fixture
def isolated_registry(monkeypatch):
    monkeypatch.setattr(reg, "_REGISTRY", {})
    sys.modules.pop("app.tools.benefits", None)
    importlib.import_module("app.tools.benefits")  # rejestruje `swiadczenia` w pustym rejestrze


async def test_tool_swiadczenia_returns_matches(client, store, isolated_registry):
    _setup_family(client)
    user_id = "user-nowak-anna"
    ctx = ToolContext(principal=Principal(user_id, "parent"), store=store, today=date.today())
    result = await call_tool("swiadczenia", {}, ctx)
    ids = {r["id"] for r in result}
    assert "nat-800-plus" in ids
    only_fits = await call_tool("swiadczenia", {"status": "fits"}, ctx)
    assert only_fits and all(r["status"] == "fits" for r in only_fits)
    assert {"id", "name", "status", "reasons", "amount", "source_url"} <= set(only_fits[0])


async def test_tool_swiadczenia_validates_status_and_family(client, store, isolated_registry):
    ctx = ToolContext(principal=Principal("user-nowak-anna", "parent"), store=store, today=date.today())
    with pytest.raises(ToolError):
        await call_tool("swiadczenia", {"status": "bogaty"}, ctx)
    login(client, "persona-nowak-anna")  # użytkownik istnieje, ale bez rodziny
    with pytest.raises(ToolError):
        await call_tool("swiadczenia", {}, ctx)
