"""Panel urzędnika (plan 07): świadczenia lokalne własnej jednostki, warunki z AI, publikacja.

Urzędnik widzi i zmienia wyłącznie świadczenia swojej jednostki (cudze -> 404). Status:
`draft` -> (wyodrębnij warunki) -> `awaiting_approval` -> (zatwierdź warunki) -> `published`.
Każda edycja (także opublikowanego) wraca do `draft`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..ai.limits import GuardContext, ai_guard, enforce_max_input, record_usage
from ..ai.llm import LLM, Usage, get_llm, track_usage
from ..errors import DomainError
from ..models.benefit import Condition, Criteria
from ..models.official_benefit import OfficialBenefit
from ..models.unit import Unit
from ..models.user import User
from ..security import Principal, require_official
from ..services.conditions import (
    FEATURE_CONDITIONS,
    FEATURE_PREFILL,
    BenefitDraft,
    extract_conditions,
    normalize_conditions,
    prefill_from_resolution,
)
from ..storage import Store, get_store

router = APIRouter(prefix="/api/official", tags=["official"])

NOT_FOUND = "Nie znaleziono takiego świadczenia w Twojej jednostce."
SCOPE_BY_LEVEL = {"gmina": "municipal", "powiat": "municipal", "voivodeship": "regional"}


class BenefitIn(BaseModel):
    """Pola edytowane przez urzędnika. `scope`, `unit_id`, `status` i warunki ustawia serwer."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    category: str = "benefit"
    amount_text: str | None = Field(default=None, max_length=200)
    annual_value_estimate: int | None = Field(default=None, ge=0)
    deadline_text: str | None = Field(default=None, max_length=300)
    how_to_apply: str = Field(default="", max_length=2000)
    apply_url: str | None = Field(default=None, max_length=500)
    source_url: str = Field(default="", max_length=500)
    criteria: Criteria = Field(default_factory=Criteria)
    extra_text: str | None = Field(default=None, max_length=4000)


class ApproveIn(BaseModel):
    conditions: list[Condition] = Field(default_factory=list, max_length=30)


class PrefillIn(BaseModel):
    text: str = Field(min_length=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if url and not url.startswith(("https://", "http://")):
        raise DomainError(422, "Link musi zaczynać się od https://")
    return url or None


async def _unit(store: Store, p: Principal) -> Unit:
    doc = await store.get("units", p.unit_id) if p.unit_id else None
    if doc is None:
        raise DomainError(403, "Twoje konto nie jest przypisane do jednostki.")
    return Unit.model_validate(doc)


async def _own(store: Store, p: Principal, benefit_id: str) -> OfficialBenefit:
    doc = await store.get("benefits", benefit_id)
    if doc is None or not p.unit_id or doc.get("unit_id") != p.unit_id:
        raise DomainError(404, NOT_FOUND)
    return OfficialBenefit.model_validate(doc)


async def _save(store: Store, b: OfficialBenefit) -> OfficialBenefit:
    b.updated_at = _now()
    await store.put("benefits", b.model_dump(mode="json"))
    return b


def _apply(b: OfficialBenefit, body: BenefitIn) -> None:
    if body.category not in ("benefit", "perk"):
        raise DomainError(422, "Nieznany rodzaj świadczenia.")
    c = body.criteria
    if (
        c.child_age_min_months is not None
        and c.child_age_max_months is not None
        and c.child_age_min_months > c.child_age_max_months
    ):
        raise DomainError(422, "Wiek „od” nie może być większy niż wiek „do”.")
    extra = (body.extra_text or "").strip() or None
    if extra != b.extra_text:
        b.extra_conditions = []
        b.conditions_approved = False
    data = body.model_dump()
    data["extra_text"] = extra
    data["apply_url"] = _clean_url(body.apply_url)
    data["source_url"] = _clean_url(body.source_url) or ""
    for k, v in data.items():
        setattr(b, k, v)
    b.criteria = c
    b.status = "draft"


@router.get("/me")
async def me(p: Principal = Depends(require_official), store: Store = Depends(get_store)) -> dict:
    user = User.model_validate(await store.get("users", p.user_id))
    return {"user": user.model_dump(mode="json"), "unit": (await _unit(store, p)).model_dump(mode="json")}


@router.get("/benefits")
async def list_benefits(
    p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> list[OfficialBenefit]:
    if not p.unit_id:
        return []
    items = [OfficialBenefit.model_validate(d) for d in await store.find("benefits", unit_id=p.unit_id)]
    items.sort(key=lambda b: b.name.casefold())
    return items


@router.post("/benefits", status_code=201)
async def create_benefit(
    body: BenefitIn, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    unit = await _unit(store, p)
    b = OfficialBenefit(
        id=f"local-{uuid.uuid4().hex[:12]}",
        name=body.name,
        description=body.description,
        scope=SCOPE_BY_LEVEL[unit.level],
        unit_id=unit.id,
        status="draft",
        created_by=p.user_id,
    )
    _apply(b, body)
    return await _save(store, b)


@router.get("/benefits/{benefit_id}")
async def get_benefit(
    benefit_id: str, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    return await _own(store, p, benefit_id)


@router.put("/benefits/{benefit_id}")
async def update_benefit(
    benefit_id: str, body: BenefitIn, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    b = await _own(store, p, benefit_id)
    _apply(b, body)
    return await _save(store, b)


@router.delete("/benefits/{benefit_id}", status_code=204)
async def delete_benefit(
    benefit_id: str, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> Response:
    await _own(store, p, benefit_id)
    await store.delete("benefits", benefit_id)
    return Response(status_code=204)


@router.post("/benefits/{benefit_id}/extract-conditions")
async def extract(
    benefit_id: str,
    p: Principal = Depends(require_official),
    ctx: GuardContext = Depends(ai_guard(FEATURE_CONDITIONS)),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
) -> OfficialBenefit:
    usage = Usage()
    try:
        b = await _own(store, p, benefit_id)
        if not b.extra_text:
            raise DomainError(422, "Wpisz najpierw „Dodatkowe wymogi”.")
        enforce_max_input(b.extra_text)
        with track_usage() as usage:
            conditions = await extract_conditions(llm, b.extra_text)
    except BaseException:
        if usage.total:
            await record_usage(ctx, usage)
        else:
            await ctx.release()
        raise
    await record_usage(ctx, usage)
    b.extra_conditions = conditions
    b.conditions_approved = False
    b.status = "awaiting_approval"
    return await _save(store, b)


@router.post("/benefits/{benefit_id}/approve-conditions")
async def approve(
    benefit_id: str, body: ApproveIn, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    b = await _own(store, p, benefit_id)
    b.extra_conditions = normalize_conditions(body.conditions)
    b.conditions_approved = True
    b.status = "awaiting_approval"
    return await _save(store, b)


@router.post("/benefits/{benefit_id}/publish")
async def publish(
    benefit_id: str, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    b = await _own(store, p, benefit_id)
    if b.extra_text and not b.conditions_approved:
        raise DomainError(409, "Zatwierdź listę warunków z „Dodatkowych wymogów” przed publikacją.")
    if not b.description.strip():
        raise DomainError(422, "Dodaj opis świadczenia przed publikacją.")
    b.status = "published"
    return await _save(store, b)


@router.post("/benefits/{benefit_id}/unpublish")
async def unpublish(
    benefit_id: str, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> OfficialBenefit:
    b = await _own(store, p, benefit_id)
    b.status = "draft"
    return await _save(store, b)


@router.post("/prefill-from-text")
async def prefill(
    body: PrefillIn,
    p: Principal = Depends(require_official),
    ctx: GuardContext = Depends(ai_guard(FEATURE_PREFILL)),
    llm: LLM = Depends(get_llm),
) -> BenefitDraft:
    usage = Usage()
    try:
        enforce_max_input(body.text)
        with track_usage() as usage:
            draft = await prefill_from_resolution(llm, body.text)
    except BaseException:
        if usage.total:
            await record_usage(ctx, usage)
        else:
            await ctx.release()
        raise
    await record_usage(ctx, usage)
    return draft
