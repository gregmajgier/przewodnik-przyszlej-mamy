from fastapi import APIRouter, Depends, Response

from ..models.family import (
    Child,
    ChildIn,
    ChildPatch,
    CreateFamilyIn,
    Family,
    FamilyView,
    JoinIn,
    JoinRequest,
    JoinRequestView,
)
from ..security import Principal, require_parent
from ..services.families import FamilyService
from ..storage import Store, get_store

router = APIRouter(prefix="/api/families", tags=["families"])


def get_service(store: Store = Depends(get_store)) -> FamilyService:
    return FamilyService(store)


@router.post("", status_code=201)
async def create_family(
    body: CreateFamilyIn | None = None,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> FamilyView:
    await svc.create_family(p.user_id, body.name if body else None)
    return await svc.get_family_view(p.user_id)


@router.get("/me")
async def my_family(
    p: Principal = Depends(require_parent), svc: FamilyService = Depends(get_service)
) -> FamilyView:
    return await svc.get_family_view(p.user_id)


@router.post("/me/invite-code")
async def new_invite_code(
    p: Principal = Depends(require_parent), svc: FamilyService = Depends(get_service)
) -> Family:
    return await svc.rotate_invite_code(p.user_id)


@router.post("/join", status_code=201)
async def join(
    body: JoinIn,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> JoinRequest:
    return await svc.request_join(p.user_id, body.code)


@router.get("/join-requests/mine")
async def my_join_requests(
    p: Principal = Depends(require_parent), svc: FamilyService = Depends(get_service)
) -> list[JoinRequest]:
    return await svc.my_requests(p.user_id)


@router.get("/me/join-requests")
async def join_requests(
    p: Principal = Depends(require_parent), svc: FamilyService = Depends(get_service)
) -> list[JoinRequestView]:
    return await svc.pending_requests(p.user_id)


@router.post("/me/join-requests/{request_id}/accept")
async def accept(
    request_id: str,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> FamilyView:
    await svc.decide(p.user_id, request_id, True)
    return await svc.get_family_view(p.user_id)


@router.post("/me/join-requests/{request_id}/reject")
async def reject(
    request_id: str,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> FamilyView:
    await svc.decide(p.user_id, request_id, False)
    return await svc.get_family_view(p.user_id)


@router.get("/me/children")
async def list_children(
    p: Principal = Depends(require_parent), svc: FamilyService = Depends(get_service)
) -> list[Child]:
    return await svc.list_children(p.user_id)


@router.post("/me/children", status_code=201)
async def add_child(
    body: ChildIn,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> Child:
    return await svc.add_child(p.user_id, body)


@router.patch("/me/children/{child_id}")
async def update_child(
    child_id: str,
    body: ChildPatch,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> Child:
    return await svc.update_child(p.user_id, child_id, body)


@router.delete("/me/children/{child_id}", status_code=204)
async def delete_child(
    child_id: str,
    p: Principal = Depends(require_parent),
    svc: FamilyService = Depends(get_service),
) -> Response:
    await svc.delete_child(p.user_id, child_id)
    return Response(status_code=204)
