from datetime import date, timedelta

import pytest

from app.errors import DomainError
from app.services.zus_sim import fetch_zus_data

TODAY = date(2026, 11, 21)


def test_zus_sim_nowak_anna_has_employment_ezla_b_and_known_children():
    p = fetch_zus_data("persona-nowak-anna", TODAY)
    assert (p.first_name, p.last_name) == ("Anna", "Nowak")
    assert p.address.city == "Kraków" and p.address.voivodeship == "Małopolskie"
    assert p.address.powiat == "Kraków" and p.address.gmina == "Kraków"
    assert len(p.pesel) == 11 and p.pesel.isdigit()
    assert [i.kind for i in p.insurance] == ["employment"]
    assert p.insurance[0].contribution_base == pytest.approx(7850.0)
    assert [e.code for e in p.ezla] == ["B"]
    assert p.ezla[0].from_date <= TODAY <= p.ezla[0].to_date
    assert p.contribution_debt is None
    kids = p.known_children
    assert len(kids) == 3
    born = [k for k in kids if k.birth_date]
    expected = [k for k in kids if k.due_date]
    assert len(born) == 2 and len(expected) == 1
    assert expected[0].due_date == TODAY + timedelta(days=60)
    ages = sorted((TODAY - k.birth_date).days // 365 for k in born)
    assert ages == [3, 7]


def test_zus_sim_dates_relative_to_today():
    a = fetch_zus_data("persona-nowak-anna", TODAY)
    b = fetch_zus_data("persona-nowak-anna", TODAY + timedelta(days=10))
    due_a = next(k.due_date for k in a.known_children if k.due_date)
    due_b = next(k.due_date for k in b.known_children if k.due_date)
    assert due_b - due_a == timedelta(days=10)
    assert b.ezla[0].from_date - a.ezla[0].from_date == timedelta(days=10)


def test_zus_sim_piotr_different_employer_no_ezla():
    anna = fetch_zus_data("persona-nowak-anna", TODAY)
    piotr = fetch_zus_data("persona-nowak-piotr", TODAY)
    assert piotr.first_name == "Piotr"
    assert piotr.insurance[0].payer != anna.insurance[0].payer
    assert piotr.ezla == []
    assert piotr.pesel != anna.pesel


def test_zus_sim_unknown_persona_raises():
    with pytest.raises(DomainError) as e:
        fetch_zus_data("persona-nie-ma", TODAY)
    assert e.value.status_code == 404
