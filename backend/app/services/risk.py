"""Reguły ryzyka utraty świadczeń z umów, ZUS i dzieci (spec §5.2, §10). Czysta funkcja, bez I/O.

Wszystkie reguły dotyczą rodziny z dzieckiem w drodze (status `expected` z terminem porodu).
Treści prawne są orientacyjne — w tekstach prosimy o weryfikację w ZUS/u pracodawcy.
"""

import hashlib
import re
from datetime import date, timedelta

from ..models.contract import Contract, Risk
from ..models.family import Child
from ..models.profile import ParentProfile

SEVERITY_ORDER = {"high": 0, "medium": 1, "info": 2}
VOLUNTARY_SICKNESS_LEAD_DAYS = 90  # karencja dobrowolnego ubezpieczenia chorobowego


def normalize_name(name: str | None) -> str:
    """Do porównań nazw płatników/pracodawców: małe litery, bez interpunkcji i podwójnych spacji."""
    return re.sub(r"[^\w]+", " ", (name or "").casefold()).strip()


def _slug(name: str | None) -> str:
    return hashlib.sha1(normalize_name(name).encode()).hexdigest()[:8]


def _due_child(children: list[Child]) -> Child | None:
    expected = [c for c in children if c.status == "expected" and c.due_date]
    return min(expected, key=lambda c: (c.due_date, c.id)) if expected else None


def _fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _money(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " zł"


def _fixed_term_risk(profile: ParentProfile, c: Contract, child: Child) -> Risk | None:
    if c.kind != "employment" or c.end_date is None or c.indefinite is True:
        return None
    if c.end_date >= child.due_date:
        return None
    return Risk(
        id=f"fixed-term:{profile.user_id}:{c.id}:{child.id}",
        severity="info",
        title="Umowa na czas określony kończy się przed terminem porodu",
        explanation=(
            f"Twoja umowa o pracę ({c.employer_name or 'bez nazwy pracodawcy'}) kończy się {_fmt(c.end_date)}, "
            f"a termin porodu to {_fmt(child.due_date)}. Umowa na czas określony, która upływa po trzecim miesiącu "
            "ciąży, zwykle przedłuża się do dnia porodu (art. 177 Kodeksu pracy). To dobra wiadomość, "
            "ale zweryfikuj to z pracodawcą."
        ),
        action="Poinformuj pracodawcę o ciąży i dostarcz zaświadczenie lekarskie, zanim umowa wygaśnie.",
        deadline=c.end_date,
        user_id=profile.user_id,
        source_ref=c.id,
    )


def _mandate_risk(
    profile: ParentProfile, child: Child, source_ref: str, employer: str | None, today: date
) -> Risk:
    latest = child.due_date - timedelta(days=VOLUNTARY_SICKNESS_LEAD_DAYS)
    deadline = latest if latest >= today else None
    late_note = (
        " Termin na spokojne zgłoszenie mógł już minąć. Zapytaj w ZUS, czy nadal możesz to zrobić."
        if deadline is None
        else ""
    )
    return Risk(
        id=f"mandate-sickness:{profile.user_id}:{source_ref}:{child.id}",
        severity="high",
        title="Brak zasiłku macierzyńskiego przy umowie zlecenia",
        explanation=(
            f"Przy umowie zlecenia ({employer or 'bez nazwy zleceniodawcy'}) ubezpieczenie chorobowe jest "
            "dobrowolne. Bez niego nie dostaniesz zasiłku macierzyńskiego ani chorobowego. "
            "Zwykle trzeba mieć je co najmniej 90 dni przed porodem (zweryfikuj w ZUS)." + late_note
        ),
        action="Zgłoś się do dobrowolnego ubezpieczenia chorobowego (u zleceniodawcy lub w ZUS) jak najszybciej.",
        deadline=deadline,
        user_id=profile.user_id,
        source_ref=source_ref,
    )


def _debt_risk(profile: ParentProfile, child: Child, source_ref: str) -> Risk:
    debt = profile.contribution_debt
    return Risk(
        id=f"jdg-debt:{profile.user_id}:{source_ref}:{child.id}",
        severity="high",
        title="Zadłużenie składkowe może zablokować zasiłek",
        explanation=(
            f"ZUS widzi u Ciebie zaległość składkową: {_money(debt.amount)} (od {_fmt(debt.since)}). "
            "Przy działalności gospodarczej zadłużenie może odebrać prawo do zasiłku chorobowego "
            "i macierzyńskiego (zweryfikuj w ZUS)."
        ),
        action="Spłać zaległe składki albo poproś ZUS o układ ratalny, najlepiej przed terminem porodu.",
        deadline=child.due_date,
        user_id=profile.user_id,
        source_ref=source_ref,
    )


def evaluate_risks(
    profile: ParentProfile, contracts: list[Contract], children: list[Child], today: date
) -> list[Risk]:
    """Ostrzeżenia dla jednego rodzica. Bierze pod uwagę tylko jego zatwierdzone umowy."""
    child = _due_child(children)
    if child is None:
        return []
    mine = [c for c in contracts if c.confirmed and c.user_id == profile.user_id]
    risks: list[Risk] = []

    for c in mine:
        if (r := _fixed_term_risk(profile, c, child)) and c.end_date >= today:
            risks.append(r)
        if c.kind == "mandate" and c.voluntary_sickness is not True:
            risks.append(_mandate_risk(profile, child, c.id, c.employer_name, today))

    # zlecenia znane tylko z ZUS (bez zeskanowanej umowy u tego samego płatnika)
    scanned = {normalize_name(c.employer_name) for c in mine if c.kind == "mandate"}
    for ins in profile.insurance:
        if ins.kind == "mandate" and ins.voluntary_sickness is not True and normalize_name(ins.payer) not in scanned:
            risks.append(_mandate_risk(profile, child, f"zus:{_slug(ins.payer)}", ins.payer, today))

    jdg_contract = next((c for c in mine if c.kind == "jdg"), None)
    has_jdg = jdg_contract is not None or any(i.kind == "jdg" for i in profile.insurance)
    if profile.contribution_debt is not None and has_jdg:
        risks.append(_debt_risk(profile, child, jdg_contract.id if jdg_contract else "zus:debt"))

    risks.sort(key=lambda r: (SEVERITY_ORDER[r.severity], r.deadline or date.max, r.id))
    return risks
