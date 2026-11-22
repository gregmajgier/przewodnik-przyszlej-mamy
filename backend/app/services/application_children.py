"""Którego dziecka może dotyczyć wniosek (wiek dziecka, ciąża), zgodnie z materiałami ZUS i Kodeksem pracy.

`child_block_reason(code, child, siblings, today)` zwraca None, gdy wniosek o to dziecko ma sens, albo polski
komunikat, dlaczego nie. Limity pochodzą z parametrów silnika (`reguly_uprawnien.json`), więc zmiana w przepisach
to zmiana jednego parametru. Dzieci po stracie obsługuje osobno logika trybu jaskółki (`loss_forms`).
"""

from __future__ import annotations

from datetime import date

from ..engine.derived import P, wymiar_macierzynskiego_tyg
from ..engine.kontrakt import load_kontrakt
from ..models.family import Child
from .matching import age_in_months, age_phrase

ADULT_MONTHS = 18 * 12 - 1  # 800+: do ukończenia 18 lat (pełne miesiące, granica włącznie)
ADOPTION_MAX_MONTHS_KEY = "urlop.ojcowski_adopcja_max_wiek_dziecka_lat"


def _params() -> dict:
    return load_kontrakt().params


def _born_together(child: Child, siblings: list[Child]) -> int:
    """Liczba dzieci z jednego porodu (ta sama data urodzenia) — od niej zależy wymiar urlopu macierzyńskiego."""
    return max(1, sum(1 for c in siblings if c.status == "born" and c.birth_date == child.birth_date))


def _maternity_days(child: Child, siblings: list[Child], params: dict) -> int:
    return wymiar_macierzynskiego_tyg(_born_together(child, siblings), params) * 7


def _end_of_parental_window(child: Child, params: dict) -> date:
    """Urlop rodzicielski: do końca roku kalendarzowego, w którym dziecko kończy 6 lat."""
    return date(child.birth_date.year + P(params, "urlop.rodzicielski_do_konca_roku_wiek_dziecka"), 12, 31)  # type: ignore[union-attr]


def child_block_reason(code: str, child: Child, siblings: list[Child], today: date) -> str | None:
    params = _params()
    name = child.name
    expected = child.status == "expected" or child.birth_date is None
    months = None if expected else age_in_months(child.birth_date, today)  # type: ignore[arg-type]
    days = None if expected else (today - child.birth_date).days  # type: ignore[operator]
    adoption_months = P(params, ADOPTION_MAX_MONTHS_KEY) * 12 - 1

    if code == "URLOP-OJC":
        if expected:
            return None
        limit = P(params, "urlop.ojcowski_max_wiek_dziecka_mies")
        if child.foster and months <= adoption_months:
            return None
        if months >= limit:
            return (
                f"Urlop ojcowski można wykorzystać do ukończenia przez dziecko {limit} miesięcy, "
                f"a {name} ma {age_phrase(months)}."
            )
        return None

    if code in ("URLOP-MAC-ROD", "REZYGNACJA-MAC", "URLOP-UZUP"):
        if expected:
            if code == "URLOP-MAC-ROD":
                return None
            return "Ten wniosek składa się po porodzie."
        if days >= _maternity_days(child, siblings, params):
            return f"Urlop macierzyński na {name} już się skończył, więc ten wniosek nie jest potrzebny."
        return None

    if code in ("URLOP-ROD", "URLOP-ROD-PRACA", "ZAM"):
        if expected:
            return None
        if child.foster and months <= adoption_months:
            return None
        end = _end_of_parental_window(child, params)
        if today > end:
            return (
                f"Urlop rodzicielski i zasiłek za niego przysługują do końca roku, w którym dziecko kończy 6 lat. "
                f"Dla {name} ten termin minął {end.strftime('%d.%m.%Y')}."
            )
        return None

    if code == "800PLUS":
        if expected:
            return "Wniosek o 800+ złożysz po urodzeniu dziecka."
        if months > ADULT_MONTHS:
            return f"800+ przysługuje do ukończenia przez dziecko 18 lat, a {name} ma {age_phrase(months)}."
        return None

    if code == "ZA-ZYCIEM":
        if expected:
            return "Wniosek o jednorazowe 4000 zł „Za życiem” składa się po urodzeniu dziecka."
        if months >= 12:
            return "Wniosek „Za życiem” trzeba złożyć w ciągu 12 miesięcy od urodzenia dziecka."
        if not child.serious_illness:
            return (
                f"Ten wniosek wymaga zaświadczenia o ciężkiej chorobie dziecka. Zaznacz to przy {name} "
                "w zakładce „Rodzina”, jeśli je masz."
            )
        return None

    if code == "AKTYWNY-RODZIC":
        lo = P(params, "swiadczenia.aktywny_rodzic_wiek_od_mies")
        hi = P(params, "swiadczenia.aktywny_rodzic_wiek_do_mies")
        if expected:
            return "Program „Aktywny rodzic” dotyczy dzieci od 12. do 35. miesiąca życia."
        if not lo <= months <= hi:
            return f"Program „Aktywny rodzic” dotyczy dzieci od {lo} do {hi} miesięcy, a {name} ma {age_phrase(months)}."
        return None

    return None
