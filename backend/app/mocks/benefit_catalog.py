"""MOCK planu 03 — katalog i (bardzo uproszczone) dopasowanie świadczeń.

Prawdziwy plan 03 daje `GET /api/benefits`, seed krajowy i `match_benefit`. Tu tylko:
- `visible_benefits(store, address)` — opublikowane świadczenia z kolekcji `benefits` widoczne pod adresem
  (zasięg jednostki przez `covers`) + przykładowe krajowe z `SAMPLE_NATIONAL`, jeśli w bazie nie ma krajowych;
- `naive_match(benefit, children, today)` — status `fits|maybe|no` tylko z wieku dziecka / ciąży.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from ..models.family import Child
from ..models.profile import Address
from ..storage import Store
from .benefit import Benefit, Criteria, Deadline
from .units import covers

MatchStatus = Literal["fits", "maybe", "no"]

SAMPLE_NATIONAL: list[Benefit] = [
    Benefit(
        id="mock-800plus",
        name="Świadczenie wychowawcze 800+",
        scope="national",
        description="800 zł miesięcznie na każde dziecko do 18. roku życia.",
        amount_text="800 zł / mies.",
        annual_value_estimate=9600,
        deadline=Deadline(anchor="birth", offset_months=3, note="Wniosek do 3 miesięcy od urodzenia — wtedy z wyrównaniem od urodzenia."),
        how_to_apply="Online przez PUE/eZUS lub bankowość elektroniczną.",
        form_codes=["800PLUS"],
        source_url="https://www.gov.pl/web/rodzina/swiadczenie-wychowawcze",
        criteria=Criteria(child_age_min_months=0, child_age_max_months=215),
        verify=True,
    ),
    Benefit(
        id="mock-becikowe",
        name="Jednorazowa zapomoga z tytułu urodzenia dziecka (becikowe)",
        scope="national",
        description="1000 zł jednorazowo po urodzeniu dziecka (kryterium dochodowe).",
        amount_text="1000 zł jednorazowo",
        annual_value_estimate=1000,
        deadline=Deadline(anchor="birth", offset_months=12, note="Do 12 miesięcy od urodzenia."),
        how_to_apply="Wniosek w gminie (MOPS/OPS).",
        form_codes=["BECIKOWE"],
        source_url="https://www.gov.pl/web/rodzina/becikowe",
        criteria=Criteria(child_age_min_months=0, child_age_max_months=11, max_income_per_person=1922),
        verify=True,
    ),
    Benefit(
        id="mock-zasilek-macierzynski",
        name="Zasiłek macierzyński",
        scope="national",
        description="Zasiłek za okres urlopu macierzyńskiego i rodzicielskiego.",
        amount_text="81,5–100% podstawy",
        deadline=Deadline(anchor="due", offset_days=-21, note="Wniosek o urlop składa się najpóźniej 21 dni przed porodem (zweryfikuj)."),
        how_to_apply="Pracownik — wniosek o urlop u pracodawcy; zlecenie/JDG — ZAM w ZUS.",
        form_codes=["URLOP-MAC-ROD", "ZAM"],
        source_url="https://www.zus.pl/swiadczenia/zasilki/zasilek-macierzynski",
        criteria=Criteria(requires_pregnancy=True),
        verify=True,
    ),
]


class BenefitWithMatch(BaseModel):
    benefit: Benefit
    status: MatchStatus


async def visible_benefits(store: Store, address: Address) -> list[Benefit]:
    units = {u["id"]: u for u in await store.find("units")}
    out: list[Benefit] = []
    for doc in await store.find("benefits", status="published"):
        b = Benefit.model_validate(doc)
        unit = units.get(b.unit_id) if b.unit_id else None
        if b.scope == "national" or (unit is not None and covers(unit, address)):
            out.append(b)
    if not any(b.scope == "national" for b in out):
        out.extend(SAMPLE_NATIONAL)
    return out


def _age_months(birth: date, today: date) -> int:
    months = (today.year - birth.year) * 12 + today.month - birth.month
    return months - (1 if today.day < birth.day else 0)


def naive_match(benefit: Benefit, children: list[Child], today: date) -> MatchStatus:
    c = benefit.criteria
    if c.requires_pregnancy:
        return "fits" if any(ch.status == "expected" for ch in children) else "no"
    if c.child_age_min_months is None and c.child_age_max_months is None:
        return "maybe"
    lo = c.child_age_min_months or 0
    hi = c.child_age_max_months if c.child_age_max_months is not None else 10_000
    for ch in children:
        if ch.status == "expected":
            return "maybe"  # „po urodzeniu”
        if ch.birth_date and lo <= _age_months(ch.birth_date, today) <= hi:
            return "fits"
    return "no"
