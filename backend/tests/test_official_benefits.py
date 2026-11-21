import asyncio

import pytest
from fastapi.testclient import TestClient

from app.ai.llm import FakeLLM, LLMError, get_llm
from app.config import settings
from app.main import create_app
from app.mocks.benefit_catalog import visible_benefits  # MOCK planu 03
from app.models.profile import Address
from app.services.conditions import ConditionList, RawCondition, ResolutionExtract
from conftest import login, login_official

KRAKOW = "urzednik.krakow@mrodzina.local"
MALOPOLSKA = "urzednik.malopolska@mrodzina.local"

KRAKOW_ADDR = Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001")
TARNOW_ADDR = Address(city="Tarnów", gmina="Tarnów", powiat="Tarnów", voivodeship="Małopolskie", postal_code="33-100")
GDANSK_ADDR = Address(city="Gdańsk", gmina="Gdańsk", powiat="Gdańsk", voivodeship="Pomorskie", postal_code="80-001")


def body(**kw):
    base = {"name": "Dopłata do żłobka", "description": "Dopłata dla rodziców.", "amount_text": "500 zł / mies."}
    return {**base, **kw}


@pytest.fixture
def env(store):
    app = create_app(store)
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    with TestClient(app) as c:
        yield c, fake, store


def create(c, h, **kw):
    r = c.post("/api/official/benefits", json=body(**kw), headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_me_returns_unit(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    r = c.get("/api/official/me", headers=h).json()
    assert r["unit"]["id"] == "unit-krakow"
    assert "password_hash" not in r["user"]


def test_scope_and_unit_set_from_official(env):
    c, _, _ = env
    krakow = create(c, login_official(c, KRAKOW))
    assert (krakow["scope"], krakow["unit_id"], krakow["status"]) == ("municipal", "unit-krakow", "draft")
    region = create(c, login_official(c, MALOPOLSKA))
    assert (region["scope"], region["unit_id"]) == ("regional", "unit-malopolskie")


def test_scope_cannot_be_forced_by_client(env):
    c, _, _ = env
    b = create(c, login_official(c, KRAKOW), scope="national", unit_id="unit-malopolskie", status="published")
    assert (b["scope"], b["unit_id"], b["status"]) == ("municipal", "unit-krakow", "draft")


def test_other_unit_cannot_read_edit_publish(env):
    c, _, _ = env
    b = create(c, login_official(c, KRAKOW))
    other = login_official(c, MALOPOLSKA)
    assert c.get(f"/api/official/benefits/{b['id']}", headers=other).status_code == 404
    assert c.put(f"/api/official/benefits/{b['id']}", json=body(name="X"), headers=other).status_code == 404
    assert c.post(f"/api/official/benefits/{b['id']}/publish", headers=other).status_code == 404
    assert c.delete(f"/api/official/benefits/{b['id']}", headers=other).status_code == 404
    assert b["id"] not in {x["id"] for x in c.get("/api/official/benefits", headers=other).json()}


def test_parent_token_forbidden(env):
    c, _, _ = env
    h = login(c, "persona-nowak-anna")
    assert c.get("/api/official/benefits", headers=h).status_code == 403
    assert c.post("/api/official/benefits", json=body(), headers=h).status_code == 403
    assert c.get("/api/official/me", headers=h).status_code == 403


def test_publish_without_approved_conditions_409(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h, extra_text="Zameldowanie w gminie od 12 miesięcy.")
    r = c.post(f"/api/official/benefits/{b['id']}/publish", headers=h)
    assert r.status_code == 409


def test_publish_without_extra_text_ok(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h)
    assert c.post(f"/api/official/benefits/{b['id']}/publish", headers=h).json()["status"] == "published"


def test_extract_then_approve_then_publish(env):
    c, fake, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h, extra_text="Zameldowanie 12 mies. Dziecko w żłobku publicznym.")
    fake.script(
        ConditionList(
            conditions=[
                RawCondition(text="Zameldowanie w gminie 12 mies.", kind="auto", profile_key="nieznany"),
                RawCondition(text="Zameldowanie w gminie 12 mies.", kind="ask"),
                RawCondition(text="Dziecko w żłobku publicznym", kind="auto", profile_key="child_in_public_nursery"),
            ]
        )
    )
    r = c.post(f"/api/official/benefits/{b['id']}/extract-conditions", headers=h)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "awaiting_approval" and b["conditions_approved"] is False
    assert [x["kind"] for x in b["extra_conditions"]] == ["ask", "auto"]
    assert c.post(f"/api/official/benefits/{b['id']}/publish", headers=h).status_code == 409
    # urzędnik usuwa jeden warunek i poprawia drugi
    edited = [{**b["extra_conditions"][0], "text": "Zameldowanie w Krakowie od 12 miesięcy"}]
    r = c.post(f"/api/official/benefits/{b['id']}/approve-conditions", json={"conditions": edited}, headers=h)
    assert r.json()["conditions_approved"] is True
    assert [x["text"] for x in r.json()["extra_conditions"]] == ["Zameldowanie w Krakowie od 12 miesięcy"]
    assert c.post(f"/api/official/benefits/{b['id']}/publish", headers=h).json()["status"] == "published"


def test_extract_llm_error_message(env):
    c, fake, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h, extra_text="Coś.")
    fake.script(LLMError("x"), LLMError("x"))
    r = c.post(f"/api/official/benefits/{b['id']}/extract-conditions", headers=h)
    assert r.status_code == 502
    assert r.json()["detail"] == "Nie udało się wyodrębnić warunków — dodaj je ręcznie."
    assert c.get(f"/api/official/benefits/{b['id']}", headers=h).json()["extra_conditions"] == []


def test_extract_requires_extra_text_422(env):
    c, fake, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h)
    assert c.post(f"/api/official/benefits/{b['id']}/extract-conditions", headers=h).status_code == 422
    assert fake.calls == []


def test_edit_published_goes_back_to_draft(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h)
    c.post(f"/api/official/benefits/{b['id']}/publish", headers=h)
    r = c.put(f"/api/official/benefits/{b['id']}", json=body(amount_text="600 zł"), headers=h)
    assert r.json()["status"] == "draft"


def test_changing_extra_text_resets_approval(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    b = create(c, h, extra_text="A.")
    c.post(f"/api/official/benefits/{b['id']}/approve-conditions",
           json={"conditions": [{"id": "a", "text": "A", "kind": "ask"}]}, headers=h)
    r = c.put(f"/api/official/benefits/{b['id']}", json=body(extra_text="B."), headers=h).json()
    assert r["conditions_approved"] is False and r["extra_conditions"] == []
    same = c.put(f"/api/official/benefits/{b['id']}", json=body(extra_text="B."), headers=h).json()
    assert same["status"] == "draft"


def test_publish_makes_benefit_visible_to_residents_only(env):
    c, _, store = env
    asyncio.run(store.put("units", {"id": "unit-gdansk", "name": "Gdańsk", "level": "gmina", "gmina": "Gdańsk",
                                    "powiat": "Gdańsk", "voivodeship": "Pomorskie"}))
    asyncio.run(store.put("benefits", {"id": "gdansk-1", "name": "Bon Gdańsk", "scope": "municipal",
                                       "unit_id": "unit-gdansk", "description": "x", "status": "published"}))
    h = login_official(c, KRAKOW)
    b = create(c, h)
    names = lambda addr: {x.id for x in asyncio.run(visible_benefits(store, addr))}  # noqa: E731
    assert b["id"] not in names(KRAKOW_ADDR)  # szkic niewidoczny
    c.post(f"/api/official/benefits/{b['id']}/publish", headers=h)
    assert b["id"] in names(KRAKOW_ADDR)
    assert "gdansk-1" not in names(KRAKOW_ADDR)
    assert b["id"] not in names(TARNOW_ADDR)
    assert b["id"] not in names(GDANSK_ADDR)
    # rodzina Nowaków (adres z profilu ZUS) widzi świadczenie Krakowa
    login(c, "persona-nowak-anna")
    prof = asyncio.run(store.get("profiles", "user-nowak-anna"))
    assert b["id"] in names(Address.model_validate(prof["address"]))


def test_voivodeship_benefit_visible_to_krakow_family(env):
    c, _, store = env
    h = login_official(c, MALOPOLSKA)
    b = create(c, h)
    c.post(f"/api/official/benefits/{b['id']}/publish", headers=h)
    ids = lambda addr: {x.id for x in asyncio.run(visible_benefits(store, addr))}  # noqa: E731
    assert b["id"] in ids(KRAKOW_ADDR) and b["id"] in ids(TARNOW_ADDR)
    assert b["id"] not in ids(GDANSK_ADDR)


def test_unpublish(env):
    c, _, store = env
    h = login_official(c, KRAKOW)
    b = create(c, h)
    c.post(f"/api/official/benefits/{b['id']}/publish", headers=h)
    assert c.post(f"/api/official/benefits/{b['id']}/unpublish", headers=h).json()["status"] == "draft"
    assert b["id"] not in {x.id for x in asyncio.run(visible_benefits(store, KRAKOW_ADDR))}


def test_invalid_age_range_422(env):
    c, _, _ = env
    h = login_official(c, KRAKOW)
    r = c.post("/api/official/benefits",
               json=body(criteria={"child_age_min_months": 36, "child_age_max_months": 12}), headers=h)
    assert r.status_code == 422


def test_prefill_from_text(env):
    c, fake, _ = env
    h = login_official(c, KRAKOW)
    fake.script(ResolutionExtract(name="Bon", child_age_max_months=35, max_income_per_person=2000))
    r = c.post("/api/official/prefill-from-text", json={"text": "Uchwała..."}, headers=h)
    assert r.status_code == 200
    assert r.json()["criteria"]["child_age_max_months"] == 35


def test_ai_endpoints_rate_limited(env, monkeypatch):
    c, fake, _ = env
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    h = login_official(c, KRAKOW)
    fake.script(ResolutionExtract(name="Bon"))
    assert c.post("/api/official/prefill-from-text", json={"text": "U"}, headers=h).status_code == 200
    r = c.post("/api/official/prefill-from-text", json={"text": "U"}, headers=h)
    assert r.status_code == 429
    b = create(c, h, extra_text="A.")
    assert c.post(f"/api/official/benefits/{b['id']}/extract-conditions", headers=h).status_code == 429
