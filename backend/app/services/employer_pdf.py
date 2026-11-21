"""Generowanie wniosków pracowniczych do pracodawcy (urlopy rodzicielskie) jako PDF.

Wzór: rozporządzenie MRPiPS z 11.03.2025 r. (Dz.U. 2025 poz. 322). Wniosek do pracodawcy nie ma urzędowego
druku, więc generujemy go sami. Treść wymaga weryfikacji prawnej przed użyciem produkcyjnym.
Font Unicode (DejaVu Sans) jest w repozytorium — polskie znaki muszą się poprawnie wyświetlać.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from fpdf import FPDF
from pydantic import BaseModel

from ..errors import DomainError

FONT_DIR = Path(__file__).resolve().parents[1] / "data" / "fonts"

Kind = Literal["URLOP-MAC-ROD", "URLOP-ROD", "URLOP-OJC", "URLOP-UZUP", "URLOP-ROD-PRACA", "REZYGNACJA-MAC"]

TITLES: dict[str, str] = {
    "URLOP-MAC-ROD": "Wniosek o udzielenie urlopu macierzyńskiego i bezpośrednio po nim urlopu rodzicielskiego",
    "URLOP-ROD": "Wniosek o udzielenie urlopu rodzicielskiego",
    "URLOP-OJC": "Wniosek o udzielenie urlopu ojcowskiego",
    "URLOP-UZUP": "Wniosek o udzielenie uzupełniającego urlopu macierzyńskiego",
    "URLOP-ROD-PRACA": "Wniosek o łączenie urlopu rodzicielskiego z wykonywaniem pracy",
    "REZYGNACJA-MAC": "Wniosek o rezygnację z dalszej części urlopu macierzyńskiego",
}


class EmployerData(BaseModel):
    first_name: str
    last_name: str
    employer_name: str
    child_name: str
    child_date: date
    child_born: bool = False  # True: data urodzenia, False: przewidywany termin porodu
    leave_start: date | None = None
    leave_end: date | None = None
    parental_weeks: int | None = None
    employer_address: str | None = None
    applicant_address: str | None = None
    city: str | None = None
    today: date | None = None


def _d(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "………………"


def _body(kind: str, data: EmployerData) -> list[str]:
    child = (
        f"w związku z urodzeniem dziecka {data.child_name} (data urodzenia: {_d(data.child_date)})"
        if data.child_born
        else f"w związku z oczekiwanym dzieckiem {data.child_name} (przewidywany termin porodu: {_d(data.child_date)})"
    )
    period = f"w okresie od {_d(data.leave_start)} do {_d(data.leave_end)}"
    if kind == "URLOP-MAC-ROD":
        text = f"Zwracam się z wnioskiem o udzielenie mi urlopu macierzyńskiego {period}, {child}."
        paras = [text]
        if data.parental_weeks:
            paras.append(
                f"Jednocześnie wnoszę o udzielenie mi, bezpośrednio po zakończeniu urlopu macierzyńskiego, "
                f"urlopu rodzicielskiego w wymiarze {data.parental_weeks} tygodni."
            )
        return paras
    if kind == "URLOP-ROD":
        return [f"Zwracam się z wnioskiem o udzielenie mi urlopu rodzicielskiego {period}, {child}."]
    if kind == "URLOP-OJC":
        return [f"Zwracam się z wnioskiem o udzielenie mi urlopu ojcowskiego {period}, {child}."]
    if kind == "URLOP-UZUP":
        return [f"Zwracam się z wnioskiem o udzielenie mi uzupełniającego urlopu macierzyńskiego {period}, {child}."]
    if kind == "URLOP-ROD-PRACA":
        return [
            f"Zwracam się z wnioskiem o łączenie korzystania z urlopu rodzicielskiego z wykonywaniem pracy "
            f"u Państwa w wymiarze nie większym niż połowa wymiaru czasu pracy {period}, {child}."
        ]
    if kind == "REZYGNACJA-MAC":
        return [
            "Informuję, że rezygnuję z dalszej części urlopu macierzyńskiego po wykorzystaniu co najmniej 14 tygodni "
            f"tego urlopu. Urlop macierzyński zakończy się {_d(data.leave_end)}, {child}."
        ]
    raise DomainError(404, "Nieznany rodzaj wniosku do pracodawcy.")


def render_employer_application(kind: str, data: EmployerData) -> bytes:
    if kind not in TITLES:
        raise DomainError(404, "Nieznany rodzaj wniosku do pracodawcy.")
    pdf = FPDF(format="A4")
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(True, margin=25)
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_title(TITLES[kind])
    pdf.add_page()
    width = pdf.epw

    today = data.today or date.today()
    place = f"{data.city}, " if data.city else ""
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(width, 7, f"{place}{_d(today)}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(width, 6, f"{data.first_name} {data.last_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    if data.applicant_address:
        pdf.multi_cell(width * 0.55, 5, data.applicant_address, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_x(pdf.l_margin + width * 0.5)
    pdf.multi_cell(width * 0.5, 6, "Pracodawca:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_x(pdf.l_margin + width * 0.5)
    pdf.multi_cell(width * 0.5, 6, data.employer_name, new_x="LMARGIN", new_y="NEXT")
    if data.employer_address:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_x(pdf.l_margin + width * 0.5)
        pdf.multi_cell(width * 0.5, 5, data.employer_address, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)

    pdf.set_font("DejaVu", "B", 13)
    pdf.multi_cell(width, 7, TITLES[kind], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("DejaVu", "", 11)
    for paragraph in _body(kind, data):
        pdf.multi_cell(width, 6.5, paragraph, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    pdf.ln(2)
    pdf.multi_cell(width, 6.5, "Proszę o uwzględnienie wniosku i potwierdzenie jego otrzymania.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(18)

    pdf.set_x(pdf.l_margin + width * 0.55)
    pdf.cell(width * 0.45, 6, "……………………………………", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    pdf.set_x(pdf.l_margin + width * 0.55)
    pdf.cell(width * 0.45, 5, f"{data.first_name} {data.last_name}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(
        width,
        4,
        "Wniosek wygenerowany w aplikacji mRodzina na podstawie danych podanych przez wnioskodawcę, "
        "zgodnie z wzorem wniosków pracowniczych (rozporządzenie MRPiPS z 11.03.2025 r., Dz.U. 2025 poz. 322).",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())
