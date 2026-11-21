import json
from datetime import date, timedelta

import pytest
from pypdf import PdfReader

from app.errors import DomainError
from app.models.family import Child, Family, FamilyView
from app.services.prefill import (
    DATA,
    MAPS_DIR,
    FormField,
    form_schema,
    map_codes,
    portal_schema,
    prefill,
    prefill_portal,
    recommend_flow,
    requires_child,
    valid_pesel,
    validate_answer,
)
from app.services.zus_sim import fetch_zus_data

TODAY = date.today()
CATALOG_CODES = {
    w["kod"] for w in json.loads((DATA / "katalog_wnioskow_pdf.json").read_text(encoding="utf-8"))["wnioski"]
}


def view(third_born=False) -> FamilyView:
    third = (
        Child(id="c3", family_id="f", name="Hania", birth_date=TODAY - timedelta(days=20))
        if third_born
        else Child(id="c3", family_id="f", name="Dziecko w drodze", due_date=TODAY + timedelta(days=60))
    )
    kids = [
        Child(id="c1", family_id="f", name="Maja", birth_date=TODAY - timedelta(days=7 * 365 + 90), pesel="18210112345"),
        third,
    ]
    return FamilyView(family=Family(id="f", name="Nowak", owner_id="u", member_ids=["u"]), members=[], children=kids)


def anna(**answers):
    p = fetch_zus_data("persona-nowak-anna", TODAY)
    p.answers = dict(answers)
    return p


def piotr():
    return fetch_zus_data("persona-nowak-piotr", TODAY)


# ---------- mapy pól vs PDF ----------


@pytest.mark.parametrize("code", map_codes())
def test_map_fields_exist_in_pdf(code):
    m = json.loads((MAPS_DIR / f"{code}.json").read_text(encoding="utf-8"))
    if not m["pdf"]:
        assert m["fields"] == []  # brak PDF z polami — mapa pusta i opisana w `note`
        assert m.get("note")
        return
    names = set((PdfReader(DATA / "wnioski_pdf" / m["pdf"]).get_fields() or {}).keys())
    absent = [f["pdf_field"] for f in m["fields"] if f["pdf_field"] not in names]
    assert not absent, f"{code}: pola spoza PDF: {absent}"


def test_all_requested_maps_exist_and_codes_in_catalog():
    expected = {"ZAM", "ZAS-53", "ZAS-26", "ZAS-33", "Z-3", "Z-3a", "ZAS-39", "ZAS-55", "ZNp-7", "Z-10"}
    assert set(map_codes()) == expected
    assert expected <= CATALOG_CODES


@pytest.mark.parametrize("code", map_codes())
def test_map_field_ids_and_pdf_fields_unique(code):
    fields = form_schema(code)
    assert len({f.id for f in fields}) == len(fields)
    assert len({f.pdf_field for f in fields}) == len(fields)


def test_portal_schemas_parse_and_ids_unique():
    for pid in ("ezus_800plus", "ezus_aktywny_rodzic", "ezus_zam", "emp_kdr", "emp_za_zyciem"):
        fields = portal_schema(pid)
        assert fields and len({f.id for f in fields}) == len(fields)


def test_unknown_form_and_portal():
    with pytest.raises(DomainError):
        form_schema("NIE-MA")
    with pytest.raises(DomainError):
        portal_schema("nie_ma")


# ---------- prefill ----------


def test_prefill_zam_from_nowak_anna():
    r = prefill("ZAM", view(third_born=True), [anna()], "c3")
    v = r.values
    assert v["first_name"] == "Anna" and v["last_name"] == "Nowak"
    assert v["postal_code"] == "30-001" and v["post_office"] == "Kraków"
    assert v["payer_name"].startswith("Krakowskie Centrum")
    assert v["leave_mac"] is True
    assert v["leave_mac_period"].count("–") == 1 and v["child_details"].startswith("Hania Nowak, ur. ")
    assert valid_pesel(v["pesel"])
    # adres (ulica, nr domu) nie pochodzi z ZUS -> trzeba dopytać
    assert {"street", "house_no"} <= {q.field_id for q in r.missing}
    assert "pesel" not in {q.field_id for q in r.missing}


def test_prefill_zam_for_expected_child_uses_due_date():
    r = prefill("ZAM", view(), [anna()], "c3")
    assert r.values["due_date_flag"] is True and "due_date" in r.values
    assert "child_details" not in r.values  # dziecka jeszcze nie ma: wymagana jest data porodu, nie opis
    assert "child_details" not in {q.field_id for q in r.missing}


def test_missing_pesel_listed():
    r = prefill_portal("ezus_800plus", view(), [anna()], "c3")  # dziecko w drodze nie ma PESEL
    assert "child_pesel" in {q.field_id for q in r.missing}
    assert "child_pesel" not in r.values  # nie wstawiamy pustej wartości


def test_born_child_pesel_is_prefilled_from_family_data():
    r = prefill_portal("ezus_800plus", view(), [anna()], "c1")
    assert r.values["child_pesel"] == "18210112345"
    assert r.values["citizenship"] == "polskie"  # wartość domyślna do poprawy w podglądzie


def test_answers_fill_missing():
    base = prefill("ZAM", view(third_born=True), [anna()], "c3")
    answered = prefill("ZAM", view(third_born=True), [anna()], "c3", {"street": "Floriańska", "house_no": "5"})
    assert {"street", "house_no"} <= {q.field_id for q in base.missing}
    assert answered.values["street"] == "Floriańska"
    assert not {"street", "house_no"} & {q.field_id for q in answered.missing}


def test_profile_answers_are_used_so_we_do_not_ask_twice():
    r = prefill("ZAM", view(third_born=True), [anna(street="Szeroka", house_no="7")], "c3")
    assert r.values["street"] == "Szeroka" and "street" not in {q.field_id for q in r.missing}


def test_partner_answers_are_shared_but_applicant_wins():
    a = anna(street="Moja")
    p = piotr()
    p.answers = {"street": "Jego", "house_no": "9"}
    r = prefill("ZAM", view(third_born=True), [a, p], "c3", applicant_id=a.user_id)
    assert r.values["street"] == "Moja" and r.values["house_no"] == "9"


def test_explicit_answer_overrides_profile_value():
    r = prefill("ZAM", view(third_born=True), [anna()], "c3", {"first_name": "Ania"})
    assert r.values["first_name"] == "Ania"


def test_blank_answer_does_not_hide_missing():
    r = prefill("ZAM", view(third_born=True), [anna()], "c3", {"street": "   "})
    assert "street" in {q.field_id for q in r.missing}


def test_other_family_child_404():
    with pytest.raises(DomainError) as e:
        prefill("ZAM", view(), [anna()], "child-cudzej-rodziny")
    assert e.value.status_code == 404


def test_child_fields_missing_without_child():
    r = prefill_portal("ezus_800plus", view(), [anna()], None)
    assert {"child_first_name", "child_birth_date", "child_pesel"} <= {q.field_id for q in r.missing}


def test_kdr_children_count_is_calculated():
    r = prefill_portal("emp_kdr", view(third_born=True), [anna()])
    assert r.values["children_count"] == "2"


def test_employer_schema_and_prefill():
    r = prefill("URLOP-MAC-ROD", view(), [anna()], "c3")
    assert r.values["employer_name"].startswith("Krakowskie Centrum")
    assert r.values["child_date"] == (TODAY + timedelta(days=60)).isoformat()
    assert r.values["leave_start"] == r.values["child_date"]
    assert all(q.field_id != "employer_email" for q in r.missing)  # adres e-mail nie jest wymagany w schemacie


def test_employer_leave_requires_explicit_dates():
    r = prefill("URLOP-OJC", view(third_born=True), [anna()], "c3")
    assert {"leave_start", "leave_end"} <= {q.field_id for q in r.missing}
    ok = prefill("URLOP-OJC", view(third_born=True), [anna()], "c3", {"leave_start": "2026-12-01", "leave_end": "2026-12-14"})
    assert not ok.missing


# ---------- przepływ ----------


def test_recommend_flow_employee_urlop_then_zam():
    assert recommend_flow("employment") == ["URLOP-MAC-ROD", "ZAM"]


def test_recommend_flow_mandate_zam_only():
    assert recommend_flow("mandate") == ["ZAM"]
    assert recommend_flow("jdg") == ["ZAM"]
    assert recommend_flow(None) == ["ZAM"]


def test_flow_codes_have_schemas():
    for kind in ("employment", "mandate", "jdg"):
        for code in recommend_flow(kind):
            assert form_schema(code)


def test_requires_child():
    assert requires_child("ZAM") and requires_child("800PLUS") and requires_child("URLOP-MAC-ROD")
    assert not requires_child("KDR") and not requires_child("ZAS-53")


# ---------- walidacja odpowiedzi ----------


def test_valid_pesel_checksum():
    assert valid_pesel(anna().pesel)
    assert not valid_pesel("12345678901") and not valid_pesel("abc") and not valid_pesel("")


def test_validate_answer_rules():
    pesel_field = FormField(id="child_pesel", label="PESEL dziecka", format="pesel")
    assert validate_answer(pesel_field, " " + anna().pesel + " ") == anna().pesel
    with pytest.raises(DomainError):
        validate_answer(pesel_field, "11111111111")
    assert validate_answer(FormField(id="d", label="Data", type="date"), "2026-12-01") == "2026-12-01"
    with pytest.raises(DomainError):
        validate_answer(FormField(id="d", label="Data", type="date"), "01.12.2026")
    with pytest.raises(DomainError):
        validate_answer(FormField(id="c", label="Wariant", type="choice", choices=["a", "b"]), "z")
    assert validate_answer(FormField(id="n", label="Rachunek", format="digits"), "12 3456 78") == "12345678"
    with pytest.raises(DomainError):
        validate_answer(FormField(id="b", label="Tak/nie", type="bool"), "tak")
    with pytest.raises(DomainError):
        validate_answer(FormField(id="s", label="Ulica"), "  ")
