"""Wczytanie kontraktu danych: reguly_uprawnien.json, zmienne_uzytkownika.json, katalog_wnioskow_pdf.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Kontrakt:
    reguly: dict
    zmienne: dict
    katalog: dict

    @property
    def params(self) -> dict:
        """Drzewo parametrów (`param.*` w regułach)."""
        return self.reguly["parametry_drzewo"]

    @property
    def wersja(self) -> str:
        return self.reguly["meta"]["wersja"]


def _read(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_kontrakt() -> Kontrakt:
    return Kontrakt(_read("reguly_uprawnien.json"), _read("zmienne_uzytkownika.json"), _read("katalog_wnioskow_pdf.json"))
