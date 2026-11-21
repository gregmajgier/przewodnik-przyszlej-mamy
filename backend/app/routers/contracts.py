"""Umowy rodzica (plan 04): skan (AI), zatwierdzenie, lista, usuwanie oraz ostrzeżenia o ryzyku."""

from datetime import date

from fastapi import APIRouter, Depends, File, Response, UploadFile

from ..ai.limits import GuardContext, ai_guard, record_usage
from ..ai.llm import LLM, Usage, get_llm, track_usage
from ..errors import DomainError
from ..models.contract import Contract, ContractDraft, Risk
from ..security import Principal, require_parent
from ..services import contracts as svc
from ..services.contract_extract import extract_contract
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["contracts"])

MAX_FILE_BYTES = 5 * 1024 * 1024
TOO_LARGE = "Plik jest za duży — maksymalnie 5 MB."


@router.post("/contracts/scan")
async def scan(
    file: UploadFile = File(...),
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard("contract_scan")),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
) -> dict:
    """Odczytuje umowę i zapisuje szkic (`confirmed=false`). Sam plik nie jest przechowywany."""
    usage = Usage()
    try:
        await svc.ensure_capacity(store, p.user_id)
        content = await file.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise DomainError(413, TOO_LARGE)
        filename = (file.filename or "umowa").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        with track_usage() as usage:
            draft = await extract_contract(llm, filename, content, file.content_type or "")
    except BaseException:
        # model zdążył odpowiedzieć (np. „to nie umowa”) -> rozliczamy zużycie; inaczej zwracamy rezerwację
        if usage.total:
            await record_usage(ctx, usage)
        else:
            await ctx.release()
        raise
    await record_usage(ctx, usage)
    saved = await svc.save_draft(store, p.user_id, p.family_id, filename, draft)
    return {"draft_id": saved.id, "draft": draft.model_dump(mode="json"), "filename": saved.filename}


@router.post("/contracts/{contract_id}/confirm")
async def confirm(
    contract_id: str,
    body: ContractDraft,
    p: Principal = Depends(require_parent),
    store: Store = Depends(get_store),
) -> Contract:
    return await svc.confirm(store, p.user_id, p.family_id, contract_id, body)


@router.get("/contracts")
async def list_contracts(p: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> list[Contract]:
    return await svc.family_contracts(store, p.user_id, p.family_id)


@router.delete("/contracts/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: str, p: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> Response:
    await svc.own_contract(store, p.user_id, contract_id)
    await store.delete("contracts", contract_id)
    return Response(status_code=204)


@router.get("/risks")
async def risks(p: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> list[Risk]:
    return await svc.family_risks(store, p.user_id, p.family_id, date.today())
