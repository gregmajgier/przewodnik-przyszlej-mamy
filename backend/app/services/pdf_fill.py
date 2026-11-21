"""Wypełnianie formularzy PDF z polami AcroForm (wersje „wypełnij i wydrukuj” ZUS) wg map z `form_field_maps/`."""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

from ..errors import DomainError
from .prefill import DATA, FormField, form_schema, load_map

logger = logging.getLogger("mrodzina.pdf")


def _to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def format_value(field: FormField, value: Any) -> str | None:
    """Tekst wpisywany do pola PDF (pola „grzebieniowe” ZUS wymagają samych cyfr). `None` = nie wypełniaj."""
    if field.type == "bool":
        return field.on_value if value is True else None
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field.format in ("digits", "pesel"):
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return digits or None
    if field.type == "date" or field.format == "date_digits":
        d = _to_date(value)
        if d is None:
            return str(value)
        return d.strftime("%d%m%Y") if field.format == "date_digits" else d.strftime("%d.%m.%Y")
    text = str(value).strip()
    return text.upper() if field.uppercase else text


def fill_pdf(code: str, values: dict[str, Any]) -> bytes:
    """Zwraca wypełniony PDF. Nieznany kod lub formularz bez pól AcroForm -> `DomainError`."""
    mapping = load_map(code)
    if mapping is None:
        raise DomainError(404, "Nie ma takiego formularza PDF.")
    if not mapping["pdf"]:
        raise DomainError(422, "Ten formularz nie ma wersji PDF do automatycznego wypełnienia.")
    fields = {f.id: f for f in form_schema(code)}
    to_write: dict[str, str] = {}
    for fid, value in values.items():
        field = fields.get(fid)
        if field is None or not field.pdf_field:
            continue  # wartości spoza mapy (np. pola pomocnicze) są ignorowane
        text = format_value(field, value)
        if text is not None:
            to_write[field.pdf_field] = text

    reader = PdfReader(DATA / "wnioski_pdf" / mapping["pdf"])
    writer = PdfWriter(clone_from=reader)
    if to_write:
        for page in writer.pages:
            try:
                writer.update_page_form_field_values(page, to_write, auto_regenerate=False)
            except Exception as e:  # noqa: BLE001 — strona bez pól; treść pól nie trafia do logów
                logger.debug("Pominięto stronę przy wypełnianiu %s: %s", code, type(e).__name__)
    # przeglądarki/Acrobat przerysują wygląd pól (polskie znaki, pola „grzebieniowe”)
    writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
