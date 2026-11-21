"""Umowy rodziny: szkice ze skanu, zatwierdzanie, aktualizacja profilu i ostrzeżenia o ryzyku.

Samego pliku nie przechowujemy — po ekstrakcji zostają wyłącznie dane zatwierdzone przez rodzica.
Każda operacja jest ograniczona do rodziny wołającego; zmieniać umowę może tylko jej właściciel.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from ..errors import DomainError
from ..models.contract import Contract, ContractDraft, Risk
from ..models.family import Child
from ..models.profile import Insurance, ParentProfile
from ..security import Principal
from ..storage import Store
from .risk import SEVERITY_ORDER, evaluate_risks, normalize_name

MAX_CONTRACTS_PER_PARENT = 5
DRAFT_TTL = timedelta(days=1)

NO_FAMILY = "Najpierw załóż rodzinę albo dołącz do niej — umowy zapisujemy w profilu rodziny."
FIELD_LABELS = {
    "kind": "rodzaj umowy",
    "employer_name": "nazwa pracodawcy",
    "start_date": "data rozpoczęcia",
    "fte_or_gross": "wymiar etatu lub wynagrodzenie",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContractService:
    def __init__(self, store: Store) -> None:
        self.store = store

    # ---------- dostęp ----------

    @staticmethod
    def _need_family(p: Principal) -> str:
        if not p.family_id:
            raise DomainError(409, NO_FAMILY)
        return p.family_id

    async def _own(self, p: Principal, contract_id: str) -> Contract:
        """Umowa musi istnieć i należeć do wołającego (inna rodzina i partner -> 403)."""
        doc = await self.store.get("contracts", contract_id)
        if doc is None:
            raise DomainError(404, "Nie znaleziono takiej umowy.")
        if doc.get("user_id") != p.user_id or doc.get("family_id") != p.family_id:
            raise DomainError(403, "Ta umowa należy do innej osoby.")
        return Contract.model_validate(doc)

    # ---------- skan ----------

    async def ensure_capacity(self, p: Principal) -> None:
        """Limit 5 umów na rodzica (zatwierdzone + oczekujące szkice); porządkuje stare szkice."""
        self._need_family(p)
        cutoff = _now() - DRAFT_TTL
        mine = await self.store.find("contracts", user_id=p.user_id)
        active = 0
        for d in mine:
            if not d.get("confirmed") and datetime.fromisoformat(d["created_at"]) < cutoff:
                await self.store.delete("contracts", d["id"])
            else:
                active += 1
        if active >= MAX_CONTRACTS_PER_PARENT:
            raise DomainError(
                409,
                f"Możesz dodać maksymalnie {MAX_CONTRACTS_PER_PARENT} umów. "
                "Usuń jedną z listy, aby dodać kolejną.",
            )

    async def save_draft(self, p: Principal, filename: str, draft: ContractDraft) -> Contract:
        contract = Contract(
            **draft.model_dump(),
            id=f"contract-{uuid.uuid4().hex[:12]}",
            user_id=p.user_id,
            family_id=self._need_family(p),
            filename=filename,
            confirmed=False,
            created_at=_now(),
        )
        await self.store.put("contracts", contract.model_dump(mode="json"))
        return contract

    # ---------- zatwierdzenie ----------

    @staticmethod
    def _validate(d: ContractDraft) -> ContractDraft:
        missing = [
            FIELD_LABELS[key]
            for key, absent in (
                ("kind", d.kind is None),
                ("employer_name", d.employer_name is None),
                ("start_date", d.start_date is None),
                ("fte_or_gross", d.fte is None and d.gross_monthly is None),
            )
            if absent
        ]
        if missing:
            raise DomainError(422, "Uzupełnij brakujące dane umowy: " + ", ".join(missing) + ".")
        if d.end_date is not None and d.end_date < d.start_date:
            raise DomainError(422, "Data zakończenia nie może być wcześniejsza niż data rozpoczęcia.")
        indefinite, end_date = d.indefinite, d.end_date
        if end_date is not None:
            indefinite = False
        elif indefinite is True:
            end_date = None
        return d.model_copy(update={"indefinite": indefinite, "end_date": end_date, "missing": []})

    async def confirm(self, p: Principal, contract_id: str, body: ContractDraft) -> Contract:
        current = await self._own(p, contract_id)
        if current.confirmed:
            raise DomainError(409, "Ta umowa została już zatwierdzona.")
        data = self._validate(body)
        contract = current.model_copy(update={**data.model_dump(), "confirmed": True})
        await self.store.put("contracts", contract.model_dump(mode="json"))
        await self._merge_into_profile(contract)
        return contract

    async def _merge_into_profile(self, c: Contract) -> None:
        doc = await self.store.get("profiles", c.user_id)
        if doc is None:
            return
        profile = ParentProfile.model_validate({**doc, "user_id": c.user_id})
        match = next(
            (i for i in profile.insurance if i.kind == c.kind and normalize_name(i.payer) == normalize_name(c.employer_name)),
            None,
        )
        if match is not None:
            # dane z ZUS (podstawa składek, data od) są nadrzędne; uzupełniamy to, czego ZUS nie podał
            if c.voluntary_sickness is not None:
                match.voluntary_sickness = c.voluntary_sickness
            if not match.contribution_base and c.gross_monthly:
                match.contribution_base = c.gross_monthly
        else:
            profile.insurance.append(
                Insurance(
                    kind=c.kind,
                    payer=c.employer_name,
                    contribution_base=c.gross_monthly or 0.0,
                    voluntary_sickness=c.voluntary_sickness if c.kind != "employment" else None,
                    since=c.start_date,
                )
            )
        await self.store.put("profiles", {**profile.model_dump(mode="json"), "id": c.user_id})

    # ---------- odczyt / usuwanie ----------

    async def list_confirmed(self, p: Principal) -> list[Contract]:
        """Zatwierdzone umowy rodziny; nazwa pliku tylko dla właściciela."""
        if not p.family_id:
            return []
        docs = await self.store.find("contracts", family_id=p.family_id, confirmed=True)
        out = []
        for d in sorted(docs, key=lambda d: (d["created_at"], d["id"])):
            c = Contract.model_validate(d)
            out.append(c if c.user_id == p.user_id else c.model_copy(update={"filename": None}))
        return out

    async def delete(self, p: Principal, contract_id: str) -> None:
        contract = await self._own(p, contract_id)
        await self.store.delete("contracts", contract_id)
        if contract.confirmed:
            await self._unmerge_from_profile(contract)

    async def _unmerge_from_profile(self, c: Contract) -> None:
        """Usuwa wpis ubezpieczenia utworzony przez zatwierdzenie tej umowy. Wpisy z ZUS (inna podstawa
        składek lub data) zostają, podobnie jak wpis współdzielony z inną zatwierdzoną umową."""
        doc = await self.store.get("profiles", c.user_id)
        if doc is None:
            return
        profile = ParentProfile.model_validate({**doc, "user_id": c.user_id})
        payer = normalize_name(c.employer_name)
        for other in await self.store.find("contracts", user_id=c.user_id, confirmed=True):
            if other["kind"] == c.kind and normalize_name(other["employer_name"]) == payer:
                return
        kept = [
            i
            for i in profile.insurance
            if not (
                i.kind == c.kind
                and normalize_name(i.payer) == payer
                and i.since == c.start_date
                and i.contribution_base == (c.gross_monthly or 0.0)
            )
        ]
        if len(kept) != len(profile.insurance):
            profile.insurance = kept
            await self.store.put("profiles", {**profile.model_dump(mode="json"), "id": c.user_id})

    # ---------- ryzyka ----------

    async def family_risks(self, family_id: str | None, today: date) -> list[Risk]:
        if not family_id:
            return []
        family = await self.store.get("families", family_id)
        if family is None:
            return []
        children = [Child.model_validate(d) for d in await self.store.find("children", family_id=family_id)]
        risks: list[Risk] = []
        for uid in family["member_ids"]:
            doc = await self.store.get("profiles", uid)
            if doc is None:
                continue
            profile = ParentProfile.model_validate({**doc, "user_id": uid})
            contracts = [
                Contract.model_validate(d)
                for d in await self.store.find("contracts", user_id=uid, family_id=family_id, confirmed=True)
            ]
            risks.extend(evaluate_risks(profile, contracts, children, today))
        risks.sort(key=lambda r: (SEVERITY_ORDER[r.severity], r.deadline or date.max, r.id))
        return risks
