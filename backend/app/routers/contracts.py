"""Skan i zatwierdzanie umów oraz ostrzeżenia o ryzyku (plan 04)."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.datastructures import UploadFile

from ..ai.limits import GuardContext, ai_guard, record_usage
from ..ai.llm import LLM, LLMError, get_llm, track_usage
from ..models.contract import Contract, ContractDraft, Risk
from ..security import Principal, require_parent
from ..seed import demo_handlers  # noqa: F401  (rejestruje odpowiedź demo dla contract_scan)
from ..services.contract_extract import FEATURE, MIME_BY_TYPE, detect_type, extract_contract
from ..services.contracts import ContractService
from ..storage import Store, get_store

router = APIRouter(tags=["contracts"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MULTIPART_OVERHEAD = 64 * 1024
UNSUPPORTED = "Nieobsługiwany plik. Wgraj PDF, PNG, JPG albo plik tekstowy z umową."
_NEUTRAL_TYPES = {"", "application/octet-stream"}


def get_service(store: Store = Depends(get_store)) -> ContractService:
    return ContractService(store)


class ScanOut(BaseModel):
    draft_id: str
    draft: ContractDraft
    filename: str


def _display_name(raw: str | None) -> str:
    """Nazwa tylko do wyświetlenia (nigdy do ścieżek): bez katalogów i znaków sterujących."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:120]
    return name or "umowa"


def _too_large() -> HTTPException:
    return HTTPException(413, "Plik jest za duży. Maksymalny rozmiar to 5 MB.")


async def _read_upload(request: Request) -> tuple[str, bytes, str]:
    """Czyta pojedynczy plik z pola `file`. Rozmiar sprawdzamy po Content-Length, zanim zaczniemy
    parsować multipart (parser nie ma limitu rozmiaru pliku), a potem jeszcze po faktycznym odczycie."""
    try:
        declared_len = int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(411, "Brak informacji o rozmiarze pliku. Spróbuj ponownie.") from None
    if declared_len > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD:
        raise _too_large()
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(422, "Wyślij plik w polu „file”.")
    try:
        form = await request.form(max_files=1, max_fields=1)
    except Exception:  # noqa: BLE001 - zepsuty multipart; treści nie logujemy
        raise HTTPException(422, "Nie udało się odebrać pliku. Spróbuj ponownie.") from None
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(422, "Wyślij plik w polu „file”.")
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise _too_large()
        return _display_name(upload.filename), content, (upload.content_type or "").split(";")[0].strip().lower()
    finally:
        await form.close()


def _check_type(content: bytes, declared: str) -> None:
    """Typ wg magic bytes musi istnieć i zgadzać się z deklarowanym (octet-stream/puste = ufamy sniffingowi)."""
    detected = detect_type(content)
    if detected is None:
        raise HTTPException(415, UNSUPPORTED)
    if declared not in _NEUTRAL_TYPES and declared != MIME_BY_TYPE[detected]:
        raise HTTPException(415, UNSUPPORTED)


@router.post("/api/contracts/scan")
async def scan_contract(
    request: Request,
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard(FEATURE)),
    llm: LLM = Depends(get_llm),
    svc: ContractService = Depends(get_service),
) -> ScanOut:
    try:
        await svc.ensure_capacity(p)
        filename, content, declared = await _read_upload(request)
        _check_type(content, declared)
        with track_usage() as usage:
            try:
                draft = await extract_contract(llm, filename, content, declared)
            except LLMError as e:
                raise HTTPException(503, str(e), headers={"Retry-After": "30"}) from None
            finally:
                await record_usage(ctx, usage)  # model mógł już zużyć tokeny także przy odmowie
        saved = await svc.save_draft(p, filename, draft)
        return ScanOut(draft_id=saved.id, draft=draft, filename=filename)
    except BaseException:
        await ctx.release()  # no-op, jeśli rezerwacja została już rozliczona
        raise


@router.post("/api/contracts/{contract_id}/confirm")
async def confirm_contract(
    contract_id: str,
    body: ContractDraft,
    p: Principal = Depends(require_parent),
    svc: ContractService = Depends(get_service),
) -> Contract:
    return await svc.confirm(p, contract_id, body)


@router.get("/api/contracts")
async def list_contracts(
    p: Principal = Depends(require_parent), svc: ContractService = Depends(get_service)
) -> list[Contract]:
    return await svc.list_confirmed(p)


@router.delete("/api/contracts/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: str,
    p: Principal = Depends(require_parent),
    svc: ContractService = Depends(get_service),
) -> Response:
    await svc.delete(p, contract_id)
    return Response(status_code=204)


@router.get("/api/risks")
async def list_risks(
    p: Principal = Depends(require_parent), svc: ContractService = Depends(get_service)
) -> list[Risk]:
    return await svc.family_risks(p.family_id, date.today())

