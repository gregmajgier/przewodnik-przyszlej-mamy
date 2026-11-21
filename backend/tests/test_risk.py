from datetime import date, datetime, timezone

from app.models.contract import Contract
from app.models.family import Child
from app.models.profile import Address, Debt, Insurance, ParentProfile
from app.services.risk import evaluate_risks

TODAY = date(2026, 11, 21)
DUE = date(2027, 1, 20)


def _profile(**over) -> ParentProfile:
    base = dict(
        user_id="u1",
        first_name="Anna",
        last_name="Nowak",
        pesel="95031512345",
        birth_date=date(1995, 3, 15),
        address=Address(city="Kraków", gmina="Kraków", powiat="Kraków", voivodeship="Małopolskie", postal_code="30-001"),
    )
    base.update(over)
    return ParentProfile(**base)


def _contract(cid="c1", **over) -> Contract:
    base = dict(
        id=cid,
        user_id="u1",
        family_id="f1",
        filename="u.pdf",
        confirmed=True,
        created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        kind="employment",
        employer_name="Firma Sp. z o.o.",
        fte=1.0,
        gross_monthly=7000.0,
        start_date=date(2024, 1, 1),
        indefinite=True,
    )
    base.update(over)
    return Contract(**base)


def _expected(due=DUE) -> Child:
    return Child(id="ch1", family_id="f1", name="Dziecko w drodze", due_date=due)


def _born() -> Child:
    return Child(id="ch0", family_id="f1", name="Maja", birth_date=date(2019, 5, 1))


def test_fixed_term_ending_before_due_date_info():
    c = _contract(indefinite=False, end_date=date(2026, 12, 31))
    risks = evaluate_risks(_profile(), [c], [_expected()], TODAY)
    assert len(risks) == 1
    r = risks[0]
    assert r.severity == "info"
    assert r.user_id == "u1"
    assert r.source_ref == "c1"
    assert r.deadline == date(2026, 12, 31)
    assert "porod" in r.explanation.lower()


def test_fixed_term_ending_after_due_date_no_risk():
    c = _contract(indefinite=False, end_date=date(2027, 6, 30))
    assert evaluate_risks(_profile(), [c], [_expected()], TODAY) == []


def test_indefinite_contract_no_risk():
    assert evaluate_risks(_profile(), [_contract()], [_expected()], TODAY) == []


def test_mandate_without_voluntary_sickness_high():
    c = _contract(kind="mandate", voluntary_sickness=False)
    risks = evaluate_risks(_profile(), [c], [_expected()], TODAY)
    assert len(risks) == 1
    assert risks[0].severity == "high"
    assert "macierzyński" in (risks[0].title + risks[0].explanation).lower()
    assert risks[0].action


def test_mandate_with_voluntary_sickness_ok():
    c = _contract(kind="mandate", voluntary_sickness=True)
    assert evaluate_risks(_profile(), [c], [_expected()], TODAY) == []


def test_jdg_debt_high_with_action():
    profile = _profile(contribution_debt=Debt(amount=1200.0, since=date(2026, 6, 1)))
    c = _contract(kind="jdg", voluntary_sickness=True)
    risks = evaluate_risks(profile, [c], [_expected()], TODAY)
    assert len(risks) == 1
    r = risks[0]
    assert r.severity == "high"
    assert r.action and r.deadline == DUE
    assert "1200" in r.explanation.replace(" ", "").replace("\xa0", "")  # kwota zadłużenia


def test_jdg_debt_from_zus_insurance_without_scanned_contract():
    profile = _profile(
        contribution_debt=Debt(amount=500.0, since=date(2026, 6, 1)),
        insurance=[Insurance(kind="jdg", payer="Nowak Anna", contribution_base=4000.0, since=date(2020, 1, 1))],
    )
    risks = evaluate_risks(profile, [], [_expected()], TODAY)
    assert [r.severity for r in risks] == ["high"]


def test_debt_without_jdg_is_not_reported():
    profile = _profile(contribution_debt=Debt(amount=500.0, since=date(2026, 6, 1)))
    assert evaluate_risks(profile, [_contract()], [_expected()], TODAY) == []


def test_no_expected_child_no_pregnancy_risks():
    profile = _profile(contribution_debt=Debt(amount=500.0, since=date(2026, 6, 1)))
    contracts = [
        _contract("c1", indefinite=False, end_date=date(2026, 12, 31)),
        _contract("c2", kind="mandate", voluntary_sickness=False),
        _contract("c3", kind="jdg"),
    ]
    assert evaluate_risks(profile, contracts, [_born()], TODAY) == []
    assert evaluate_risks(profile, contracts, [], TODAY) == []


def test_two_contracts_independent_risks():
    contracts = [
        _contract("c1", indefinite=False, end_date=date(2026, 12, 31)),
        _contract("c2", kind="mandate", employer_name="Inna Firma", voluntary_sickness=None),
    ]
    risks = evaluate_risks(_profile(), contracts, [_expected()], TODAY)
    assert {(r.source_ref, r.severity) for r in risks} == {("c1", "info"), ("c2", "high")}
    assert len({r.id for r in risks}) == 2


def test_risk_ids_stable():
    contracts = [_contract("c1", indefinite=False, end_date=date(2026, 12, 31))]
    a = evaluate_risks(_profile(), contracts, [_expected()], TODAY)
    b = evaluate_risks(_profile(), contracts, [_expected()], date(2026, 11, 22))
    assert [r.id for r in a] == [r.id for r in b]


def test_unconfirmed_and_foreign_contracts_ignored():
    contracts = [
        _contract("c1", confirmed=False, indefinite=False, end_date=date(2026, 12, 31)),
        _contract("c2", user_id="u2", kind="mandate", voluntary_sickness=False),
    ]
    assert evaluate_risks(_profile(), contracts, [_expected()], TODAY) == []


def test_zus_mandate_without_contract_is_reported_once():
    ins = Insurance(kind="mandate", payer="Zleceniodawca SA", contribution_base=3000.0, since=date(2025, 1, 1))
    profile = _profile(insurance=[ins])
    assert len(evaluate_risks(profile, [], [_expected()], TODAY)) == 1
    c = _contract("c1", kind="mandate", employer_name="zleceniodawca sa", voluntary_sickness=False)
    risks = evaluate_risks(profile, [c], [_expected()], TODAY)
    assert len(risks) == 1 and risks[0].source_ref == "c1"


def test_sorted_by_severity_then_deadline():
    contracts = [
        _contract("c1", indefinite=False, end_date=date(2026, 12, 31)),
        _contract("c2", kind="mandate", voluntary_sickness=False),
    ]
    risks = evaluate_risks(_profile(), contracts, [_expected()], TODAY)
    assert [r.severity for r in risks] == ["high", "info"]
