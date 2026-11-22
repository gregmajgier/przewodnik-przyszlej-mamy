"""Kto wypłaci zasiłek i gdzie złożyć dokumenty (art. 61 ustawy zasiłkowej, wymaganie g zadania ZUS)."""

from datetime import date

import pytest
from test_benefits_api import _by_id, _setup_family

from app.models.benefit import Benefit, Criteria
from app.models.profile import Address, Insurance, ParentProfile
from app.services.payout import PAYOUT_TAG, describe, payer_threshold, payouts_for

KRAKOW = Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001")
MUM_PESEL = "90010112342"  # przedostatnia cyfra parzysta = kobieta
DAD_PESEL = "88050512351"  # nieparzysta = mężczyzna


def ins(kind="employment", count=None, voluntary=None, payer="Firma Sp. z o.o.") -> Insurance:
    return Insurance(
        kind=kind,
        payer=payer,
        contribution_base=5000,
        since=date(2020, 1, 1),
        voluntary_sickness=voluntary,
        payer_insured_count=count,
    )


def parent(name="Anna", pesel=MUM_PESEL, insurance=()) -> ParentProfile:
    return ParentProfile(
        user_id=f"u-{name}",
        first_name=name,
        last_name="Nowak",
        pesel=pesel,
        birth_date=date(1990, 1, 1),
        address=KRAKOW,
        insurance=list(insurance),
    )


def benefit(tags=(PAYOUT_TAG,), kinds=None, pregnancy=None, forms=()) -> Benefit:
    return Benefit(
        id="b",
        name="Zasiłek",
        scope="national",
        category="benefit",
        description="opis",
        how_to_apply="jak",
        source_url="https://www.zus.pl",
        criteria=Criteria(employment_kinds=kinds, requires_pregnancy=pregnancy),
        tags=list(tags),
        form_codes=list(forms),
    )


def test_threshold_comes_from_engine_parameters():
    assert payer_threshold() == 20


@pytest.mark.parametrize(
    ("count", "paid_by", "headline"),
    [
        (21, "payer", "Zasiłek wypłaci pracodawca"),
        (20, "zus", "Zasiłek wypłaci ZUS"),  # „powyżej 20”: dokładnie 20 to jeszcze ZUS
        (3, "zus", "Zasiłek wypłaci ZUS"),
        (None, "unknown", "Zasiłek wypłaci pracodawca albo ZUS"),
    ],
)
def test_employee_payer_depends_on_insured_count(count, paid_by, headline):
    got, head, _why, _where = describe(ins(count=count), sickness=False, threshold=20)
    assert (got, head) == (paid_by, headline)


def test_small_employer_sends_z3_to_zus():
    _, _, why, where = describe(ins(count=5, payer="Piekarnia"), sickness=False, threshold=20)
    assert "Piekarnia" in why and "najwyżej 20" in why
    assert "Z-3" in where and "kadrach" in where


def test_mandate_with_small_payer_goes_to_zus_with_z3a():
    paid_by, _, _, where = describe(ins("mandate", count=4, voluntary=True), sickness=True, threshold=20)
    assert paid_by == "zus"
    assert "Z-3a" in where


def test_mandate_without_voluntary_sickness_has_no_benefit():
    paid_by, headline, _, _ = describe(ins("mandate", count=100, voluntary=False), sickness=False, threshold=20)
    assert paid_by == "none"
    assert "nie przysługuje" in headline


def test_business_owner_is_always_paid_by_zus():
    paid_by, _, why, where = describe(ins("jdg", count=500, voluntary=True), sickness=True, threshold=20)
    assert paid_by == "zus"
    assert "zawsze" in why
    assert "ZAS-53" in where


def test_benefit_without_tag_has_no_payout_lines():
    assert payouts_for(benefit(tags=()), [parent(insurance=[ins(count=50)])]) == []


def test_one_line_per_matching_insurance_title():
    p = parent(insurance=[ins(count=240, payer="Duża"), ins("mandate", count=6, voluntary=True, payer="Mała")])
    lines = payouts_for(benefit(), [p])
    assert [(x.payer, x.paid_by) for x in lines] == [("Duża", "payer"), ("Mała", "zus")]
    assert lines[0].title == "umowa o pracę" and lines[0].parent_name == "Anna"


def test_employment_kinds_of_benefit_filter_titles():
    p = parent(insurance=[ins(count=240), ins("mandate", count=6, voluntary=True)])
    lines = payouts_for(benefit(kinds=["employment"]), [p])
    assert [x.title for x in lines] == ["umowa o pracę"]


def test_paternity_leave_concerns_only_the_father():
    mum = parent("Anna", MUM_PESEL, [ins(count=240)])
    dad = parent("Piotr", DAD_PESEL, [ins(count=18)])
    lines = payouts_for(benefit(tags=(PAYOUT_TAG, "tata")), [mum, dad])
    assert [x.parent_name for x in lines] == ["Piotr"]


def test_pregnancy_sickness_concerns_only_the_mother():
    mum = parent("Anna", MUM_PESEL, [ins(count=240)])
    dad = parent("Piotr", DAD_PESEL, [ins(count=18)])
    lines = payouts_for(benefit(tags=(PAYOUT_TAG, "ezla"), pregnancy=True), [mum, dad])
    assert [x.parent_name for x in lines] == ["Anna"]
    assert "e-ZLA" in lines[0].where


def test_pregnancy_sick_leave_needs_a_form_only_for_business_owners():
    sick = benefit(tags=(PAYOUT_TAG, "ezla"), pregnancy=True, forms=("ZAS-53",))
    employee = parent(insurance=[ins(count=240), ins("mandate", count=3, voluntary=True)])
    owner = parent(insurance=[ins("jdg", voluntary=True)])
    assert [x.form_code for x in payouts_for(sick, [employee])] == [None, None]  # e-ZLA wystarczy
    assert [x.form_code for x in payouts_for(sick, [owner])] == ["ZAS-53"]


def test_leave_forms_depend_on_insurance_title():
    maternity = benefit(forms=("URLOP-MAC-ROD", "ZAM"))
    p = parent(
        insurance=[ins(count=240), ins("mandate", count=3, voluntary=True), ins("mandate", voluntary=False, payer="Bez")]
    )
    assert [x.form_code for x in payouts_for(maternity, [p])] == ["URLOP-MAC-ROD", "ZAM", None]


def test_payout_lines_never_contain_pesel_or_amounts():
    p = parent(insurance=[ins(count=240)])
    dumped = str([x.model_dump() for x in payouts_for(benefit(), [p])])
    assert MUM_PESEL not in dumped
    assert "5000" not in dumped


def test_zus_simulation_knows_payer_size_of_both_personas():
    from app.services.zus_sim import fetch_zus_data

    anna = fetch_zus_data("persona-nowak-anna", date(2026, 11, 22)).insurance[0]
    piotr = fetch_zus_data("persona-nowak-piotr", date(2026, 11, 22)).insurance[0]
    assert anna.payer_insured_count > 20  # demo: pracodawca wypłaca sam
    assert piotr.payer_insured_count <= 20  # demo: wypłaca ZUS


# ---------- API: Anna (pracodawca > 20 osób) ----------


def test_api_tells_anna_her_employer_pays_maternity(client):
    h = _setup_family(client)
    item = _by_id(client, h)["nat-zasilek-macierzynski"]
    assert item["match"]["status"] == "fits"
    (line,) = item["payouts"]
    assert line["paid_by"] == "payer"
    assert line["payer"] == "Krakowskie Centrum Usług Wspólnych Sp. z o.o."
    assert line["headline"] == "Zasiłek wypłaci pracodawca"


def test_api_has_no_payout_lines_for_800_plus(client):
    h = _setup_family(client)
    assert _by_id(client, h)["nat-800-plus"]["payouts"] == []
