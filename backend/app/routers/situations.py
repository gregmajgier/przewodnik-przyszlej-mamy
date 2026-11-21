"""Tryb jaskółki i „Za życiem” (plan 10): zmiana sytuacji dziecka, cofnięcie, wyjście z trybu."""

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from ..models.family import Child
from ..security import Principal, require_parent
from ..services import situations
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["situations"])


class SituationIn(BaseModel):
    kind: Literal["poronienie", "martwe-urodzenie", "smierc-dziecka"]


class SeriousIllnessIn(BaseModel):
    value: bool


@router.post("/families/me/children/{child_id}/situation")
async def report_situation(
    child_id: str,
    body: SituationIn,
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> Child:
    return await situations.set_situation(store, p, child_id, body.kind)


@router.delete("/families/me/children/{child_id}/situation")
async def undo_situation(
    child_id: str, p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> Child:
    return await situations.undo_situation(store, p, child_id)


@router.post("/families/me/mode/exit", status_code=204)
async def exit_mode(p: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> Response:
    await situations.exit_mode(store, p)
    return Response(status_code=204)


@router.patch("/families/me/children/{child_id}/serious-illness")
async def serious_illness(
    child_id: str,
    body: SeriousIllnessIn,
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> Child:
    return await situations.set_serious_illness(store, p, child_id, body.value)


@router.get("/me/mode")
async def my_mode(p: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> dict:
    return await situations.mode_info(store, p)
