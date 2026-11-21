import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

DATA = Path(__file__).resolve().parents[1] / "data"

router = APIRouter(prefix="/api", tags=["wnioski"])


@lru_cache
def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@router.get("/wnioski")
def lista_wnioskow():
    """Katalog wniosków: instytucja, kanał wysyłki, linki do PDF."""
    return _load("katalog_wnioskow_pdf.json")["wnioski"]


@router.get("/wnioski/{kod}")
def wniosek(kod: str):
    for w in _load("katalog_wnioskow_pdf.json")["wnioski"]:
        if w["kod"].lower() == kod.lower():
            return w
    raise HTTPException(404, "Nie ma wniosku o takim kodzie")


@router.get("/wnioski/{kod}/pdf")
def pusty_pdf(kod: str):
    """Pusty formularz pobrany skryptem scripts/pobierz_pdfy.py."""
    pliki = sorted((DATA / "wnioski_pdf").glob(f"{kod}_pdf_*.pdf"))
    if not pliki:
        raise HTTPException(404, "Brak PDF: uruchom scripts/pobierz_pdfy.py")
    return FileResponse(pliki[-1], media_type="application/pdf")


@router.get("/zmienne")
def zmienne():
    """Zmienne użytkownika (kontrakt v1.1: zagnieżdżone klucze, np. `ubezpieczenie.tytul`)."""
    return _load("zmienne_uzytkownika.json")["zmienne"]


@router.get("/parametry")
def parametry():
    """Stawki i limity z reguly_uprawnien.json (docelowo edytowane w panelu admina)."""
    reguly = _load("reguly_uprawnien.json")
    return {"drzewo": reguly["parametry_drzewo"], "lista": reguly["parametry"]}
