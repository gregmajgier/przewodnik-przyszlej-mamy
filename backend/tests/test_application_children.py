"""Którego dziecka może dotyczyć wniosek (np. nie ma urlopu ojcowskiego na 7-latka)."""

from datetime import date, timedelta

import pytest
from conftest import login

from app.models.family import Child
from app.services.application_children import child_block_reason

TODAY = date(2026, 11, 22)


def kid(name="Hania", *, months=None, days=None, born=None, expected=False, **kw) -> Child:
    if expected:
        return Child(id=f"c-{name}", family_id="f", name=name, due_date=TODAY + timedelta(days=60), **kw)
    if born is None:
        if months is not None:
            y, m = TODAY.year, TODAY.month - months
            while m < 1:
                y, m = y - 1, m + 12
            born = date(y, m, TODAY.day)
        else:
            born = TODAY - timedelta(days=days)
    return Child(id=f"c-{name}", family_id="f", name=name, birth_date=born, **kw)


def reason(code, child, siblings=None):
    return child_block_reason(code, child, siblings or [child], TODAY)


# ---------- urlop ojcowski ----------


@pytest.mark.parametrize("months", [0, 6, 11])
def test_paternity_leave_ok_until_12_months(months):
    assert reason("URLOP-OJC", kid(months=months)) is None


def test_paternity_leave_ok_before_birth():
    assert reason("URLOP-OJC", kid(expected=True)) is None


@pytest.mark.parametrize("months", [12, 36, 84])
def test_paternity_leave_blocked_from_12_months(months):
    msg = reason("URLOP-OJC", kid("Maja", months=months))
    assert msg is not None and "12 miesięcy" in msg and "Maja" in msg


def test_paternity_leave_for_adopted_child_up_to_14_years():
    assert reason("URLOP-OJC", kid(months=7 * 12, foster=True)) is None
    assert reason("URLOP-OJC", kid(months=14 * 12, foster=True)) is not None


# ---------- urlop i zasiłek macierzyński / rodzicielski ----------


def test_maternity_leave_request_before_birth_and_within_20_weeks():
    assert reason("URLOP-MAC-ROD", kid(expected=True)) is None
    assert reason("URLOP-MAC-ROD", kid(days=20 * 7 - 1)) is None
    assert reason("URLOP-MAC-ROD", kid(days=20 * 7)) is not None


def test_twins_have_longer_maternity_leave():
    a, b = kid("Ala", days=25 * 7), kid("Ola", days=25 * 7)
    assert reason("URLOP-MAC-ROD", a, [a, b]) is None  # bliźnięta: 31 tygodni


def test_resignation_and_supplementary_leave_only_after_birth():
    for code in ("REZYGNACJA-MAC", "URLOP-UZUP"):
        assert reason(code, kid(expected=True)) == "Ten wniosek składa się po porodzie."
        assert reason(code, kid(days=30)) is None


def test_parental_leave_until_end_of_year_child_turns_6():
    assert reason("URLOP-ROD", kid(born=date(2020, 12, 1))) is None  # 6 lat w 2026 -> do 31.12.2026
    msg = reason("ZAM", kid("Maja", born=date(2019, 8, 26)))  # 6 lat w 2025 -> termin minął
    assert msg is not None and "31.12.2025" in msg


# ---------- świadczenia ----------


def test_800_plus_needs_born_child_under_18():
    assert reason("800PLUS", kid(expected=True)) is not None
    assert reason("800PLUS", kid(months=17 * 12 + 11)) is None
    assert reason("800PLUS", kid(months=18 * 12)) is not None


def test_za_zyciem_needs_serious_illness_within_12_months():
    assert reason("ZA-ZYCIEM", kid(months=3, serious_illness=True)) is None
    assert "zaświadczenia" in reason("ZA-ZYCIEM", kid(months=3))
    assert reason("ZA-ZYCIEM", kid(months=12, serious_illness=True)) is not None


def test_active_parent_12_to_35_months():
    assert reason("AKTYWNY-RODZIC", kid(months=11)) is not None
    assert reason("AKTYWNY-RODZIC", kid(months=12)) is None
    assert reason("AKTYWNY-RODZIC", kid(months=35)) is None
    assert reason("AKTYWNY-RODZIC", kid(months=36)) is not None


def test_forms_without_child_rules_are_not_blocked():
    assert reason("KDR", kid(months=200)) is None


# ---------- API ----------


def _family(client):
    h = login(client, "persona-nowak-anna")
    assert client.post("/api/families", json={}, headers=h).status_code == 201
    today = date.today()
    ids = {}
    for body in (
        {"name": "Maja", "birth_date": (today - timedelta(days=7 * 365 + 90)).isoformat()},
        {"name": "Maleństwo", "due_date": (today + timedelta(days=60)).isoformat()},
    ):
        r = client.post("/api/families/me/children", json=body, headers=h)
        assert r.status_code == 201, r.text
        ids[body["name"]] = r.json()["id"]
    return h, ids


def test_api_forms_list_blocked_children_with_reason(client):
    h, ids = _family(client)
    forms = {f["code"]: f for f in client.get("/api/applications/forms", headers=h).json()["forms"]}
    assert ids["Maja"] in forms["URLOP-OJC"]["child_blocks"]
    assert ids["Maleństwo"] not in forms["URLOP-OJC"]["child_blocks"]
    assert forms["KDR"]["child_blocks"] == {}


def test_api_rejects_paternity_leave_for_7_year_old(client):
    h, ids = _family(client)
    r = client.post("/api/applications", json={"form_code": "URLOP-OJC", "child_id": ids["Maja"]}, headers=h)
    assert r.status_code == 422
    assert "12 miesięcy" in r.json()["detail"]
    ok = client.post("/api/applications", json={"form_code": "URLOP-OJC", "child_id": ids["Maleństwo"]}, headers=h)
    assert ok.status_code in (200, 201), ok.text
