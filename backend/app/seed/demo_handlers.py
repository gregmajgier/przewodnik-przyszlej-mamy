"""Odpowiedzi trybu demo (bez Azure): rejestrowane per funkcja przez `register_demo_handler`.

`contract_scan` czyta tekst umowy prostymi regexami (etykiety „Pracodawca:”, „Stanowisko:” itd.) —
tak działa przykładowa umowa Anny Nowak (`sample_umowa_anna_nowak.pdf`). Brak słowa „umowa” = nie umowa.
"""

import re
from datetime import date

from ..ai.llm import LLMMessage, register_demo_handler
from ..models.contract import ContractDraft


def _label(text: str, *labels: str) -> str | None:
    for label in labels:
        m = re.search(rf"^\s*{label}\s*:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1)
    return None


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
    else:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
        if not m:
            return None
        y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _parse_money(s: str | None) -> float | None:
    m = re.search(r"(\d[\d\s ]*(?:[.,]\d{1,2})?)", s or "")
    if not m:
        return None
    try:
        return float(re.sub(r"[\s ]", "", m.group(1)).replace(",", "."))
    except ValueError:
        return None


def _parse_fte(s: str | None) -> float | None:
    if not s:
        return None
    low = s.casefold()
    if "pełn" in low:
        return 1.0
    m = re.search(r"(\d+)\s*/\s*(\d+)", low)
    if m and int(m.group(2)):
        return int(m.group(1)) / int(m.group(2))
    return None


def contract_scan_demo(messages: list[LLMMessage]) -> ContractDraft:
    text = next((m.content or "" for m in reversed(messages) if m.role == "user"), "")
    low = text.casefold()
    if "umow" not in low:
        return ContractDraft()  # nie umowa -> usługa zwróci „Nie udało się odczytać umowy”
    if "zleceni" in low:
        kind = "mandate"
    elif "działalno" in low:
        kind = "jdg"
    else:
        kind = "employment"
    end = _parse_date(_label(text, "Do dnia", "Data zakończenia"))
    period = (_label(text, "Okres zatrudnienia", "Okres obowiązywania") or "").casefold()
    indefinite: bool | None = None
    if "nieokreślon" in period:
        indefinite = True
    elif end is not None or "określon" in period:
        indefinite = False
    return ContractDraft(
        kind=kind,
        employer_name=_label(text, "Pracodawca", "Zleceniodawca", "Zamawiający", "Firma"),
        employer_address=_label(text, "Adres pracodawcy", "Adres zleceniodawcy", "Adres"),
        employer_email=_label(text, "E-mail kadr", "E-mail", "Email"),
        position=_label(text, "Stanowisko"),
        fte=_parse_fte(_label(text, "Wymiar etatu")),
        gross_monthly=_parse_money(_label(text, "Wynagrodzenie")),
        start_date=_parse_date(_label(text, "Data rozpoczęcia pracy", "Data rozpoczęcia")),
        end_date=end,
        indefinite=indefinite,
    )


register_demo_handler("contract_scan", contract_scan_demo)
