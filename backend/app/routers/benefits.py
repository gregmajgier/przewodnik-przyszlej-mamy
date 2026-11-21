from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import Principal, require_parent
from ..services.benefit_service import Analysis, BenefitMatch, BenefitService, Summary
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["benefits"])


def get_today() -> date:
    """Dzisiejsza data (zależność do podmiany w testach)."""
    return date.today()


def get_service(store: Store = Depends(get_store), today: date = Depends(get_today)) -> BenefitService:
    return BenefitService(store, today)


class AnswerIn(BaseModel):
    condition_id: str
    answer: bool


@router.get("/benefits")
async def list_benefits(
    p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> list[BenefitMatch]:
    return await svc.list_matches(p)


@router.get("/benefits/{benefit_id}")
async def get_benefit(
    benefit_id: str, p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> BenefitMatch:
    return await svc.get_match(p, benefit_id)


@router.post("/benefits/{benefit_id}/answers")
async def answer_question(
    benefit_id: str,
    body: AnswerIn,
    p: Principal = Depends(require_parent),
    svc: BenefitService = Depends(get_service),
) -> BenefitMatch:
    return await svc.answer(p, benefit_id, body.condition_id, body.answer)


@router.get("/analysis")
async def analysis(p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)) -> Analysis:
    return await svc.analysis(p)


@router.get("/summary")
async def summary(p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)) -> Summary:
    return await svc.summary(p)
