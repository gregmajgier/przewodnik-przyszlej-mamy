from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException

from ..models.profile import MemberProfile, ParentProfile
from ..security import Principal, require_parent
from ..storage import Store, get_store

router = APIRouter(prefix="/api/profile", tags=["profile"])

# Składki pracownika (emerytalna 9,76% + rentowa 1,5% + chorobowa 2,45%) — do weryfikacji merytorycznej.
EMPLOYEE_SOCIAL_RATE = 0.1371


async def _profile(store: Store, user_id: str) -> ParentProfile:
    doc = await store.get("profiles", user_id)
    if doc is None:
        raise HTTPException(404, "Nie znaleziono profilu. Zaloguj się ponownie przez mObywatela.")
    return ParentProfile.model_validate({**doc, "user_id": user_id})


@router.get("")
async def family_profiles(
    p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> dict[str, list[MemberProfile]]:
    """Profile wszystkich rodziców z rodziny zalogowanego (bez rodziny: tylko własny)."""
    family = await store.get("families", p.family_id) if p.family_id else None
    member_ids = family["member_ids"] if family else [p.user_id]
    members = []
    for uid in member_ids:
        user = await store.get("users", uid)
        doc = await store.get("profiles", uid)
        if user is None or doc is None:
            continue
        members.append(MemberProfile.model_validate({**doc, "user_id": uid, "user_name": user["name"]}))
    return {"members": members}


@router.get("/me")
async def my_profile(
    p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> ParentProfile:
    return await _profile(store, p.user_id)


@router.patch("/me/answers")
async def patch_answers(
    answers: dict[str, bool | str] = Body(...),
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> ParentProfile:
    profile = await _profile(store, p.user_id)
    profile.answers = {**profile.answers, **answers}
    await store.put("profiles", {**profile.model_dump(mode="json"), "id": p.user_id})
    return profile


@router.get("/me/zus")
async def zus_preview(
    p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> dict:
    """Symulowany podgląd konta PUE ZUS."""
    profile = await _profile(store, p.user_id)
    today = date.today()
    insurance = profile.insurance[0] if profile.insurance else None
    months = []
    for back in range(3):
        y, m = today.year, today.month - back
        while m < 1:
            y, m = y - 1, m + 12
        base = insurance.contribution_base if insurance else 0.0
        months.append(
            {
                "month": f"{y:04d}-{m:02d}",
                "base": base,
                "employee_social": round(base * EMPLOYEE_SOCIAL_RATE, 2),
            }
        )
    return {
        "simulated": True,
        "insured": insurance is not None,
        "insurance": [i.model_dump(mode="json") for i in profile.insurance],
        "contributions": months,
        "ezla": [e.model_dump(mode="json") for e in profile.ezla],
        "contribution_debt": profile.contribution_debt.model_dump(mode="json")
        if profile.contribution_debt
        else None,
        "verify": True,
    }
