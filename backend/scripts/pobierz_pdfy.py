"""Pobiera wszystkie PDF-y z katalog_wnioskow_pdf.json do folderu app/data/wnioski_pdf
i (jeśli zainstalowano pypdf) zapisuje nazwy pól formularzy do
app/data/wnioski_pdf/pola_formularzy.json.

Działa na samej bibliotece standardowej Pythona; pypdf jest opcjonalny.

Użycie (z folderu backend):
    python scripts/pobierz_pdfy.py
"""
import json
import pathlib
import re
import urllib.request

try:
    from pypdf import PdfReader
except ImportError:  # pypdf opcjonalny: bez niego tylko pobieramy pliki
    PdfReader = None

DATA = pathlib.Path(__file__).resolve().parents[1] / "app" / "data"
KATALOG = DATA / "katalog_wnioskow_pdf.json"
OUT = DATA / "wnioski_pdf"
OUT.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (przewodnik-przyszlej-mamy; hackathon)"}

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
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                dane = r.read()
            if not dane.startswith(b"%PDF"):
                print(f"[!] {w['kod']} {wariant}: to nie jest PDF (sprawdź stronę formularza)")
                continue
            plik.write_bytes(dane)
            if PdfReader:
                fields = PdfReader(plik).get_fields() or {}
                pola[nazwa] = sorted(fields.keys())
                print(f"[ok] {nazwa}: {len(fields)} pól")
            else:
                print(f"[ok] {nazwa}")
        except Exception as e:
            print(f"[x] {w['kod']} {wariant}: {e}")

if PdfReader:
    (OUT / "pola_formularzy.json").write_text(
        json.dumps(pola, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Gotowe. Nazwy pól w app/data/wnioski_pdf/pola_formularzy.json")
else:
    print("Gotowe. Aby wypisać pola formularzy, zainstaluj pypdf i uruchom ponownie.")
