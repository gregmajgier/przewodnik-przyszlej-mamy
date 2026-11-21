"""Umowy rodziców w bazie (plan 04): zatwierdzanie, scalanie z profilem ZUS i ryzyka całej rodziny."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from ..errors import DomainError
from ..models.contract import Contract, ContractDraft, Risk
from ..models.family import Child
from ..models.profile import Insurance, ParentProfile
from ..storage import Store
from .risk import SEVERITY_ORDER, evaluate_risks, normalize_name

MAX_CONTRACTS = 5  # zatwierdzonych umów na rodzica
MAX_DRAFTS = 5  # niezatwierdzonych szkiców na rodzica (starsze usuwamy)

NOT_FOUND = "Nie znaleziono takiej umowy."
LIMIT_REACHED = f"Możesz dodać maksymalnie {MAX_CONTRACTS} umów. Usuń nieaktualną umowę, aby dodać nową."

FIELD_LABELS = {
    "kind": "rodzaj umowy",
    "employer_name": "pracodawca / zleceniodawca",
    "start_date": "data rozpoczęcia",
    "fte_or_gross": "wymiar etatu lub wynagrodzenie",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def family_member_ids(store: Store, user_id: str, family_id: str | None) -> list[str]:
    family = await store.get("families", family_id) if family_id else None
    return list(family["member_ids"]) if family else [user_id]


async def user_contracts(store: Store, user_id: str, *, confirmed: bool | None = True) -> list[Contract]:
    docs = await store.find("contracts", user_id=user_id)
    items = [Contract.model_validate(d) for d in docs]
    if confirmed is not None:
        items = [c for c in items if c.confirmed is confirmed]
    items.sort(key=lambda c: (c.created_at, c.id))
    return items


async def ensure_capacity(store: Store, user_id: str) -> None:
    if len(await user_contracts(store, user_id)) >= MAX_CONTRACTS:
        raise DomainError(409, LIMIT_REACHED)


async def save_draft(
    store: Store, user_id: str, family_id: str | None, filename: str, draft: ContractDraft
) -> Contract:
    drafts = await user_contracts(store, user_id, confirmed=False)
    for old in drafts[: max(0, len(drafts) - MAX_DRAFTS + 1)]:
        await store.delete("contracts", old.id)
    contract = Contract(
        **draft.model_dump(),
        id=f"contract-{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        family_id=family_id or "",
        filename=filename[:200],
        confirmed=False,
        created_at=_now(),
    )
    await store.put("contracts", contract.model_dump(mode="json"))
    return contract


async def own_contract(store: Store, user_id: str, contract_id: str) -> Contract:
    doc = await store.get("contracts", contract_id)
    if doc is None or doc.get("user_id") != user_id:
        raise DomainError(404, NOT_FOUND)
    return Contract.model_validate(doc)


def validate_required(d: ContractDraft) -> None:
    missing = [k for k in ("kind", "employer_name", "start_date") if getattr(d, k) is None]
    if d.fte is None and d.gross_monthly is None:
        missing.append("fte_or_gross")
    if missing:
        labels = ", ".join(FIELD_LABELS[m] for m in missing)
        raise DomainError(422, f"Uzupełnij brakujące dane umowy: {labels}.")
    if d.end_date and d.start_date and d.end_date < d.start_date:
        raise DomainError(422, "Data zakończenia umowy nie może być wcześniejsza niż data rozpoczęcia.")


def merge_insurance(profile: ParentProfile, c: Contract) -> ParentProfile:
    """Dodaje do profilu wpis ubezpieczenia zgodny z umową albo aktualizuje istniejący (ten sam płatnik i rodzaj)."""
    key = (c.kind, normalize_name(c.employer_name))
    for ins in profile.insurance:
        if (ins.kind, normalize_name(ins.payer)) == key:
            if c.gross_monthly is not None:
                ins.contribution_base = c.gross_monthly
            if c.kind == "mandate" and c.voluntary_sickness is not None:
                ins.voluntary_sickness = c.voluntary_sickness
            return profile
    profile.insurance.append(
        Insurance(
            kind=c.kind,
            payer=c.employer_name,
            contribution_base=c.gross_monthly or 0.0,
            voluntary_sickness=c.voluntary_sickness if c.kind == "mandate" else None,
            since=c.start_date,
        )
    )
    return profile


async def confirm(store: Store, user_id: str, family_id: str | None, contract_id: str, body: ContractDraft) -> Contract:
    current = await own_contract(store, user_id, contract_id)
    if not current.confirmed:
        await ensure_capacity(store, user_id)
    validate_required(body)
    data = body.model_dump(exclude={"missing"})
    if data.get("indefinite") is True:
        data["end_date"] = None
    if data.get("kind") != "mandate":
        data["voluntary_sickness"] = None
    contract = Contract(
        **data,
        missing=[],
        id=current.id,
        user_id=user_id,
        family_id=family_id or current.family_id,
        filename=current.filename,
        confirmed=True,
        created_at=current.created_at,
    )
    await store.put("contracts", contract.model_dump(mode="json"))

    profile_doc = await store.get("profiles", user_id)
    if profile_doc is not None:
        profile = merge_insurance(ParentProfile.model_validate({**profile_doc, "user_id": user_id}), contract)
        await store.put("profiles", {**profile.model_dump(mode="json"), "id": user_id})
    return contract


async def family_contracts(store: Store, viewer_id: str, family_id: str | None) -> list[Contract]:
    """Zatwierdzone umowy całej rodziny. Nazwę pliku widzi tylko właściciel umowy."""
    out: list[Contract] = []
    for uid in await family_member_ids(store, viewer_id, family_id):
        for c in await user_contracts(store, uid):
            if c.user_id != viewer_id:
                c = c.model_copy(update={"filename": None})
            out.append(c)
    return out


async def family_risks(store: Store, viewer_id: str, family_id: str | None, today: date) -> list[Risk]:
    """Ryzyka obojga rodziców (profil ZUS + zatwierdzone umowy + dzieci rodziny), bez duplikatów."""
    children = (
        [Child.model_validate(d) for d in await store.find("children", family_id=family_id)] if family_id else []
    )
    seen: dict[str, Risk] = {}
    for uid in await family_member_ids(store, viewer_id, family_id):
        doc = await store.get("profiles", uid)
        if doc is None:
            continue
        profile = ParentProfile.model_validate({**doc, "user_id": uid})
        for r in evaluate_risks(profile, await user_contracts(store, uid), children, today):
            seen.setdefault(r.id, r)
    return sorted(seen.values(), key=lambda r: (SEVERITY_ORDER[r.severity], r.deadline or date.max, r.id))
