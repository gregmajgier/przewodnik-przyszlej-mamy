"""Odpowiedzi trybu demo (bez Azure) dla funkcji AI planu 04.

`contract_scan`: proste regexy na tekście umowy (etykiety „Pracodawca:”, „Stanowisko:” itd., jak w
`scripts/make_sample_contract.py`). Działa dla przykładowej umowy Anny Nowak i podobnych plików tekstowych.
"""

import re
from datetime import date

from ..ai.llm import LLMMessage, register_demo_handler
from ..services.contract_extract import FEATURE as CONTRACT_SCAN
from ..services.contract_extract import ExtractionResult

_DATE = r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})"


def _label(text: str, *labels: str) -> str | None:
    for label in labels:
        m = re.search(rf"^\s*{label}\s*:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1)
    return None


def _date(value: str | None) -> date | None:
    m = re.search(_DATE, value or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _money(value: str | None) -> float | None:
    m = re.search(r"(\d[\d\s]*(?:[.,]\d{1,2})?)\s*zł", value or "")
    if not m:
        return None
    return float(m.group(1).replace(" ", "").replace(",", "."))


def _fte(value: str | None) -> float | None:
    if not value:
        return None
    v = value.casefold()
    if "pełn" in v:
        return 1.0
    m = re.search(r"(\d+)\s*/\s*(\d+)", v)
    if m and int(m.group(2)):
        return int(m.group(1)) / int(m.group(2))
    return None


def parse_contract_text(text: str) -> ExtractionResult:
    low = text.casefold()
    if "umowa o pracę" in low or "umowa o prace" in low:
        kind = "employment"
    elif "zleceni" in low:
        kind = "mandate"
    elif "działalnoś" in low or "b2b" in low:
        kind = "jdg"
    else:
        return ExtractionResult(is_contract=False)

    period = _label(text, "Okres zatrudnienia", "Okres umowy", "Czas trwania") or ""
    indefinite: bool | None = None
    end_date = None
    if "nieokreślony" in period.casefold():
        indefinite = True
    elif period:
        indefinite = False
        end_date = _date(period)

    sickness = _label(text, "Dobrowolne ubezpieczenie chorobowe")
    voluntary = None
    if sickness:
        voluntary = sickness.strip().casefold().startswith("tak")

    return ExtractionResult(
        kind=kind,
        employer_name=_label(text, "Pracodawca", "Zleceniodawca", "Zamawiający"),
        employer_address=_label(text, "Adres pracodawcy", "Adres zleceniodawcy", "Adres"),
        employer_email=_label(text, "E-mail kadr", "E-mail"),
        position=_label(text, "Stanowisko", "Przedmiot umowy"),
        fte=_fte(_label(text, "Wymiar etatu")) if kind == "employment" else None,
        gross_monthly=_money(_label(text, "Wynagrodzenie")),
        start_date=_date(_label(text, "Data rozpoczęcia pracy", "Data rozpoczęcia", "Data zawarcia")),
        end_date=end_date,
        indefinite=indefinite,
        voluntary_sickness=voluntary if kind == "mandate" else None,
    )


def _contract_scan(messages: list[LLMMessage]) -> ExtractionResult:
    user = next((m for m in reversed(messages) if m.role == "user"), None)
    if user is None or user.images:
        # zdjęcia nie odczytamy bez modelu — pusty wynik = „nie udało się odczytać”
        return ExtractionResult()
    return parse_contract_text(user.content or "")


register_demo_handler(CONTRACT_SCAN, _contract_scan)
