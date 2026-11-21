"""Świadczenia dla rodziny zalogowanego rodzica: lista dopasowań, odpowiedzi na pytania, analiza i podsumowanie.

Silnik (`matching.py`) jest czysty i deterministyczny — ten moduł tylko składa dane z magazynu.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..errors import DomainError
from ..models.benefit import Benefit
from ..models.profile import Address, ParentProfile
from ..storage import Store
from .families import FamilyService
from .situations import loss_support_applies
from .units import units_for
from .matching import FamilyContext, MatchResult, build_context, match_benefit, next_deadline

PARAMETERS_LABEL = "Parametry ZUS 2026 – aktywne"
INCOME_CONDITION = "income"


class BenefitMatch(BaseModel):
    benefit: Benefit
    match: MatchResult


class AnalysisStep(BaseModel):
    key: str
    label: str
    detail: str
    status: str = "done"


class Totals(BaseModel):
    national: int
    local: int
    fits: int
    maybe: int
    no: int


class NearestDeadline(BaseModel):
    date: date
    benefit_id: str
    benefit_name: str


class Summary(BaseModel):
    totals: Totals
    estimated_annual_total: int
    nearest_deadline: NearestDeadline | None = None
    parameters_label: str = PARAMETERS_LABEL


class Analysis(Summary):
    steps: list[AnalysisStep] = Field(default_factory=list)


async def visible_benefits(store: Store, address: Address) -> list[Benefit]:
    """Opublikowane świadczenia obejmujące dany adres (krajowe + jednostki, które go obejmują)."""
    unit_ids = set(units_for(address, await store.find("units")))
    benefits = [Benefit.model_validate(d) for d in await store.find("benefits", status="published")]
    return sorted(
        (b for b in benefits if b.scope == "national" or (b.unit_id and b.unit_id in unit_ids)),
        key=lambda b: (b.scope != "national", b.name),
    )


def answer_key(benefit_id: str, condition_id: str) -> str:
    return f"benefit:{benefit_id}:{condition_id}"


class BenefitService:
    def __init__(self, store: Store) -> None:
        self.store = store

    # ---------- kontekst ----------

    async def _context(self, user_id: str, today: date) -> FamilyContext:
        view = await FamilyService(self.store).get_family_view(user_id)
        profiles: list[ParentProfile] = []
        for member_id in view.family.member_ids:
            doc = await self.store.get("profiles", member_id)
            if doc is not None:
                profiles.append(ParentProfile.model_validate({**doc, "user_id": member_id}))
        if not profiles:
            raise DomainError(404, "Nie znaleziono profilu. Zaloguj się ponownie przez mObywatela.")
        units = await self.store.find("units")
        return build_context(view, profiles, today, units, viewer_id=user_id)

    async def _visible(self, ctx: FamilyContext) -> list[Benefit]:
        """Opublikowane świadczenia obejmujące adres rodziny (cudze gminy nigdy się nie pojawiają)."""
        docs = await self.store.find("benefits", status="published")
        benefits = [Benefit.model_validate(d) for d in docs]
        return sorted(
            (
                b
                for b in benefits
                if (b.scope == "national" or (b.unit_id and b.unit_id in ctx.unit_ids))
                and loss_support_applies(b.tags, ctx.children)  # wsparcie po stracie tylko w trybie jaskółki
            ),
            key=lambda b: (b.scope != "national", b.name),
        )

    async def _matches(self, ctx: FamilyContext) -> list[BenefitMatch]:
        return [BenefitMatch(benefit=b, match=match_benefit(ctx, b)) for b in await self._visible(ctx)]

    # ---------- lista i szczegóły ----------

    async def list_matches(self, user_id: str, today: date) -> list[BenefitMatch]:
        return await self._matches(await self._context(user_id, today))

    async def get_match(self, user_id: str, benefit_id: str, today: date) -> BenefitMatch:
        for item in await self.list_matches(user_id, today):
            if item.benefit.id == benefit_id:
                return item
        raise DomainError(404, "Nie znaleziono takiego świadczenia.")

    # ---------- odpowiedzi na pytania ----------

    async def answer(
        self, user_id: str, benefit_id: str, condition_id: str, value: bool, today: date
    ) -> BenefitMatch:
        current = await self.get_match(user_id, benefit_id, today)
        valid = {c.id for c in current.benefit.extra_conditions}
        if current.benefit.criteria.max_income_per_person is not None:
            valid.add(INCOME_CONDITION)
        if condition_id not in valid:
            raise DomainError(404, "To świadczenie nie ma takiego pytania.")
        doc = await self.store.get("profiles", user_id)
        if doc is None:
            raise DomainError(404, "Nie znaleziono profilu. Zaloguj się ponownie przez mObywatela.")
        profile = ParentProfile.model_validate({**doc, "user_id": user_id})
        profile.answers = {**profile.answers, answer_key(benefit_id, condition_id): value}
        await self.store.put("profiles", {**profile.model_dump(mode="json"), "id": user_id})
        return await self.get_match(user_id, benefit_id, today)

    # ---------- agregacje ----------

    @staticmethod
    def _aggregate(matches: list[BenefitMatch], ctx: FamilyContext) -> Summary:
        fits = [m for m in matches if m.match.status == "fits"]
        maybe = [m for m in matches if m.match.status == "maybe"]
        totals = Totals(
            national=sum(1 for m in matches if m.benefit.scope == "national"),
            local=sum(1 for m in matches if m.benefit.scope != "national"),
            fits=len(fits),
            maybe=len(maybe),
            no=len(matches) - len(fits) - len(maybe),
        )
        # Szacunek liczymy tylko dla pozycji, które na pewno pasują (konserwatywnie), i tylko świadczeń pieniężnych.
        estimated = sum(m.benefit.annual_value_estimate or 0 for m in fits if m.benefit.category == "benefit")
        deadlines = [
            (d, m.benefit)
            for m in fits + maybe
            if (d := next_deadline(m.benefit, ctx)) is not None
        ]
        nearest = None
        if deadlines:
            d, b = min(deadlines, key=lambda x: (x[0], x[1].name))
            nearest = NearestDeadline(date=d, benefit_id=b.id, benefit_name=b.name)
        return Summary(totals=totals, estimated_annual_total=estimated, nearest_deadline=nearest)

    async def summary(self, user_id: str, today: date) -> Summary:
        ctx = await self._context(user_id, today)
        return self._aggregate(await self._matches(ctx), ctx)

    async def analysis(self, user_id: str, today: date) -> Analysis:
        ctx = await self._context(user_id, today)
        s = self._aggregate(await self._matches(ctx), ctx)
        t = s.totals
        born = [c for c in ctx.children if c.status == "born" and c.situation != "loss"]
        expected = [c for c in ctx.children if c.status == "expected" and c.situation != "loss"]
        parents = len(ctx.parents)
        steps = [
            AnalysisStep(
                key="profile",
                label="Czytam twoje dane z ZUS i mObywatela",
                detail=f"Rodzice w rodzinie: {parents}. Adres: {ctx.address.city}.",
            ),
            AnalysisStep(
                key="family",
                label="Sprawdzam skład rodziny",
                detail=f"Dzieci: {len(born)}, w drodze: {len(expected)}.",
            ),
            AnalysisStep(
                key="national",
                label="Przeglądam świadczenia krajowe",
                detail=f"Znalazłem {t.national} świadczeń i uprawnień krajowych.",
            ),
            AnalysisStep(
                key="local",
                label=f"Szukam świadczeń w gminie {ctx.address.gmina} i w województwie",
                detail=f"Dostępnych lokalnie: {t.local}.",
            ),
            AnalysisStep(
                key="match",
                label="Dopasowuję je do waszej sytuacji",
                detail=f"Pasuje: {t.fits}, może ci przysługiwać: {t.maybe}, nie pasuje: {t.no}.",
            ),
        ]
        return Analysis(**s.model_dump(), steps=steps)
