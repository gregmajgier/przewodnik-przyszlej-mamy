import asyncio
import json
from datetime import date
from pathlib import Path

from conftest import login

from app.models.benefit import Benefit
from app.models.profile import ParentProfile
from app.seed.benefits import load_national_benefits
from app.services.families import FamilyService
from app.services.matching import build_context, match_benefit

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
ANNA = "persona-nowak-anna"


def _form_codes() -> set[str]:
    catalog = json.loads((DATA / "katalog_wnioskow_pdf.json").read_text(encoding="utf-8"))
    return {w["kod"] for w in catalog["wnioski"]}


def test_at_least_16_benefits_all_valid():
    benefits = load_national_benefits()
    assert len(benefits) >= 16
    assert all(isinstance(b, Benefit) for b in benefits)


def test_ids_unique_and_sources_https():
    benefits = load_national_benefits()
    assert len({b.id for b in benefits}) == len(benefits)
    for b in benefits:
        assert b.source_url.startswith("https://"), b.id
        assert b.scope == "national" and b.unit_id is None, b.id
        assert b.status == "published", b.id


def test_form_codes_exist_in_catalog():
    codes = _form_codes()
    for b in load_national_benefits():
        assert set(b.form_codes) <= codes, (b.id, set(b.form_codes) - codes)


def test_every_benefit_has_polish_text_and_how_to_apply():
    for b in load_national_benefits():
        assert b.name and b.description and b.how_to_apply, b.id


def test_required_topics_are_covered():
    text = " ".join(b.name.lower() for b in load_national_benefits())
    for topic in [
        "zasiłek macierzyński", "urlop macierzyński", "urlop rodzicielski", "urlop ojcowski", "ciąży",
        "800+", "aktywnie w pracy", "aktywnie w żłobku", "aktywnie w domu", "becikowe", "za życiem",
        "zasiłek rodzinny", "dobry start", "karta dużej rodziny", "ulga", "leki", "pielęgnacyjne",
        "zastępczych", "prenatalne",
    ]:
        assert topic in text, topic


def test_seed_all_stores_benefits_idempotently(store):
    from app.seed import seed_all

    first = asyncio.run(store.find("benefits"))
    asyncio.run(seed_all(store))
    second = asyncio.run(store.find("benefits"))
    assert len(first) == len(second) >= 16


def _nowak_context(client, store, today=None):
    h = login(client, ANNA)
    client.post("/api/families", json={}, headers=h)
    profile = client.get("/api/profile/me", headers=h).json()
    for k in profile["known_children"]:
        client.post("/api/families/me/children", json=k, headers=h)
    svc = FamilyService(store)
    view = asyncio.run(svc.get_family_view("user-nowak-anna"))
    prof = ParentProfile.model_validate(profile)
    units = asyncio.run(store.find("units"))
    ctx = build_context(view, [prof], today or date.today(), units=units, viewer_id="user-nowak-anna")
    return h, view, ctx


def _statuses(ctx):
    return {b.id: match_benefit(ctx, b).status for b in load_national_benefits()}


def test_nowak_family_fits_expected_benefits(client, store):
    _, _, ctx = _nowak_context(client, store)
    st = _statuses(ctx)
    # ciąża + etat + ubezpieczenie chorobowe
    assert st["nat-zasilek-macierzynski"] == "fits"
    assert st["nat-zasilek-chorobowy-ciaza"] == "fits"
    assert st["nat-leki-ciaza"] == "fits"
    assert st["nat-urlop-macierzynski"] == "fits"
    # dzieci 7 i ~3 lata
    assert st["nat-800plus"] == "fits"
    assert st["nat-ulga-prorodzinna"] == "fits"
    # wymagają dopytania
    assert st["nat-zasilek-rodzinny"] == "maybe"
    assert st["nat-dobry-start"] == "maybe"
    assert st["nat-badania-prenatalne"] == "maybe"
    # KDR dopiero po urodzeniu trzeciego dziecka
    assert st["nat-kdr"] == "no"
    # Za życiem tylko przy ciężkiej chorobie dziecka
    assert st["nat-za-zyciem"] == "no"


def test_nowak_third_child_born_unlocks_kdr_and_newborn_benefits(client, store):
    h, view, _ = _nowak_context(client, store)
    expected = next(c for c in view.children if c.status == "expected")
    r = client.patch(
        f"/api/families/me/children/{expected.id}",
        json={"status": "born", "birth_date": date.today().isoformat()},
        headers=h,
    )
    assert r.status_code == 200, r.text
    _, _, ctx = _nowak_context_after(client, store, h)
    st = _statuses(ctx)
    assert st["nat-kdr"] == "fits"
    assert st["nat-becikowe"] == "maybe"
    assert st["nat-urlop-ojcowski"] == "fits"
    assert st["nat-leki-ciaza"] == "no"


def _nowak_context_after(client, store, h):
    profile = client.get("/api/profile/me", headers=h).json()
    view = asyncio.run(FamilyService(store).get_family_view("user-nowak-anna"))
    units = asyncio.run(store.find("units"))
    ctx = build_context(
        view, [ParentProfile.model_validate(profile)], date.today(), units=units, viewer_id="user-nowak-anna"
    )
    return h, view, ctx
