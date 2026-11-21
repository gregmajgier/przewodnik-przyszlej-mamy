"""Pobiera wszystkie PDF-y z katalog_wnioskow_pdf.json do folderu app/data/wnioski_pdf
i zapisuje nazwy pól formularzy (AcroForm) do app/data/wnioski_pdf/pola_formularzy.json.

Użycie:
    pip install requests pypdf
    cd backend && python scripts/pobierz_pdfy.py
"""
import json
import pathlib
import re

import requests
from pypdf import PdfReader

DATA = pathlib.Path(__file__).resolve().parents[1] / "app" / "data"
KATALOG = DATA / "katalog_wnioskow_pdf.json"
OUT = DATA / "wnioski_pdf"
OUT.mkdir(exist_ok=True)

katalog = json.loads(KATALOG.read_text(encoding="utf-8"))
pola = {}

for w in katalog["wnioski"]:
    for wariant in ("pdf_do_druku", "pdf_wypelnij_i_wydrukuj"):
        url = w.get(wariant)
        if not url:
            continue
        nazwa = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{w['kod']}_{wariant}") + ".pdf"
        plik = OUT / nazwa
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                print(f"[!] {w['kod']} {wariant}: to nie jest PDF (sprawdź stronę formularza)")
                continue
            plik.write_bytes(r.content)
            fields = PdfReader(plik).get_fields() or {}
            pola[nazwa] = sorted(fields.keys())
            print(f"[ok] {nazwa}: {len(fields)} pól")
        except Exception as e:
            print(f"[x] {w['kod']} {wariant}: {e}")

(OUT / "pola_formularzy.json").write_text(
    json.dumps(pola, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Gotowe. Nazwy pól w wnioski_pdf/pola_formularzy.json")
