"""Wstępne wypełnianie wniosków danymi z profilu rodziny.

Źródła wartości pola (`source_key`):
- `applicant.<atrybut>` — dane zalogowanego rodzica (ZUS/mObywatel),
- `answers.<klucz>`     — odpowiedzi zapisane w profilu rodzica (np. ulica, nr domu; nie pytamy drugi raz),
- `child.<atrybut>`     — dziecko, którego dotyczy wniosek,
- `calc.<nazwa>`        — wartości wyliczane (okres urlopu, opis dziecka),
- `const.<nazwa>`       — stałe,
- brak (`null`)         — wartość wyłącznie z odpowiedzi do tego wniosku (`answers[field_id]`).

Odpowiedź przekazana w `answers` pod `id` pola zawsze ma pierwszeństwo (rodzic mógł edytować pole w podglądzie).
Brak wymaganej wartości nie powoduje błędu ani pustego pola w PDF — trafia na listę `missing` (pytania).
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..errors import DomainError
from ..models.family import Child, FamilyView
from ..models.profile import ParentProfile

DATA = Path(__file__).resolve().parents[1] / "data"
MAPS_DIR = DATA / "form_field_maps"

EMPLOYER_KINDS = ("URLOP-MAC-ROD", "URLOP-ROD", "URLOP-OJC", "URLOP-UZUP", "URLOP-ROD-PRACA", "REZYGNACJA-MAC")

# kody wniosków składanych przez makietę portalu (agent) -> identyfikator portalu
CODE_TO_PORTAL = {
    "800PLUS": "pue_800plus",
    "DOBRY-START": "pue_dobry_start",
    "AKTYWNY-RODZIC": "pue_aktywny_rodzic",
    "ZAM": "pue_zam",
    "ZAS-53": "pue_zas_53",
    "ZAS-55": "pue_zas_55",
    "ZNp-7": "pue_znp_7",
    "Z-10": "pue_z_10",
    "ZAS-26": "pue_zas_26",
    "ZAS-33": "pue_zas_33",
    "ZAS-39": "pue_zas_39",
    "KDR": "emp_kdr",
    "ZA-ZYCIEM": "emp_za_zyciem",
}

MATERNITY_WEEKS = 20  # jedno dziecko; domyślne podpowiedzi, rodzic potwierdza w podglądzie


class FormField(BaseModel):
    id: str
    label: str
    type: Literal["text", "date", "bool", "choice"] = "text"
    required: bool = False
    required_when: Literal["born", "expected"] | None = None  # wymagane tylko dla dziecka urodzonego / w drodze
    source_key: str | None = None
    choices: list[str] | None = None
    default: Any = None
    # tylko dla map PDF
    pdf_field: str | None = None
    format: str | None = None
    uppercase: bool = False
    on_value: str = "/1"


class Question(BaseModel):
    field_id: str
    label: str
    type: Literal["text", "date", "bool", "choice"] = "text"
    choices: list[str] | None = None


class PrefillResult(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    missing: list[Question] = Field(default_factory=list)


# ---------- schematy formularzy ----------


@lru_cache
def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_map(code: str) -> dict | None:
    """Surowa mapa pól PDF (`form_field_maps/<kod>.json`) albo `None`."""
    path = MAPS_DIR / f"{code}.json"
    return _read_json(path) if path.is_file() and path.resolve().parent == MAPS_DIR.resolve() else None


def map_codes() -> list[str]:
    return sorted(p.stem for p in MAPS_DIR.glob("*.json"))


def _portals() -> dict[str, dict]:
    return _read_json(DATA / "portal_schemas.json")["portals"]


def portal_schema(portal_id: str) -> list[FormField]:
    portal = _portals().get(portal_id)
    if portal is None:
        raise DomainError(404, "Nie ma takiej makiety portalu.")
    if "extends_form" in portal:
        return form_schema(portal["extends_form"])
    return [FormField.model_validate(f) for f in portal["fields"]]


def portal_meta(portal_id: str) -> dict:
    portal = _portals().get(portal_id)
    if portal is None:
        raise DomainError(404, "Nie ma takiej makiety portalu.")
    return {k: v for k, v in portal.items() if k != "fields"}


def _employer_schema(code: str) -> list[FormField]:
    fields = [
        FormField(id="first_name", label="Imię", required=True, source_key="applicant.first_name"),
        FormField(id="last_name", label="Nazwisko", required=True, source_key="applicant.last_name"),
        FormField(id="employer_name", label="Nazwa pracodawcy", required=True, source_key="applicant.payer_name"),
        FormField(id="child_name", label="Imię dziecka", required=True, source_key="child.first_name"),
        FormField(id="child_date", label="Data urodzenia lub przewidywanego porodu", type="date", required=True,
                  source_key="calc.child_date"),
    ]
    if code == "URLOP-MAC-ROD":
        fields += [
            FormField(id="leave_start", label="Początek urlopu macierzyńskiego", type="date", required=True,
                      source_key="calc.leave_start"),
            FormField(id="leave_end", label="Koniec urlopu macierzyńskiego", type="date", required=True,
                      source_key="calc.leave_end"),
            FormField(id="parental_weeks", label="Liczba tygodni urlopu rodzicielskiego bezpośrednio po macierzyńskim",
                      required=True, default="32"),
        ]
    elif code == "REZYGNACJA-MAC":
        fields += [
            FormField(id="leave_end", label="Ostatni dzień urlopu macierzyńskiego", type="date", required=True),
        ]
    else:
        fields += [
            FormField(id="leave_start", label="Początek urlopu", type="date", required=True),
            FormField(id="leave_end", label="Koniec urlopu", type="date", required=True),
        ]
    fields.append(FormField(id="employer_email", label="Adres e-mail pracodawcy (dział kadr)", source_key="answers.employer_email"))
    return fields


def form_schema(code: str) -> list[FormField]:
    """Pola wniosku: z mapy PDF, wbudowanego schematu wniosków do pracodawcy albo schematu makiety portalu."""
    m = load_map(code)
    if m is not None:
        return [FormField.model_validate(f) for f in m["fields"]]
    if code in EMPLOYER_KINDS:
        return _employer_schema(code)
    portal_id = CODE_TO_PORTAL.get(code)
    if portal_id:
        return portal_schema(portal_id)
    raise DomainError(422, "Dla tego wniosku nie ma jeszcze kreatora w aplikacji.")


_CHILD_CALCS = {
    "calc.child_date", "calc.leave_start", "calc.leave_end", "calc.maternity_period", "calc.child_details", "calc.is_expected",
}


def requires_child(code: str) -> bool:
    """Czy wniosek dotyczy konkretnego dziecka (wtedy przy tworzeniu trzeba podać `child_id`)."""
    return any((f.source_key or "").startswith("child.") or f.source_key in _CHILD_CALCS for f in form_schema(code))


def recommend_flow(insurance_kind: str | None) -> list[str]:
    """Kolejność wniosków: pracownik → najpierw urlop u pracodawcy, potem ZAM; zlecenie/JDG → od razu ZAM."""
    if insurance_kind == "employment":
        return ["URLOP-MAC-ROD", "ZAM"]
    return ["ZAM"]


# ---------- rozwiązywanie wartości ----------


class _Ctx(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    applicant: ParentProfile
    partner: ParentProfile | None
    children: list[Child]
    child: Child | None
    answers: dict[str, Any]
    today: date


def _fmt_dmy(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _child_date(child: Child | None) -> date | None:
    if child is None:
        return None
    return child.birth_date if child.status == "born" and child.birth_date else (child.due_date or child.birth_date)


def _calc(name: str, ctx: _Ctx) -> Any:
    child = ctx.child
    if name == "child_date":
        d = _child_date(child)
        return d.isoformat() if d else None
    if name == "leave_start":
        d = _child_date(child)
        return d.isoformat() if d else None
    if name == "leave_end":
        d = _child_date(child)
        return (d + timedelta(weeks=MATERNITY_WEEKS) - timedelta(days=1)).isoformat() if d else None
    if name == "maternity_period":
        d = _child_date(child)
        if d is None:
            return None
        return f"{_fmt_dmy(d)} – {_fmt_dmy(d + timedelta(weeks=MATERNITY_WEEKS) - timedelta(days=1))}"
    if name == "child_details":
        if child is None or child.status != "born" or not child.birth_date:
            return None
        return f"{child.name} {ctx.applicant.last_name}, ur. {_fmt_dmy(child.birth_date)}"
    if name == "is_expected":
        return bool(child is not None and child.status == "expected")
    if name == "children_count":
        live = [c for c in ctx.children if c.situation != "loss"]
        return str(len(live)) if live else None
    return None


def _resolve(field: FormField, ctx: _Ctx) -> Any:
    key = field.source_key
    if key is None:
        return field.default
    scope, _, attr = key.partition(".")
    if scope == "applicant":
        a = ctx.applicant
        if attr == "city":
            return a.address.city or None
        if attr == "postal_code":
            return a.address.postal_code or None
        if attr == "payer_name":
            return a.insurance[0].payer if a.insurance else None
        if attr == "birth_date":
            return a.birth_date.isoformat()
        return getattr(a, attr, None)
    if scope == "answers":
        value = ctx.answers.get(attr)
        return value if value not in ("", None) else field.default
    if scope == "child":
        c = ctx.child
        if c is None:
            return None
        if attr == "first_name":
            return c.name
        if attr == "last_name":
            return ctx.applicant.last_name
        value = getattr(c, attr, None)
        return value.isoformat() if isinstance(value, date) else value
    if scope == "calc":
        return _calc(attr, ctx)
    if scope == "const":
        return {"true": True, "country": "Polska"}.get(attr)
    return None


def _is_required(field: FormField, child: Child | None) -> bool:
    if field.required:
        return True
    if field.required_when == "born":
        return child is not None and child.status == "born"
    if field.required_when == "expected":
        return child is not None and child.status == "expected"
    return False


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _select_child(view: FamilyView, child_id: str | None) -> Child | None:
    if child_id is None:
        return None
    for c in view.children:
        if c.id == child_id:
            return c
    raise DomainError(404, "Nie znaleziono takiego dziecka.")


def _build_ctx(
    view: FamilyView, profiles: list[ParentProfile], child_id: str | None, answers: dict, applicant_id: str | None
) -> _Ctx:
    if not profiles:
        raise DomainError(404, "Nie znaleziono profilu rodzica.")
    applicant = next((p for p in profiles if p.user_id == applicant_id), profiles[0])
    partner = next((p for p in profiles if p.user_id != applicant.user_id), None)
    merged: dict[str, Any] = {}
    if partner:
        merged.update(partner.answers)
    merged.update(applicant.answers)  # odpowiedzi wnioskodawcy mają pierwszeństwo
    merged.update(answers)
    return _Ctx(
        applicant=applicant,
        partner=partner,
        children=list(view.children),
        child=_select_child(view, child_id),
        answers=merged,
        today=date.today(),
    )


def prefill_fields(
    fields: list[FormField],
    family_view: FamilyView,
    profiles: list[ParentProfile],
    child_id: str | None = None,
    answers: dict | None = None,
    applicant_id: str | None = None,
) -> PrefillResult:
    answers = answers or {}
    ctx = _build_ctx(family_view, profiles, child_id, answers, applicant_id)
    values: dict[str, Any] = {}
    missing: list[Question] = []
    for f in fields:
        value = answers[f.id] if f.id in answers and not _blank(answers[f.id]) else _resolve(f, ctx)
        if _blank(value):
            value = None
        if value is not None:
            values[f.id] = value
        elif _is_required(f, ctx.child):
            missing.append(Question(field_id=f.id, label=f.label, type=f.type, choices=f.choices))
    return PrefillResult(values=values, missing=missing)


def prefill(
    code: str,
    family_view: FamilyView,
    profiles: list[ParentProfile],
    child_id: str | None = None,
    answers: dict | None = None,
    applicant_id: str | None = None,
) -> PrefillResult:
    return prefill_fields(form_schema(code), family_view, profiles, child_id, answers, applicant_id)


def prefill_portal(
    portal_id: str,
    family_view: FamilyView,
    profiles: list[ParentProfile],
    child_id: str | None = None,
    answers: dict | None = None,
    applicant_id: str | None = None,
) -> PrefillResult:
    return prefill_fields(portal_schema(portal_id), family_view, profiles, child_id, answers, applicant_id)


# ---------- walidacja odpowiedzi ----------

_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]{2,}")


def valid_pesel(value: str) -> bool:
    if not (isinstance(value, str) and len(value) == 11 and value.isdigit()):
        return False
    check = (10 - sum(int(d) * w for d, w in zip(value, _PESEL_WEIGHTS)) % 10) % 10
    return check == int(value[10])


def validate_answer(field: FormField, value: Any) -> Any:
    """Normalizuje i waliduje odpowiedź na pytanie; błąd -> `DomainError(422)` po polsku."""
    if field.type == "bool":
        if not isinstance(value, bool):
            raise DomainError(422, f"Pole „{field.label}” wymaga odpowiedzi tak lub nie.")
        return value
    if not isinstance(value, str) or not value.strip():
        raise DomainError(422, f"Uzupełnij pole „{field.label}”.")
    text = value.strip()
    if field.type == "date":
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            raise DomainError(422, f"Pole „{field.label}” wymaga daty w formacie RRRR-MM-DD.") from None
    if field.type == "choice" and field.choices and text not in field.choices:
        raise DomainError(422, f"Pole „{field.label}”: wybierz jedną z dostępnych opcji.")
    if field.format == "email" or field.id.endswith("email"):
        if not _EMAIL_RE.fullmatch(text):
            raise DomainError(422, f"Pole „{field.label}”: podaj poprawny adres e-mail.")
        text = text.lower()
    elif field.format == "pesel" or field.id.endswith("pesel"):
        text = text.replace(" ", "")
        if not valid_pesel(text):
            raise DomainError(422, "Numer PESEL jest nieprawidłowy. Sprawdź go i spróbuj ponownie.")
    elif field.format == "digits":
        text = "".join(ch for ch in text if ch.isdigit())
        if not text:
            raise DomainError(422, f"Pole „{field.label}” powinno zawierać cyfry.")
    return text
