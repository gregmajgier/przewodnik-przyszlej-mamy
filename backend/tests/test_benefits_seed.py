import json
from datetime import date, timedelta

from app.models.benefit import Benefit
from app.models.family import Child, Family, FamilyView
from app.seed.benefits import DATA_FILE, load_loss_benefits, load_national_benefits
from app.services.matching import build_context, match_benefit
from app.services.zus_sim import fetch_zus_data

CATALOG = json.loads(
    (DATA_FILE.parent / "katalog_wnioskow_pdf.json").read_text(encoding="utf-8")
)
FORM_CODES = {w["kod"] for w in CATALOG["wnioski"]}


def test_at_least_16_national_benefits():
    assert len(load_national_benefits()) >= 16


def test_every_record_validates_and_has_https_source():
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))["benefits"]
    for b in raw:
        Benefit.model_validate(b)
        assert b["source_url"].startswith("https://"), b["id"]


def test_ids_are_unique():
    ids = [b.id for b in load_national_benefits()]
    assert len(ids) == len(set(ids))


def test_form_codes_exist_in_catalog():
    for b in load_national_benefits():
        for code in b.form_codes:
            assert code in FORM_CODES, f"{b.id}: nieznany kod wniosku {code}"


def test_all_national_and_published():
    for b in load_national_benefits():
        assert b.scope == "national" and b.unit_id is None
        assert b.status == "published"


def test_required_positions_present():
    ids = {b.id for b in load_national_benefits()}
    for needed in (
        "nat-zasilek-macierzynski",
        "nat-800-plus",
        "nat-becikowe",
        "nat-za-zyciem",
        "nat-kdr",
        "nat-dobry-start",
        "nat-aktywny-rodzic-w-pracy",
        "nat-aktywny-rodzic-w-zlobku",
        "nat-aktywny-rodzic-w-domu",
        "nat-zasilek-chorobowy-ciaza",
        "nat-zasilek-rodzinny",
    ):
        assert needed in ids


def test_seed_is_idempotent(store):
    import asyncio

    from app.seed import seed_all

    asyncio.run(seed_all(store))
    docs = asyncio.run(store.find("benefits", scope="national"))
    assert len(docs) == len(load_national_benefits()) + len(load_loss_benefits())  # + wsparcie po stracie (plan 10)


TODAY = date(2026, 11, 21)


def _nowak_view(third_born: bool = False):
    """Nowakowie: Maja (7 l.), Antek (3 l. i 4 mies.) i trzecie dziecko — w drodze albo już urodzone."""
    third = (
        Child(id="c3", family_id="f", name="Hania", birth_date=TODAY - timedelta(days=20))
        if third_born
        else Child(id="c3", family_id="f", name="Dziecko w drodze", due_date=TODAY + timedelta(days=60))
    )
    children = [
        Child(id="c1", family_id="f", name="Maja", birth_date=TODAY - timedelta(days=7 * 365 + 90)),
        Child(id="c2", family_id="f", name="Antek", birth_date=TODAY - timedelta(days=3 * 365 + 120)),
        third,
    ]
    view = FamilyView(
        family=Family(id="f", name="Rodzina Nowak", owner_id="u", member_ids=["u"]),
        members=[],
        children=children,
    )
    anna = fetch_zus_data("persona-nowak-anna", TODAY)
    units = [
        {"id": "unit-krakow", "level": "gmina", "gmina": "Kraków", "powiat": "Kraków", "voivodeship": "Małopolskie"},
        {"id": "unit-malopolskie", "level": "voivodeship", "voivodeship": "Małopolskie"},
    ]
    return build_context(view, [anna], TODAY, units, viewer_id=anna.user_id)


def _statuses(ctx) -> dict[str, str]:
    return {b.id: match_benefit(ctx, b).status for b in load_national_benefits()}


def test_nowak_family_fits_expected_benefits():
    s = _statuses(_nowak_view())
    assert s["nat-zasilek-macierzynski"] == "fits"
    assert s["nat-zasilek-chorobowy-ciaza"] == "fits"  # e-ZLA B z danych ZUS
    assert s["nat-800-plus"] == "fits"
    assert s["nat-opieka-okolooporodowa"] == "fits"
    assert s["nat-badania-prenatalne"] == "fits"
    assert s["nat-becikowe"] == "no"  # dziecko w drodze: dopiero po urodzeniu
    assert s["nat-kdr"] == "no"  # trzecie dziecko jeszcze się nie urodziło
    assert s["nat-za-zyciem"] == "no"
    assert s["nat-zasilek-pielegnacyjny"] == "no"


def test_nowak_family_maybe_benefits_need_answers():
    ctx = _nowak_view()
    for bid in ("nat-zasilek-rodzinny", "nat-dobry-start", "nat-ulga-prorodzinna"):
        benefit = next(b for b in load_national_benefits() if b.id == bid)
        r = match_benefit(ctx, benefit)
        assert r.status == "maybe" and r.questions, bid


def test_kdr_appears_after_third_child_is_born():
    assert _statuses(_nowak_view(third_born=False))["nat-kdr"] == "no"
    assert _statuses(_nowak_view(third_born=True))["nat-kdr"] == "fits"
    assert _statuses(_nowak_view(third_born=True))["nat-800-plus"] == "fits"


def test_estimated_values_are_positive_when_present():
    for b in load_national_benefits():
        if b.annual_value_estimate is not None:
            assert b.annual_value_estimate > 0, b.id


def test_maternity_leave_and_allowance_are_one_entry_not_a_duplicate():
    from app.seed.benefits import load_national_benefits

    names = [b.name for b in load_national_benefits()]
    assert len(names) == len(set(names))
    assert not any(n == "Urlop macierzyński" for n in names)  # scalone z zasiłkiem
    merged = next(b for b in load_national_benefits() if b.id == "nat-zasilek-macierzynski")
    assert merged.name == "Urlop i zasiłek macierzyński" and set(merged.form_codes) == {"URLOP-MAC-ROD", "ZAM"}


def test_seed_removes_obsolete_benefits_from_existing_databases():
    import asyncio

    from app.seed import seed_all
    from app.storage import MemoryStore

    store = MemoryStore()
    asyncio.run(store.put("benefits", {"id": "nat-urlop-macierzynski", "name": "Urlop macierzyński", "status": "published"}))
    asyncio.run(seed_all(store))
    assert asyncio.run(store.get("benefits", "nat-urlop-macierzynski")) is None
    assert asyncio.run(store.get("benefits", "nat-zasilek-macierzynski")) is not None
