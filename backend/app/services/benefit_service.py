"""Świadczenia rodziny: lista z dopasowaniem, odpowiedzi na pytania, analiza i podsumowanie dla dashboardu.

Wszystko jest filtrowane po `family_id` zalogowanego rodzica; odpowiedzi trafiają do profilu wywołującego.
Silnik dopasowania jest deterministyczny (bez LLM).
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from ..errors import DomainError
from ..models.benefit import Benefit
from ..models.family import FamilyView
from ..models.profile import ParentProfile
from ..security import Principal
from ..storage import Store
from .families import NO_FAMILY, FamilyService
from .matching import (
    INSURANCE_LABELS,
    FamilyContext,
    MatchResult,
    build_context,
    match_benefit,
    next_deadline,
)

DEADLINE_WARNING_DAYS = 30
STATUS_ORDER = {"fits": 0, "maybe": 1, "no": 2}


class BenefitMatch(BaseModel):
    benefit: Benefit
    match: MatchResult
    deadline_date: date | None = None


class AnalysisStep(BaseModel):
    key: str
    label: str
    detail: str
    status: str  # done | warning


class Totals(BaseModel):
    national: int
    local: int
    fits: int
    maybe: int
    no: int


class NearestDeadline(BaseModel):
    benefit_id: str
    name: str
    date: date
    days_left: int


class Analysis(BaseModel):
    steps: list[AnalysisStep]
    totals: Totals
    estimated_annual_total: int
    nearest_deadline: NearestDeadline | None = None


class Summary(BaseModel):
    family_name: str
    totals: Totals
    estimated_annual_total: int
    nearest_deadline: NearestDeadline | None = None
    warnings: list[str]
    parameters_label: str


def _fmt_int(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


class BenefitService:
    def __init__(self, store: Store, today: date | None = None) -> None:
        self.store = store
        self.today = today or date.today()

    # ---------- kontekst ----------

    async def _load(self, principal: Principal) -> tuple[FamilyView, list[ParentProfile], FamilyContext]:
        if not principal.family_id:
            raise DomainError(404, NO_FAMILY)
        view = await FamilyService(self.store).get_family_view(principal.user_id)
        profiles: list[ParentProfile] = []
        for uid in view.family.member_ids:
            doc = await self.store.get("profiles", uid)
            if doc is not None:
                profiles.append(ParentProfile.model_validate({**doc, "user_id": uid}))
        if not any(p.user_id == principal.user_id for p in profiles):
            raise DomainError(404, "Nie znaleziono profilu. Zaloguj się ponownie przez mObywatela.")
        units = await self.store.find("units")
        ctx = build_context(view, profiles, self.today, units=units, viewer_id=principal.user_id)
        return view, profiles, ctx

    async def _visible_benefits(self, ctx: FamilyContext) -> list[Benefit]:
        """Opublikowane świadczenia krajowe oraz lokalne, których jednostka obejmuje adres rodziny."""
        out = []
        for doc in await self.store.find("benefits", status="published"):
            b = Benefit.model_validate(doc)
            if b.scope == "national" or (b.unit_id and b.unit_id in ctx.unit_ids):
                out.append(b)
        return out

    def _evaluate(self, ctx: FamilyContext, benefits: list[Benefit]) -> list[BenefitMatch]:
        rows = [
            BenefitMatch(benefit=b, match=match_benefit(ctx, b), deadline_date=next_deadline(b, ctx))
            for b in benefits
        ]
        rows.sort(key=lambda r: (STATUS_ORDER[r.match.status], r.benefit.name))
        return rows

    # ---------- API ----------

    async def list_matches(self, principal: Principal) -> list[BenefitMatch]:
        _, _, ctx = await self._load(principal)
        return self._evaluate(ctx, await self._visible_benefits(ctx))

    async def get_match(self, principal: Principal, benefit_id: str) -> BenefitMatch:
        _, _, ctx = await self._load(principal)
        for row in self._evaluate(ctx, await self._visible_benefits(ctx)):
            if row.benefit.id == benefit_id:
                return row
        raise DomainError(404, "Nie znaleziono takiego świadczenia.")

    async def answer(self, principal: Principal, benefit_id: str, condition_id: str, answer: bool) -> BenefitMatch:
        _, _, ctx = await self._load(principal)
        benefit = next((b for b in await self._visible_benefits(ctx) if b.id == benefit_id), None)
        if benefit is None:
            raise DomainError(404, "Nie znaleziono takiego świadczenia.")
        valid = {c.id for c in benefit.extra_conditions}
        if benefit.criteria.max_income_per_person is not None:
            valid.add("income")
        if condition_id not in valid:
            raise DomainError(422, "To świadczenie nie ma takiego pytania.")
        doc = await self.store.get("profiles", principal.user_id)
        profile = ParentProfile.model_validate({**doc, "user_id": principal.user_id})  # type: ignore[arg-type]
        profile.answers = {**profile.answers, f"benefit:{benefit_id}:{condition_id}": answer}
        await self.store.put("profiles", {**profile.model_dump(mode="json"), "id": principal.user_id})
        return await self.get_match(principal, benefit_id)

    # ---------- agregacje ----------

    @staticmethod
    def _totals(rows: list[BenefitMatch]) -> Totals:
        count = {"fits": 0, "maybe": 0, "no": 0}
        for r in rows:
            count[r.match.status] += 1
        national = sum(1 for r in rows if r.benefit.scope == "national")
        return Totals(national=national, local=len(rows) - national, **count)

    @staticmethod
    def _annual_total(rows: list[BenefitMatch]) -> int:
        """Orientacyjnie: tylko świadczenia, które „pasują”; „na dziecko” × liczba uprawnionych dzieci."""
        total = 0.0
        for r in rows:
            est = r.benefit.annual_value_estimate
            if r.match.status != "fits" or not est:
                continue
            total += est * max(r.match.eligible_children, 1) if "per_child" in r.benefit.tags else est
        return int(total)

    def _nearest(self, rows: list[BenefitMatch]) -> NearestDeadline | None:
        dated = [r for r in rows if r.match.status in ("fits", "maybe") and r.deadline_date]
        if not dated:
            return None
        r = min(dated, key=lambda x: x.deadline_date)  # type: ignore[arg-type, return-value]
        return NearestDeadline(
            benefit_id=r.benefit.id,
            name=r.benefit.name,
            date=r.deadline_date,  # type: ignore[arg-type]
            days_left=(r.deadline_date - self.today).days,  # type: ignore[operator]
        )

    def _soon(self, rows: list[BenefitMatch]) -> list[BenefitMatch]:
        limit = self.today + timedelta(days=DEADLINE_WARNING_DAYS)
        return [
            r
            for r in rows
            if r.match.status in ("fits", "maybe") and r.deadline_date and r.deadline_date <= limit
        ]

    async def analysis(self, principal: Principal) -> Analysis:
        view, profiles, ctx = await self._load(principal)
        rows = self._evaluate(ctx, await self._visible_benefits(ctx))
        totals = self._totals(rows)
        me = next(p for p in profiles if p.user_id == principal.user_id)

        if me.insurance:
            ins = me.insurance[0]
            zus_detail = f"{INSURANCE_LABELS[ins.kind]}, podstawa {_fmt_int(ins.contribution_base)} zł"
        else:
            zus_detail = "brak tytułu ubezpieczenia w danych ZUS"
        if any(e.code.upper() == "B" for e in me.ezla):
            zus_detail += "; zwolnienie w ciąży (e-ZLA, kod B)"

        contracts = [
            c for c in await self.store.find("contracts") if c.get("family_id") == principal.family_id
        ]
        soon = self._soon(rows)
        steps = [
            AnalysisStep(key="zus", label="Dane z ZUS", detail=zus_detail, status="done"),
            AnalysisStep(
                key="contracts",
                label="Umowy",
                detail=str(len(contracts)) if contracts else "0 — możesz je dodać w „Moich danych”",
                status="done",
            ),
            AnalysisStep(
                key="catalog",
                label="Przeglądamy świadczenia",
                detail=(
                    f"{totals.national} krajowych, {totals.local} lokalnych "
                    f"({ctx.address.city}, woj. {ctx.address.voivodeship.lower()})"
                ),
                status="done",
            ),
            AnalysisStep(
                key="results",
                label="Wynik dopasowania",
                detail=f"pasuje do was: {totals.fits} · może przysługiwać: {totals.maybe}",
                status="done",
            ),
            AnalysisStep(
                key="deadlines",
                label="Terminy",
                detail=(
                    f"{len(soon)} {_deadline_word(len(soon))} w ciągu {DEADLINE_WARNING_DAYS} dni"
                    if soon
                    else f"brak terminów w ciągu {DEADLINE_WARNING_DAYS} dni"
                ),
                status="warning" if soon else "done",
            ),
        ]
        return Analysis(
            steps=steps,
            totals=totals,
            estimated_annual_total=self._annual_total(rows),
            nearest_deadline=self._nearest(rows),
        )

    async def summary(self, principal: Principal) -> Summary:
        view, profiles, ctx = await self._load(principal)
        rows = self._evaluate(ctx, await self._visible_benefits(ctx))
        warnings = [
            f"{r.benefit.name}: termin {r.deadline_date.strftime('%d.%m.%Y')}"  # type: ignore[union-attr]
            for r in self._soon(rows)
        ]
        for p in profiles:
            if p.contribution_debt and any(i.kind == "jdg" for i in p.insurance):
                warnings.append("Zadłużenie składkowe może pozbawić cię zasiłku macierzyńskiego.")
                break
        return Summary(
            family_name=view.family.name,
            totals=self._totals(rows),
            estimated_annual_total=self._annual_total(rows),
            nearest_deadline=self._nearest(rows),
            warnings=warnings,
            parameters_label=f"Parametry ZUS {self.today.year} – aktywne",
        )


def _deadline_word(n: int) -> str:
    return "termin" if n == 1 else "terminy" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "terminów"


__all__ = ["BenefitService", "BenefitMatch", "Analysis", "Summary"]
