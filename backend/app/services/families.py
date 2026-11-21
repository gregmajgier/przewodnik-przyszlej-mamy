"""Rodzina: zakładanie, kod dołączania (prośba + akceptacja założyciela), dzieci."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from ..errors import DomainError
from ..models.family import (
    Child,
    ChildIn,
    ChildPatch,
    Family,
    FamilyView,
    JoinRequest,
    JoinRequestView,
)
from ..models.user import User
from ..storage import Store

CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_TTL = timedelta(days=7)
MAX_PARENTS = 2

NO_FAMILY = "Nie należysz jeszcze do żadnej rodziny."


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FamilyService:
    def __init__(self, store: Store) -> None:
        self.store = store

    # ---------- pomocnicze ----------

    async def _user(self, user_id: str) -> dict:
        doc = await self.store.get("users", user_id)
        if doc is None:
            raise DomainError(401, "Konto nie istnieje. Zaloguj się ponownie.")
        return doc

    async def _family_of(self, user_id: str) -> Family:
        user = await self._user(user_id)
        fam = await self.store.get("families", user["family_id"]) if user.get("family_id") else None
        if fam is None:
            raise DomainError(404, NO_FAMILY)
        return Family.model_validate(fam)

    async def _unique_code(self) -> str:
        while True:
            code = _new_code()
            if not await self.store.find("families", invite_code=code):
                return code

    async def _save_family(self, family: Family) -> Family:
        await self.store.put("families", family.model_dump(mode="json"))
        return family

    # ---------- rodzina ----------

    async def create_family(self, user_id: str, name: str | None = None) -> Family:
        user = await self._user(user_id)
        if user.get("family_id"):
            raise DomainError(409, "Należysz już do rodziny.")
        last_name = user["name"].split()[-1] if user.get("name") else ""
        family = Family(
            id=f"family-{uuid.uuid4().hex[:12]}",
            name=name or (f"Rodzina {last_name}" if last_name else "Moja rodzina"),
            owner_id=user_id,
            member_ids=[user_id],
            invite_code=await self._unique_code(),
            invite_expires_at=_now() + CODE_TTL,
        )
        await self._save_family(family)
        await self.store.put("users", {**user, "family_id": family.id})
        return family

    async def rotate_invite_code(self, user_id: str) -> Family:
        family = await self._family_of(user_id)
        if family.owner_id != user_id:
            raise DomainError(403, "Kod zaproszenia może wygenerować tylko założyciel rodziny.")
        family.invite_code = await self._unique_code()
        family.invite_expires_at = _now() + CODE_TTL
        return await self._save_family(family)

    async def request_join(self, user_id: str, code: str) -> JoinRequest:
        user = await self._user(user_id)
        code = (code or "").strip().upper()
        found = await self.store.find("families", invite_code=code) if code else []
        if not found:
            raise DomainError(404, "Nie znaleziono rodziny o takim kodzie. Sprawdź kod i spróbuj ponownie.")
        family = Family.model_validate(found[0])
        if family.invite_expires_at and family.invite_expires_at <= _now():
            raise DomainError(404, "Kod zaproszenia wygasł. Poproś o wygenerowanie nowego.")
        if user.get("family_id") == family.id:
            raise DomainError(409, "To jest już twoja rodzina.")
        if user.get("family_id"):
            raise DomainError(409, "Należysz już do innej rodziny.")
        if len(family.member_ids) >= MAX_PARENTS:
            raise DomainError(409, "Ta rodzina ma już dwoje rodziców.")
        for existing in await self.store.find("join_requests", family_id=family.id, user_id=user_id):
            if existing["status"] == "pending":
                raise DomainError(409, "Prośba o dołączenie została już wysłana. Poczekaj na akceptację.")
        req = JoinRequest(id=f"jr-{uuid.uuid4().hex[:12]}", family_id=family.id, user_id=user_id)
        await self.store.put("join_requests", req.model_dump(mode="json"))
        return req

    async def decide(self, owner_id: str, request_id: str, accept: bool) -> Family:
        doc = await self.store.get("join_requests", request_id)
        if doc is None:
            raise DomainError(404, "Nie znaleziono takiej prośby o dołączenie.")
        req = JoinRequest.model_validate(doc)
        family_doc = await self.store.get("families", req.family_id)
        family = Family.model_validate(family_doc)
        if family.owner_id != owner_id:
            raise DomainError(403, "Tylko założyciel rodziny może zdecydować o prośbie.")
        if req.status != "pending":
            raise DomainError(409, "Ta prośba została już rozpatrzona.")
        if accept:
            joiner = await self._user(req.user_id)
            if len(family.member_ids) >= MAX_PARENTS:
                raise DomainError(409, "Ta rodzina ma już dwoje rodziców.")
            if joiner.get("family_id"):
                raise DomainError(409, "Ta osoba należy już do innej rodziny.")
            family.member_ids.append(req.user_id)
            await self._save_family(family)
            await self.store.put("users", {**joiner, "family_id": family.id})
        req.status = "accepted" if accept else "rejected"
        await self.store.put("join_requests", req.model_dump(mode="json"))
        return family

    async def pending_requests(self, owner_id: str) -> list[JoinRequestView]:
        family = await self._family_of(owner_id)
        if family.owner_id != owner_id:
            return []
        views = []
        for d in await self.store.find("join_requests", family_id=family.id, status="pending"):
            u = await self.store.get("users", d["user_id"])
            views.append(JoinRequestView(**d, user_name=u["name"] if u else ""))
        return views

    async def my_requests(self, user_id: str) -> list[JoinRequest]:
        return [JoinRequest.model_validate(d) for d in await self.store.find("join_requests", user_id=user_id)]

    async def get_family_view(self, user_id: str) -> FamilyView:
        family = await self._family_of(user_id)
        members = [
            User.model_validate(u)
            for mid in family.member_ids
            if (u := await self.store.get("users", mid)) is not None
        ]
        return FamilyView(
            family=family,
            members=members,
            children=await self.list_children(user_id),
            pending_requests=await self.pending_requests(user_id),
        )

    # ---------- dzieci ----------

    async def list_children(self, user_id: str) -> list[Child]:
        family = await self._family_of(user_id)
        docs = await self.store.find("children", family_id=family.id)
        children = [Child.model_validate(d) for d in docs]
        children.sort(key=lambda c: (c.birth_date or c.due_date, c.id), reverse=False)
        return children

    async def add_child(self, user_id: str, data: ChildIn) -> Child:
        family = await self._family_of(user_id)
        child = Child(id=f"child-{uuid.uuid4().hex[:12]}", family_id=family.id, **data.model_dump())
        await self.store.put("children", child.model_dump(mode="json"))
        return child

    async def _own_child(self, user_id: str, child_id: str) -> dict:
        family = await self._family_of(user_id)
        doc = await self.store.get("children", child_id)
        if doc is None or doc["family_id"] != family.id:
            raise DomainError(404, "Nie znaleziono takiego dziecka.")
        return doc

    async def update_child(self, user_id: str, child_id: str, patch: ChildPatch) -> Child:
        doc = await self._own_child(user_id, child_id)
        changes = patch.model_dump(exclude_unset=True)
        # pola z domyślną wartością nie-null nie mogą zostać wyzerowane przez null
        for key in ("name", "has_disability", "foster", "serious_illness"):
            if key in changes and changes[key] is None:
                del changes[key]
        if changes.get("birth_date") and "status" not in changes:
            changes["status"] = "born"
        merged = {**doc, **patch_json(changes)}
        try:
            child = Child.model_validate(merged)
        except ValidationError:
            raise DomainError(422, "Podaj datę urodzenia albo przewidywany termin porodu.") from None
        await self.store.put("children", child.model_dump(mode="json"))
        return child

    async def delete_child(self, user_id: str, child_id: str) -> None:
        await self._own_child(user_id, child_id)
        await self.store.delete("children", child_id)


def patch_json(changes: dict) -> dict:
    """Zamienia daty z `ChildPatch` na wartości JSON (ISO) zgodne z zapisem w store."""
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in changes.items()}
