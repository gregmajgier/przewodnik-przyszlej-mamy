from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.user import User
from ..security import Principal, current_principal, issue_token, verify_password
from ..seed.personas import PERSONAS, get_persona
from ..services.zus_sim import fetch_zus_data
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["auth"])


class PersonaLogin(BaseModel):
    persona_id: str


class OfficialLogin(BaseModel):
    email: str
    password: str


def _session(user_doc: dict) -> dict:
    user = User.model_validate(user_doc)  # pomija m.in. password_hash
    token = issue_token(Principal(user.id, user.role, user.family_id, user.unit_id))
    return {"token": token, "user": user.model_dump(mode="json")}


@router.get("/auth/personas")
async def list_personas():
    return [{"id": p["id"], "name": p["name"], "role_label": p["role_label"]} for p in PERSONAS.values()]


@router.post("/auth/mobywatel")
async def login_mobywatel(body: PersonaLogin, store: Store = Depends(get_store)):
    persona = get_persona(body.persona_id)
    if persona is None:
        raise HTTPException(404, "Nie znaleziono takiej persony mObywatela.")
    user_id = f"user-{persona['id'].removeprefix('persona-')}"
    user_doc = await store.get("users", user_id)
    if user_doc is None:
        user = User(id=user_id, role="parent", name=persona["name"], persona_id=persona["id"])
        user_doc = await store.put("users", user.model_dump(mode="json"))
    if await store.get("profiles", user_id) is None:
        # dane „z ZUS/mObywatela” pobierane przy pierwszym logowaniu persony
        zus = fetch_zus_data(persona["id"], date.today())
        await store.put("profiles", {**zus.model_dump(mode="json"), "id": user_id})
    return _session(user_doc)


@router.post("/auth/official")
async def login_official(body: OfficialLogin, store: Store = Depends(get_store)):
    candidates = await store.find("users", role="official", email=body.email.strip().lower())
    user_doc = candidates[0] if candidates else None
    if user_doc is None or not verify_password(body.password, user_doc.get("password_hash")):
        raise HTTPException(401, "Nieprawidłowy e-mail lub hasło.")
    return _session(user_doc)


@router.get("/me")
async def me(p: Principal = Depends(current_principal), store: Store = Depends(get_store)) -> User:
    doc = await store.get("users", p.user_id)
    return User.model_validate(doc)
