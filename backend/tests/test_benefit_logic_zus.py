"""Logika dopasowania świadczeń zgodna z materiałami ZUS (na prawdziwych wpisach katalogu)."""

import json
from datetime import date, timedelta
from pathlib import Path

from app.models.benefit import Benefit
from app.services.matching import match_benefit
from app.services.payout import payouts_for
from test_matching import TODAY, born_months_ago, child, ctx, parent

DATA = Path(__file__).resolve().parents[1] / "app" / "data"


def entry(benefit_id: str) -> Benefit:
    for name in ("benefits_national.json", "benefits_loss.json"):
        raw = json.loads((DATA / name).read_text(encoding="utf-8"))
        items = raw["benefits"] if isinstance(raw, dict) else raw
        for b in items:
            if b["id"] == benefit_id:
                return Benefit.model_validate(b)
    raise KeyError(benefit_id)


def born_days_ago(days: int, name="Hania") -> object:
    return child(name, birth=TODAY - timedelta(days=days))


def expecting():
    return child("Maleństwo", due=TODAY + timedelta(days=60), status="expected")


# ---------- urlop rodzicielski: do końca roku, w którym dziecko kończy 6 lat ----------


def test_parental_leave_fits_for_3_year_old_without_pregnancy():
    result = match_benefit(ctx([born_months_ago(40, "Antek")]), entry("nat-urlop-rodzicielski"))
    assert result.status == "fits"
    assert any("Antek" in r and "do końca" in r for r in result.reasons)


def test_parental_leave_ends_with_the_year_child_turns_6():
    maja = child("Maja", birth=date(2019, 8, 26))  # 6 lat w 2025 -> w listopadzie 2026 po terminie
    assert match_benefit(ctx([maja]), entry("nat-urlop-rodzicielski")).status == "no"
    six_this_year = child("Ola", birth=date(2020, 12, 1))  # 6 lat w 2026 -> do 31.12.2026
    assert match_benefit(ctx([six_this_year]), entry("nat-urlop-rodzicielski")).status == "fits"


def test_parental_leave_fits_in_pregnancy_and_for_insured_non_employees():
    family = ctx([expecting()], parents=[parent(kinds=("mandate",))])
    assert match_benefit(family, entry("nat-urlop-rodzicielski")).status == "fits"


# ---------- zasiłek macierzyński: tylko w ciąży albo w trakcie urlopu macierzyńskiego ----------


def test_maternity_fits_during_20_weeks_after_birth():
    assert match_benefit(ctx([born_days_ago(19 * 7)]), entry("nat-zasilek-macierzynski")).status == "fits"


def test_maternity_ends_after_20_weeks_for_one_child():
    result = match_benefit(ctx([born_days_ago(21 * 7)]), entry("nat-zasilek-macierzynski"))
    assert result.status == "no"
    assert any("20 tygodni" in u for u in result.unmet)


def test_twins_extend_maternity_leave_to_31_weeks():
    birth = TODAY - timedelta(days=25 * 7)
    twins = [child("Ala", birth=birth), child("Ola", birth=birth)]
    assert match_benefit(ctx(twins), entry("nat-zasilek-macierzynski")).status == "fits"


# ---------- Aktywny rodzic: aktywnie w pracy wymaga pracy obojga ----------

ACTIVE = "benefit:nat-aktywny-rodzic-w-pracy:opiekun"


def test_active_at_work_asks_about_second_parent_when_only_one_in_app():
    result = match_benefit(ctx([born_months_ago(20)], answers={ACTIVE: True}), entry("nat-aktywny-rodzic-w-pracy"))
    assert result.status == "maybe"
    assert [q.condition_id for q in result.questions] == ["oboje-pracuja"]


def test_active_at_work_fits_when_both_parents_work():
    parents = [parent("u1", ("employment",)), parent("u2", ("mandate",))]
    family = ctx([born_months_ago(20)], parents=parents, answers={ACTIVE: True})
    assert match_benefit(family, entry("nat-aktywny-rodzic-w-pracy")).status == "fits"


def test_active_at_work_not_when_second_parent_does_not_work():
    parents = [parent("u1", ("employment",)), parent("u2", ())]
    result = match_benefit(ctx([born_months_ago(20)], parents=parents, answers={ACTIVE: True}), entry("nat-aktywny-rodzic-w-pracy"))
    assert result.status == "no"
    assert any("oboje rodzice" in u for u in result.unmet)


# ---------- brakujące dotąd świadczenia ZUS ----------


def test_rehabilitation_benefit_shown_in_pregnancy_with_question():
    result = match_benefit(ctx([expecting()]), entry("nat-swiadczenie-rehabilitacyjne"))
    assert result.status == "maybe"
    assert "270 dni" in result.questions[0].text


def test_benefit_after_job_loss_in_pregnancy_asks_about_liquidation():
    result = match_benefit(ctx([expecting()], parents=[parent(kinds=())]), entry("nat-zasilek-w-wysokosci-macierzynskiego"))
    assert result.status == "maybe"
    assert "likwidacji" in result.questions[0].text


def test_adoption_leave_for_foster_child_with_leave_form_for_employee():
    family = ctx([born_months_ago(5 * 12, "Kuba", foster=True)])
    b = entry("nat-urlop-przyjecie-dziecka")
    assert match_benefit(family, b).status == "fits"
    assert [p.form_code for p in payouts_for(b, family.parents)] == ["URLOP-MAC-PRZYJECIE"]


def test_adoption_leave_not_without_foster_child():
    assert match_benefit(ctx([born_months_ago(24)]), entry("nat-urlop-przyjecie-dziecka")).status == "no"


def test_care_allowance_for_children_under_14():
    assert match_benefit(ctx([born_months_ago(7 * 12)]), entry("nat-zasilek-opiekunczy")).status == "fits"
    assert match_benefit(ctx([born_months_ago(14 * 12)]), entry("nat-zasilek-opiekunczy")).status == "no"


def test_care_allowance_has_no_waiting_period_text():
    b = entry("nat-zasilek-opiekunczy")
    assert "90 dni" not in (b.extra_text or "")


# ---------- po stracie ----------


def test_loss_leave_mentions_7_days_after_death_of_a_child():
    text = entry("loss-skrocony-urlop-macierzynski").description
    assert "7 dni od dnia śmierci" in text and "8 tygodni" in text
    assert "!" not in text  # tryb jaskółki: spokojnie, bez wykrzykników


def test_loss_maternity_allowance_resolved_from_zus_data():
    b = entry("loss-zasilek-macierzynski")
    assert match_benefit(ctx([], parents=[parent(kinds=("employment",))]), b).status == "fits"
    result = match_benefit(ctx([], parents=[parent(kinds=())]), b)
    assert result.status == "no"
    assert "!" not in " ".join(result.unmet)
