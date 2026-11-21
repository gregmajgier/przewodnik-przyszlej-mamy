"""Generuje przykładową umowę o pracę Anny Nowak (dane wymyślone) do testów skanu w trybie demo.

Użycie (z katalogu backend/):
    .venv/bin/python scripts/make_sample_contract.py [--font /ścieżka/do/czcionki.ttf]

Plik wynikowy: app/seed/sample_umowa_anna_nowak.pdf. Wymaga `fpdf2` (requirements-dev.txt) oraz
czcionki TTF z polskimi znakami (DejaVu Sans / Arial / Liberation — szukamy w typowych miejscach).
"""

import argparse
import sys
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent.parent / "app" / "seed" / "sample_umowa_anna_nowak.pdf"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

# Etykiety w formacie „Etykieta: wartość” — demo-handler skanu czyta je prostymi regexami.
LINES = [
    ("title", "UMOWA O PRACĘ"),
    ("text", "zawarta w Krakowie dnia 15 listopada 2021 r. pomiędzy:"),
    ("text", ""),
    ("text", "Pracodawca: Krakowskie Centrum Usług Wspólnych Sp. z o.o."),
    ("text", "Adres pracodawcy: ul. Przykładowa 12, 31-001 Kraków"),
    ("text", "E-mail kadr: kadry@kcuw.example.pl"),
    ("text", ""),
    ("text", "a Panią Anną Nowak, zwaną dalej Pracownikiem."),
    ("text", ""),
    ("heading", "§ 1. Warunki zatrudnienia"),
    ("text", "Stanowisko: Specjalista ds. obsługi klienta"),
    ("text", "Wymiar etatu: pełny etat"),
    ("text", "Wynagrodzenie: 7850,00 zł brutto miesięcznie"),
    ("text", "Data rozpoczęcia pracy: 21.11.2021"),
    ("text", "Okres zatrudnienia: na czas nieokreślony"),
    ("text", ""),
    ("heading", "§ 2. Postanowienia końcowe"),
    ("text", "W sprawach nieuregulowanych niniejszą umową stosuje się przepisy Kodeksu pracy."),
    ("text", "Umowa została sporządzona w dwóch jednobrzmiących egzemplarzach."),
    ("text", ""),
    ("text", "Dokument wymyślony na potrzeby prototypu mRodzina — nie jest prawdziwą umową."),
]


def find_font(explicit: str | None) -> str:
    candidates = [explicit] if explicit else FONT_CANDIDATES
    for c in candidates:
        if c and Path(c).is_file():
            return c
    sys.exit("Nie znaleziono czcionki TTF z polskimi znakami. Podaj ją przez --font /ścieżka/do/plik.ttf")


def build(font_path: str) -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Sample", fname=font_path)
    for kind, text in LINES:
        pdf.set_font("Sample", size={"title": 18, "heading": 13}.get(kind, 11))
        pdf.multi_cell(0, 8, text, new_x="LMARGIN", new_y="NEXT", align="C" if kind == "title" else "L")
    return pdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    pdf = build(find_font(args.font))
    pdf.set_creation_date(None) if False else None  # data tworzenia jest w metadanych — nieistotna
    Path(args.out).write_bytes(bytes(pdf.output()))
    print(f"Zapisano {args.out}")


if __name__ == "__main__":
    main()
