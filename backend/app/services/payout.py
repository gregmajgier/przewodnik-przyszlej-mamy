"""Kto wypłaci zasiłek z ubezpieczenia chorobowego i gdzie złożyć dokumenty (wymaganie g zadania ZUS).

Art. 61 ustawy zasiłkowej: płatnik, który zgłasza do ubezpieczenia chorobowego więcej niż 20 osób
(`platnik.prog_ubezpieczonych`), sam ustala prawo do zasiłków i je wypłaca. Mniejszy płatnik przekazuje dokumenty
do ZUS (pracownik: Z-3, zleceniobiorca: Z-3a), a wypłaca ZUS. Osobie prowadzącej działalność zawsze wypłaca ZUS.

Czysta funkcja: dostaje świadczenie i profile rodziców, zwraca opis dla każdego pasującego tytułu ubezpieczenia.
Wynik nie zawiera PESEL-u ani kwot (PESEL służy tylko do odróżnienia mamy od taty).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..engine.derived import P
from ..engine.kontrakt import load_kontrakt
from ..models.benefit import Benefit
from ..models.profile import Insurance, ParentProfile

# Świadczenia z tym tagiem w katalogu wypłaca płatnik albo ZUS (zasiłki z ubezpieczenia chorobowego).
PAYOUT_TAG = "wyplata-platnik-zus"

TITLE_LABELS = {"employment": "umowa o pracę", "mandate": "umowa zlecenia", "jdg": "własna działalność"}

PaidBy = Literal["payer", "zus", "unknown", "none"]


class Payout(BaseModel):
    parent_name: str
    title: str
    payer: str
    paid_by: PaidBy
    headline: str
    why: str
    where: str


def payer_threshold() -> int:
    return int(P(load_kontrakt().params, "platnik.prog_ubezpieczonych"))


def _is_female(pesel: str) -> bool | None:
    """Płeć z PESEL-u (przedostatnia cyfra parzysta = kobieta); None, gdy numer jest niepoprawny."""
    return int(pesel[9]) % 2 == 0 if len(pesel) == 11 and pesel.isdigit() else None


def _concerns(benefit: Benefit, parent: ParentProfile) -> bool:
    """Urlop ojcowski dotyczy taty, zasiłek chorobowy w ciąży mamy, pozostałe obojga rodziców."""
    female = _is_female(parent.pesel)
    if female is None:
        return True
    if "tata" in benefit.tags:
        return not female
    if benefit.criteria.requires_pregnancy:
        return female
    return True


def _paid_by(ins: Insurance, threshold: int) -> PaidBy:
    if ins.kind in ("mandate", "jdg") and ins.voluntary_sickness is False:
        return "none"
    if ins.kind == "jdg":
        return "zus"
    if ins.payer_insured_count is None:
        return "unknown"
    return "payer" if ins.payer_insured_count > threshold else "zus"


def describe(ins: Insurance, sickness: bool, threshold: int) -> tuple[PaidBy, str, str, str]:
    """(kto wypłaca, nagłówek, dlaczego, gdzie złożyć) dla jednego tytułu ubezpieczenia."""
    paid_by = _paid_by(ins, threshold)
    payer = ins.payer
    big = f"{payer} zgłasza do ubezpieczenia chorobowego więcej niż {threshold} osób, więc sam ustala prawo do zasiłku i go wypłaca."
    small = f"{payer} zgłasza do ubezpieczenia chorobowego najwyżej {threshold} osób, więc zasiłek ustala i wypłaca ZUS."
    rule = (
        f"Płatnik, który zgłasza do ubezpieczenia chorobowego więcej niż {threshold} osób, wypłaca zasiłek sam. "
        "Mniejszy przekazuje dokumenty do ZUS i wtedy wypłaca ZUS."
    )

    if paid_by == "none":
        return (
            paid_by,
            "Z tego tytułu zasiłek nie przysługuje",
            "Nie widzimy dobrowolnego ubezpieczenia chorobowego, a bez niego zasiłku nie ma.",
            "Do ubezpieczenia chorobowego możesz przystąpić, ale prawo do zasiłku powstaje zwykle po 90 dniach.",
        )

    if ins.kind == "employment":
        if paid_by == "payer":
            where = (
                "Zwolnienie e-ZLA trafia do pracodawcy samo. Nic nie składasz w ZUS."
                if sickness
                else "Wniosek o urlop składasz w kadrach. Na tej podstawie pracodawca ustali i wypłaci zasiłek, w ZUS nic nie składasz."
            )
            return paid_by, "Zasiłek wypłaci pracodawca", big, where
        if paid_by == "zus":
            where = (
                "Zwolnienie e-ZLA trafia do ZUS i do pracodawcy samo. Za pierwsze 33 dni zwolnienia w roku płaci pracodawca "
                "(wynagrodzenie chorobowe), potem ZUS, któremu pracodawca przekaże zaświadczenie płatnika Z-3."
                if sickness
                else "Wniosek o urlop składasz w kadrach. Pracodawca prześle go do ZUS razem z zaświadczeniem płatnika Z-3, "
                "a ZUS wypłaci zasiłek."
            )
            return paid_by, "Zasiłek wypłaci ZUS", small, where
        return (
            paid_by,
            "Zasiłek wypłaci pracodawca albo ZUS",
            rule,
            "Dokumenty i tak składasz u pracodawcy, w kadrach. Zapytaj tam, kto wypłaci zasiłek.",
        )

    if ins.kind == "mandate":
        if paid_by == "payer":
            where = (
                "Zwolnienie e-ZLA trafia do zleceniodawcy samo i na jego podstawie wypłaci zasiłek."
                if sickness
                else "Wniosek ZAM składasz u zleceniodawcy, a on ustali i wypłaci zasiłek."
            )
            return paid_by, "Zasiłek wypłaci zleceniodawca", big, where
        if paid_by == "zus":
            where = (
                "Zwolnienie e-ZLA trafia do ZUS samo. Zleceniodawca przekaże do ZUS zaświadczenie płatnika Z-3a."
                if sickness
                else "Wniosek ZAM złóż w ZUS (np. przez eZUS) albo u zleceniodawcy. Zleceniodawca prześle do ZUS "
                "zaświadczenie płatnika Z-3a."
            )
            return paid_by, "Zasiłek wypłaci ZUS", small, where
        return (
            paid_by,
            "Zasiłek wypłaci zleceniodawca albo ZUS",
            rule,
            "Zapytaj zleceniodawcę, ile osób zgłasza do ubezpieczenia chorobowego. Jeśli więcej niż "
            f"{threshold}, dokumenty składasz u niego. Jeśli mniej, w ZUS, a zleceniodawca prześle zaświadczenie Z-3a.",
        )

    # własna działalność: zawsze ZUS
    where = (
        "Zwolnienie e-ZLA trafia do ZUS samo. Do ZUS złóż też wniosek o zasiłek chorobowy ZAS-53."
        if sickness
        else "Wniosek ZAM składasz bezpośrednio w ZUS, np. przez eZUS."
    )
    return paid_by, "Zasiłek wypłaci ZUS", "Przy własnej działalności zasiłki zawsze wypłaca ZUS.", where


def payouts_for(benefit: Benefit, parents: list[ParentProfile], threshold: int | None = None) -> list[Payout]:
    """Opis wypłaty dla każdego tytułu ubezpieczenia rodziców, którego dotyczy świadczenie. Puste dla świadczeń
    bez tagu `PAYOUT_TAG` (np. 800+ czy świadczenia gminne)."""
    if PAYOUT_TAG not in benefit.tags:
        return []
    limit = payer_threshold() if threshold is None else threshold
    kinds = benefit.criteria.employment_kinds
    sickness = "ezla" in benefit.tags
    out: list[Payout] = []
    for parent in parents:
        if not _concerns(benefit, parent):
            continue
        for ins in parent.insurance:
            if kinds and ins.kind not in kinds:
                continue
            paid_by, headline, why, where = describe(ins, sickness, limit)
            out.append(
                Payout(
                    parent_name=parent.first_name,
                    title=TITLE_LABELS[ins.kind],
                    payer=ins.payer,
                    paid_by=paid_by,
                    headline=headline,
                    why=why,
                    where=where,
                )
            )
    return out
