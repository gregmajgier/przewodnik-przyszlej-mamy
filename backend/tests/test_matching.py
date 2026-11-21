from datetime import date

import pytest

from app.models.benefit import Benefit, Condition, Criteria, Deadline
from app.models.family import Child, Family, FamilyView
from app.models.profile import Address, Ezla, Insurance, ParentProfile
from app.models.user import User
from app.services.matching import (
    FamilyContext,
    age_in_months,
    build_context,
    match_benefit,
    next_deadline,
)

TODAY = date(2026, 11, 21)
KRAKOW = Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001")


def child(name="Antek", birth=None, due=None, status=None, **kw) -> Child:
    return Child(id=f"c-{name}", family_id="f1", name=name, birth_date=birth, due_date=due, status=status, **kw)


def parent(uid="u1", kinds=("employment",), answers=None, ezla=None) -> ParentProfile:
    return ParentProfile(
        user_id=uid,
        first_name="Anna",
        last_name="Nowak",
        pesel="90010112345",
        birth_date=date(1990, 1, 1),
        address=KRAKOW,
        insurance=[
            Insurance(kind=k, payer="X", contribution_base=5000, since=date(2020, 1, 1)) for k in kinds
        ],
        ezla=ezla or [],
        answers=answers or {},
    )


def ctx(children, parents=None, today=TODAY, unit_ids=("unit-krakow", "unit-malopolskie"), answers=None) -> FamilyContext:
    parents = parents if parents is not None else [parent()]
    merged = {}
    for p in parents:
        merged.update(p.answers)
    merged.update(answers or {})
    return FamilyContext(
        children=children, parents=parents, today=today, address=KRAKOW, answers=merged, unit_ids=list(unit_ids)
    )


def benefit(id="b1", scope="national", unit_id=None, **criteria) -> Benefit:
    conditions = criteria.pop("conditions", [])
    return Benefit(
        id=id,
        name="Testowe",
        scope=scope,
        unit_id=unit_id,
        category="benefit",
        description="opis",
        how_to_apply="jak",
        source_url="https://example.gov.pl",
        criteria=Criteria(**criteria),
        extra_conditions=conditions,
    )


def born_months_ago(months: int, name="Antek", **kw) -> Child:
    """Dziecko, które w TODAY ma dokładnie `months` pełnych miesięcy."""
    y, m = TODAY.year, TODAY.month - months
    while m < 1:
        y, m = y - 1, m + 12
    return child(name, birth=date(y, m, 21), **kw)


# ---------- wiek ----------


def test_age_in_months_counts_full_months():
    assert age_in_months(date(2026, 10, 21), date(2026, 11, 21)) == 1
    assert age_in_months(date(2026, 10, 22), date(2026, 11, 21)) == 0
    assert age_in_months(date(2023, 11, 21), date(2026, 11, 21)) == 36
    assert age_in_months(date(2023, 11, 22), date(2026, 11, 21)) == 35


def test_age_in_months_end_of_month_birthdays():
    # 31 stycznia → 28 lutego: miesiąc nie jest jeszcze pełny w lutym 2026, pełny dopiero 1 marca
    assert age_in_months(date(2026, 1, 31), date(2026, 2, 28)) == 0
    assert age_in_months(date(2026, 1, 31), date(2026, 3, 31)) == 2


@pytest.mark.parametrize(
    "months,status",
    [(0, "no"), (11, "no"), (12, "fits"), (35, "fits"), (36, "no")],
)
def test_age_bounds_are_inclusive(months, status):
    b = benefit(child_age_min_months=12, child_age_max_months=35)
    assert match_benefit(ctx([born_months_ago(months)]), b).status == status


def test_age_zero_is_in_range_when_min_is_zero():
    b = benefit(child_age_min_months=0, child_age_max_months=11)
    assert match_benefit(ctx([born_months_ago(0)]), b).status == "fits"


def test_child_turning_18_today_no_longer_qualifies_but_day_before_does():
    b = benefit(child_age_max_months=215)  # do ukończenia 18 lat
    turns_18_today = child("Maja", birth=date(2008, 11, 21))
    turns_18_tomorrow = child("Maja", birth=date(2008, 11, 22))
    assert match_benefit(ctx([turns_18_today]), b).status == "no"
    assert match_benefit(ctx([turns_18_tomorrow]), b).status == "fits"


def test_third_birthday_minus_one_day_still_under_36_months():
    b = benefit(child_age_max_months=35)
    day_before_3rd = child("Antek", birth=date(2023, 11, 22))  # 36 mies. dopiero jutro
    on_3rd = child("Antek", birth=date(2023, 11, 21))
    assert match_benefit(ctx([day_before_3rd]), b).status == "fits"
    assert match_benefit(ctx([on_3rd]), b).status == "no"


def test_any_child_in_range_is_enough():
    b = benefit(child_age_min_months=12, child_age_max_months=35)
    result = match_benefit(ctx([born_months_ago(90, name="Maja"), born_months_ago(24, name="Antek")]), b)
    assert result.status == "fits"
    assert any("Antek" in r for r in result.reasons)
    assert not any("Maja" in r for r in result.reasons)


def test_expected_child_does_not_count_for_age_benefits_and_says_after_birth():
    b = benefit(child_age_min_months=0, child_age_max_months=215)
    result = match_benefit(ctx([child("Dziecko w drodze", due=date(2027, 1, 20))]), b)
    assert result.status == "no"
    assert any("po urodzeniu" in u for u in result.unmet)


def test_no_children_at_all_is_no():
    b = benefit(child_age_max_months=215)
    result = match_benefit(ctx([]), b)
    assert result.status == "no"
    assert any("dzieci" in u for u in result.unmet)


# ---------- ciąża ----------


def test_pregnancy_requires_expected_child():
    b = benefit(requires_pregnancy=True)
    assert match_benefit(ctx([child("Dziecko", due=date(2027, 1, 20))]), b).status == "fits"
    no = match_benefit(ctx([born_months_ago(30)]), b)
    assert no.status == "no"
    assert any("ciąż" in u for u in no.unmet)


def test_pregnancy_recognised_from_ezla_code_b():
    b = benefit(requires_pregnancy=True)
    p = parent(ezla=[Ezla(code="B", from_date=date(2026, 11, 14), to_date=date(2026, 12, 12))])
    assert match_benefit(ctx([], parents=[p]), b).status == "fits"


def test_pregnancy_ended_by_loss_does_not_count():
    b = benefit(requires_pregnancy=True)
    lost = child("Dziecko", due=date(2027, 1, 20), situation="loss", situation_kind="poronienie")
    assert match_benefit(ctx([lost]), b).status == "no"


# ---------- liczba dzieci ----------


def test_min_children_counts_expected_after_birth_only():
    b = benefit(min_children=3)
    two_born_one_expected = [
        born_months_ago(90, name="Maja"),
        born_months_ago(40, name="Antek"),
        child("Dziecko w drodze", due=date(2027, 1, 20)),
    ]
    before = match_benefit(ctx(two_born_one_expected), b)
    assert before.status == "no"
    assert any("po urodzeniu" in u for u in before.unmet)
    after = [*two_born_one_expected[:2], child("Dziecko w drodze", birth=date(2026, 11, 20))]
    assert match_benefit(ctx(after), b).status == "fits"


def test_changing_child_status_to_born_recalculates():
    b = benefit(min_children=3)
    kids = [born_months_ago(90, name="Maja"), born_months_ago(40, name="Antek"), child("Nowe", due=date(2026, 11, 25))]
    assert match_benefit(ctx(kids), b).status == "no"
    kids[2] = kids[2].model_copy(update={"status": "born", "birth_date": date(2026, 11, 21)})
    assert match_benefit(ctx(kids), b).status == "fits"


def test_adult_children_are_not_counted_for_min_children():
    b = benefit(min_children=3)
    kids = [born_months_ago(90, name="A"), born_months_ago(40, name="B"), child("Dorosły", birth=date(2000, 1, 1))]
    assert match_benefit(ctx(kids), b).status == "no"


# ---------- dochód ----------


def test_income_unknown_gives_maybe_with_question():
    b = benefit(max_income_per_person=674)
    result = match_benefit(ctx([born_months_ago(40)]), b)
    assert result.status == "maybe"
    assert [q.condition_id for q in result.questions] == ["income"]
    assert "674" in result.questions[0].text


def test_income_answer_yes_fits_and_no_rejects():
    b = benefit(id="zr", max_income_per_person=674)
    kids = [born_months_ago(40)]
    yes = match_benefit(ctx(kids, answers={"benefit:zr:income": True}), b)
    no = match_benefit(ctx(kids, answers={"benefit:zr:income": False}), b)
    assert yes.status == "fits" and yes.questions == []
    assert no.status == "no" and any("dochód" in u.lower() for u in no.unmet)


def test_numeric_income_answer_is_compared_with_threshold():
    b = benefit(max_income_per_person=674)
    kids = [born_months_ago(40)]
    assert match_benefit(ctx(kids, answers={"income_per_person": "600"}), b).status == "fits"
    assert match_benefit(ctx(kids, answers={"income_per_person": "674"}), b).status == "fits"
    assert match_benefit(ctx(kids, answers={"income_per_person": "700,50"}), b).status == "no"


def test_structural_no_wins_over_open_income_question():
    b = benefit(max_income_per_person=674, child_age_max_months=35)
    result = match_benefit(ctx([born_months_ago(90)]), b)
    assert result.status == "no"
    assert result.questions == []


# ---------- niepełnosprawność, rodzina zastępcza, zatrudnienie ----------


def test_disability_and_foster_flags():
    disabled = benefit(requires_disability=True)
    foster = benefit(requires_foster=True)
    assert match_benefit(ctx([born_months_ago(40, has_disability=True)]), disabled).status == "fits"
    assert match_benefit(ctx([born_months_ago(40)]), disabled).status == "no"
    assert match_benefit(ctx([born_months_ago(40, foster=True)]), foster).status == "fits"
    assert match_benefit(ctx([born_months_ago(40)]), foster).status == "no"


def test_employment_kinds_checked_against_insurance():
    b = benefit(employment_kinds=["employment", "mandate"])
    assert match_benefit(ctx([], parents=[parent(kinds=("employment",))]), b).status == "fits"
    assert match_benefit(ctx([], parents=[parent(kinds=("jdg",))]), b).status == "no"
    assert match_benefit(ctx([], parents=[parent(kinds=())]), b).status == "no"


def test_employment_of_either_parent_counts():
    b = benefit(employment_kinds=["jdg"])
    assert match_benefit(ctx([], parents=[parent("u1"), parent("u2", kinds=("jdg",))]), b).status == "fits"


# ---------- warunki dodatkowe ----------

ASK = Condition(id="reside12", text="Zameldowanie w gminie od co najmniej 12 miesięcy", kind="ask", question="Czy mieszkasz w gminie od ponad roku?")


def test_ask_condition_unanswered_gives_maybe_with_question():
    b = benefit(id="loc", conditions=[ASK])
    result = match_benefit(ctx([born_months_ago(40)]), b)
    assert result.status == "maybe"
    assert result.questions[0].condition_id == "reside12"
    assert result.questions[0].text == "Czy mieszkasz w gminie od ponad roku?"


def test_ask_condition_answered_true_fits():
    b = benefit(id="loc", conditions=[ASK])
    assert match_benefit(ctx([], answers={"benefit:loc:reside12": True}), b).status == "fits"


def test_ask_condition_answered_false_no():
    b = benefit(id="loc", conditions=[ASK])
    result = match_benefit(ctx([], answers={"benefit:loc:reside12": False}), b)
    assert result.status == "no"
    assert any("zameldowanie" in u.lower() for u in result.unmet)


def test_auto_condition_uses_profile_key():
    cond = Condition(id="ill", text="Dziecko z ciężką chorobą", kind="auto", profile_key="family.child_serious_illness")
    b = benefit(conditions=[cond])
    assert match_benefit(ctx([born_months_ago(10, serious_illness=True)]), b).status == "fits"
    assert match_benefit(ctx([born_months_ago(10)]), b).status == "no"


def test_auto_condition_reads_plain_answers_key():
    cond = Condition(id="x", text="Samotne wychowywanie", kind="auto", profile_key="single_parent")
    b = benefit(conditions=[cond])
    assert match_benefit(ctx([], answers={"single_parent": True}), b).status == "fits"
    assert match_benefit(ctx([], answers={"single_parent": False}), b).status == "no"


def test_auto_condition_unresolved_becomes_question():
    cond = Condition(id="x", text="Samotne wychowywanie dziecka", kind="auto", profile_key="single_parent")
    result = match_benefit(ctx([]), benefit(conditions=[cond]))
    assert result.status == "maybe"
    assert result.questions[0].condition_id == "x"


# ---------- zasięg terytorialny ----------


def test_other_municipality_is_no_with_reason():
    b = benefit(scope="municipal", unit_id="unit-wieliczka")
    result = match_benefit(ctx([born_months_ago(10)]), b)
    assert result.status == "no"
    assert any("innej" in u for u in result.unmet)


def test_own_municipality_and_voivodeship_pass():
    assert match_benefit(ctx([]), benefit(scope="municipal", unit_id="unit-krakow")).status == "fits"
    assert match_benefit(ctx([]), benefit(scope="regional", unit_id="unit-malopolskie")).status == "fits"


def test_regional_benefit_without_unit_never_matches():
    assert match_benefit(ctx([]), benefit(scope="regional", unit_id=None)).status == "no"


# ---------- czytelność ----------


def test_reasons_are_human_readable_polish():
    b = benefit(scope="municipal", unit_id="unit-krakow", child_age_min_months=12, child_age_max_months=35)
    result = match_benefit(ctx([born_months_ago(36 - 12, name="Antek")]), b)  # 24 mies. = 2 lata
    assert result.status == "fits"
    text = " ".join(result.reasons)
    assert "Antek ma 2 lata" in text
    assert "mieszkasz w gminie Kraków" in text


@pytest.mark.parametrize(
    "months,expected",
    [(0, "0 miesięcy"), (1, "1 miesiąc"), (3, "3 miesiące"), (12, "12 miesięcy"), (23, "23 miesiące"),
     (24, "2 lata"), (36, "3 lata"), (60, "5 lat"), (84, "7 lat"), (132, "11 lat"), (156, "13 lat"), (264, "22 lata")],
)
def test_age_phrase_polish_plurals(months, expected):
    from app.services.matching import age_phrase

    assert age_phrase(months) == expected


# ---------- build_context ----------


def _family_view(children):
    user = User(id="u1", role="parent", name="Anna Nowak", family_id="f1")
    fam = Family(id="f1", name="Rodzina Nowak", owner_id="u1", member_ids=["u1"])
    return FamilyView(family=fam, members=[user], children=children)


def test_build_context_merges_answers_viewer_wins_and_computes_units():
    p1 = parent("u1", answers={"a": True, "shared": "z1"})
    p2 = parent("u2", answers={"b": False, "shared": "z2"})
    units = [
        {"id": "unit-krakow", "level": "gmina", "gmina": "Kraków", "powiat": "Kraków", "voivodeship": "Małopolskie"},
        {"id": "unit-slask", "level": "voivodeship", "voivodeship": "Śląskie"},
    ]
    c = build_context(_family_view([]), [p1, p2], TODAY, units=units, viewer_id="u1")
    assert c.answers == {"a": True, "b": False, "shared": "z1"}
    assert c.unit_ids == ["unit-krakow"]
    assert c.address.gmina == "Kraków"


def test_build_context_without_profiles_has_blank_address():
    c = build_context(_family_view([]), [], TODAY)
    assert c.address.gmina == ""
    assert match_benefit(c, benefit(scope="municipal", unit_id="unit-krakow")).status == "no"


# ---------- terminy ----------


def test_next_deadline_from_birth_anchor():
    b = benefit()
    b.deadline = Deadline(anchor="birth", offset_days=21)
    c = ctx([child("Nowe", birth=date(2026, 11, 10))])
    assert next_deadline(b, c) == date(2026, 12, 1)


def test_next_deadline_uses_due_date_for_expected_child_and_ignores_past():
    b = benefit()
    b.deadline = Deadline(anchor="due", offset_days=-14)
    assert next_deadline(b, ctx([child("W drodze", due=date(2027, 1, 20))])) == date(2027, 1, 6)
    b.deadline = Deadline(anchor="birth", offset_days=10)
    assert next_deadline(b, ctx([child("Stare", birth=date(2020, 1, 1))])) is None


def test_next_deadline_child_age_and_fixed():
    b = benefit()
    b.deadline = Deadline(anchor="child_age", offset_months=36)
    assert next_deadline(b, ctx([child("Antek", birth=date(2024, 1, 15))])) == date(2027, 1, 15)
    b.deadline = Deadline(anchor="fixed", fixed_date=date(2026, 12, 31))
    assert next_deadline(b, ctx([])) == date(2026, 12, 31)
    b.deadline = None
    assert next_deadline(b, ctx([])) is None


# ---------- ciąża albo noworodek ----------


def test_pregnant_or_newborn_fits_when_pregnant():
    b = benefit(pregnant_or_child_max_months=5)
    assert match_benefit(ctx([child("W drodze", due=date(2027, 1, 20))]), b).status == "fits"


@pytest.mark.parametrize("months,status", [(0, "fits"), (5, "fits"), (6, "no")])
def test_pregnant_or_newborn_after_birth_bounds_inclusive(months, status):
    b = benefit(pregnant_or_child_max_months=5)
    assert match_benefit(ctx([born_months_ago(months)]), b).status == status


def test_pregnant_or_newborn_no_without_either():
    b = benefit(pregnant_or_child_max_months=5)
    r = match_benefit(ctx([born_months_ago(40)]), b)
    assert r.status == "no" and r.unmet
