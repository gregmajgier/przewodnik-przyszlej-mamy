import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..storage import Store, get_store

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
async def parametry(store: Store = Depends(get_store)):
    """Stawki i limity silnika, z aktywnymi (demonstracyjnymi) zmianami panelu."""
    reguly = _load("reguly_uprawnien.json")
    from ..services.national_parameters import apply_overrides
    drzewo = apply_overrides(reguly["parametry_drzewo"], await _stored_overrides(store))
    lista = []
    for item in reguly["parametry"]:
        item_copy = dict(item)
        item_copy["wartosc"] = _value_at_path(drzewo, item["sciezka"], item["wartosc"])
        lista.append(item_copy)
    return {"drzewo": drzewo, "lista": lista}


async def _stored_overrides(store: Store) -> dict:
    doc = await store.get("engine_parameters", "national-active")
    return doc.get("overrides", {}) if doc else {}


def _value_at_path(tree: dict, path: str, fallback):
    node = tree
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return fallback
        node = node[part]
    return node
