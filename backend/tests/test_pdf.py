import io
from datetime import date

import pytest
from pypdf import PdfReader

from app.errors import DomainError
from app.services.employer_pdf import EmployerData, render_employer_application
from app.services.pdf_fill import fill_pdf, format_value
from app.services.prefill import FormField, form_schema


def _fields(pdf_bytes: bytes) -> dict:
    return PdfReader(io.BytesIO(pdf_bytes)).get_fields() or {}


def _value(fields: dict, name: str):
    return fields[name].get("/V")


P1 = "topmostSubform[0].Page1[0]."


def test_filled_pdf_contains_values():
    pdf = fill_pdf(
        "ZAM",
        {
            "pesel": "90010112345",
            "birth_date": "1990-01-01",
            "first_name": "Żaneta",
            "last_name": "Nowak",
            "street": "Floriańska",
            "postal_code": "30-001",
            "leave_mac": True,
            "leave_mac_period": "01.12.2026 – 18.04.2027",
        },
    )
    f = _fields(pdf)
    assert _value(f, P1 + "PESEL[0]") == "90010112345"
    assert _value(f, P1 + "Dataurodzenia[0]") == "01011990"  # pole „grzebieniowe”: same cyfry
    assert _value(f, P1 + "Imie[0]") == "ŻANETA"  # ZUS: wielkie litery
    assert _value(f, P1 + "Ulica[0]") == "FLORIAŃSKA"
    assert _value(f, P1 + "Kodpocztowy[0]") == "30-001"
    assert _value(f, "topmostSubform[0].Page2[0].macierzynskiego[0]") == "/1"
    assert "–" in _value(f, "topmostSubform[0].Page2[0].Okres[0]")


def test_unfilled_fields_stay_empty_and_false_checkbox_not_checked():
    f = _fields(fill_pdf("ZAM", {"pesel": "90010112345", "leave_mac": False}))
    assert _value(f, P1 + "Nazwisko[0]") in (None, "")
    assert _value(f, "topmostSubform[0].Page2[0].macierzynskiego[0]") in (None, "/Off")


def test_need_appearances_set():
    reader = PdfReader(io.BytesIO(fill_pdf("ZAM", {"pesel": "90010112345"})))
    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"] == True  # noqa: E712 (BooleanObject)


def test_unknown_values_are_ignored():
    fill_pdf("ZAM", {"nie_ma_takiego_pola": "x", "pesel": "90010112345"})


def test_other_forms_fill():
    for code in ("ZAS-53", "ZAS-26", "ZAS-33", "ZAS-39", "ZAS-55", "ZNp-7"):
        pesel_field = next(f for f in form_schema(code) if f.id == "pesel")
        f = _fields(fill_pdf(code, {"pesel": "90010112345"}))
        assert _value(f, pesel_field.pdf_field) == "90010112345", code


def test_unknown_code_raises():
    with pytest.raises(DomainError):
        fill_pdf("NIE-MA", {})
    with pytest.raises(DomainError):  # Z-10 nie ma pól AcroForm
        fill_pdf("Z-10", {})


def test_format_value_rules():
    assert format_value(FormField(id="x", label="x", type="date"), "2026-12-01") == "01.12.2026"
    assert format_value(FormField(id="x", label="x", type="bool"), True) == "/1"
    assert format_value(FormField(id="x", label="x", type="bool"), False) is None
    assert format_value(FormField(id="x", label="x", format="digits"), "PL 12 34") == "1234"
    assert format_value(FormField(id="x", label="x"), "   ") is None


# ---------- PDF do pracodawcy ----------


def _text(pdf_bytes: bytes) -> str:
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    return " ".join(text.split())  # wyjustowanie i zawijanie wierszy nie ma znaczenia dla treści


def _data(**kw) -> EmployerData:
    base = dict(
        first_name="Żaneta",
        last_name="Wiśniewska-Łuczak",
        employer_name="Zakłady Mięsne „Źródło” Sp. z o.o.",
        child_name="Jaś",
        child_date=date(2027, 1, 20),
        leave_start=date(2026, 12, 9),
        leave_end=date(2027, 4, 26),
        parental_weeks=32,
        city="Kraków",
        today=date(2026, 11, 21),
    )
    base.update(kw)
    return EmployerData(**base)


def test_employer_pdf_has_polish_diacritics_and_dates():
    text = _text(render_employer_application("URLOP-MAC-ROD", _data()))
    assert "Żaneta Wiśniewska-Łuczak" in text
    assert "Zakłady Mięsne „Źródło” Sp. z o.o." in text
    assert "urlopu macierzyńskiego" in text
    assert "09.12.2026" in text and "26.04.2027" in text
    assert "21.11.2026" in text and "Kraków" in text
    assert "32 tygodni" in text
    assert "20.01.2027" in text and "przewidywany termin porodu" in text


def test_employer_pdf_born_child_uses_birth_date_wording():
    text = _text(render_employer_application("URLOP-OJC", _data(child_born=True, child_date=date(2026, 11, 1))))
    assert "data urodzenia: 01.11.2026" in text
    assert "urlopu ojcowskiego" in text


@pytest.mark.parametrize(
    "kind,phrase",
    [
        ("URLOP-MAC-ROD", "macierzyńskiego"),
        ("URLOP-ROD", "rodzicielskiego"),
        ("URLOP-OJC", "ojcowskiego"),
        ("URLOP-UZUP", "uzupełniającego urlopu macierzyńskiego"),
        ("URLOP-ROD-PRACA", "połowa wymiaru czasu pracy"),
        ("REZYGNACJA-MAC", "rezygnuję z dalszej części"),
    ],
)
def test_every_kind_renders_valid_pdf(kind, phrase):
    pdf = render_employer_application(kind, _data())
    assert pdf.startswith(b"%PDF")
    assert phrase in _text(pdf)


def test_missing_dates_show_placeholder_not_none():
    text = _text(render_employer_application("URLOP-ROD", _data(leave_start=None, leave_end=None)))
    assert "None" not in text and "………" in text


def test_unknown_kind_raises():
    with pytest.raises(DomainError):
        render_employer_application("INNY", _data())
