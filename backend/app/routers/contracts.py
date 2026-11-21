"""Umowy rodzica (plan 04): skan (AI), zatwierdzenie, lista, usuwanie oraz ostrzeżenia o ryzyku."""

from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from starlette.datastructures import UploadFile

from ..ai.limits import GuardContext, ai_guard, record_usage
from ..ai.llm import LLM, Usage, get_llm, track_usage
from ..errors import DomainError
from ..models.contract import Contract, ContractDraft, Risk
from ..security import Principal, require_parent
from ..services import contracts as svc
from ..services.contract_extract import extract_contract, safe_filename
from ..storage import Store, get_store

router = APIRouter(prefix="/api", tags=["contracts"])

MAX_FILE_BYTES = 5 * 1024 * 1024
TOO_LARGE = "Plik jest za duży — maksymalnie 5 MB."
MULTIPART_OVERHEAD = 64 * 1024


async def _read_upload(request: Request) -> tuple[str, bytes, str]:
    """Czyta pojedynczy plik z pola `file`. Rozmiar sprawdzamy po Content-Length, zanim zaczniemy parsować
    multipart (parser nie ma limitu rozmiaru pliku), i jeszcze raz po faktycznym odczycie."""
    try:
        declared_len = int(request.headers.get("content-length", ""))
    except ValueError:
        raise DomainError(411, "Brak informacji o rozmiarze pliku. Spróbuj ponownie.") from None
    if declared_len > MAX_FILE_BYTES + MULTIPART_OVERHEAD:
        raise DomainError(413, TOO_LARGE)
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise DomainError(422, "Wyślij plik w polu „file”.")
    try:
        form = await request.form(max_files=1, max_fields=1)
    except Exception:  # noqa: BLE001 - zepsuty multipart; treści nie logujemy
        raise DomainError(422, "Nie udało się odebrać pliku. Spróbuj ponownie.") from None
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise DomainError(422, "Wyślij plik w polu „file”.")
        content = await upload.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise DomainError(413, TOO_LARGE)
        return safe_filename(upload.filename), content, upload.content_type or ""
    finally:
        await form.close()


@router.post("/contracts/scan")
async def scan(
    request: Request,
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard("contract_scan")),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
) -> dict:
    """Odczytuje umowę i zapisuje szkic (`confirmed=false`). Sam plik nie jest przechowywany."""
    usage = Usage()
    try:
        await svc.ensure_capacity(store, p.user_id)
        filename, content, content_type = await _read_upload(request)
        with track_usage() as usage:
            draft = await extract_contract(llm, filename, content, content_type)
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
