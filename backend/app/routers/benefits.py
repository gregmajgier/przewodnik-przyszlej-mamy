from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..ai.limits import warsaw_today
from ..security import Principal, require_parent
from ..services.benefit_service import Analysis, BenefitMatch, BenefitService, Summary
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["benefits"])


class AnswerIn(BaseModel):
    condition_id: str
    answer: bool


def get_service(store: Store = Depends(get_store)) -> BenefitService:
    return BenefitService(store)


@router.get("/benefits")
async def list_benefits(
    p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> list[BenefitMatch]:
    return await svc.list_matches(p.user_id, warsaw_today())


@router.get("/benefits/{benefit_id}")
async def get_benefit(
    benefit_id: str, p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> BenefitMatch:
    return await svc.get_match(p.user_id, benefit_id, warsaw_today())


@router.post("/benefits/{benefit_id}/answers")
async def answer_question(
    benefit_id: str,
    body: AnswerIn,
    p: Principal = Depends(require_parent),
    svc: BenefitService = Depends(get_service),
) -> BenefitMatch:
    return await svc.answer(p.user_id, benefit_id, body.condition_id, body.answer, warsaw_today())


@router.get("/analysis")
async def analysis(
    p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> Analysis:
    return await svc.analysis(p.user_id, warsaw_today())


@router.get("/summary")
async def summary(
    p: Principal = Depends(require_parent), svc: BenefitService = Depends(get_service)
) -> Summary:
    return await svc.summary(p.user_id, warsaw_today())
