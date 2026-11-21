"""Wnioski rodzica: szkic z prefillem, pytania o braki, podgląd PDF, podpis, wysyłka i plan agenta w makiecie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..ai.limits import GuardContext, ai_guard, record_usage
from ..ai.llm import LLM, LLMError, get_llm, track_usage
from ..mail import MailProvider, get_mail
from ..models.application import AnswersIn, Application, ApplicationCreate, ApplicationPatch
from ..security import Principal, require_parent
from ..services.agent_plan import build_plan
from ..services.applications import ApplicationService, cancel_drafts_for_child  # noqa: F401  (API dla planu 10)
from ..services.prefill import portal_meta, portal_schema
from ..storage import Store, get_store

router = APIRouter(prefix="/api/applications", tags=["applications"])

_HIDDEN = {"signed_digest"}


def get_service(store: Store = Depends(get_store), mail: MailProvider = Depends(get_mail)) -> ApplicationService:
    return ApplicationService(store, mail)


def _out(app: Application) -> dict:
    return app.model_dump(mode="json", exclude=_HIDDEN)


@router.get("/forms")
async def forms(p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)) -> dict:
    """Katalog wniosków z kreatorem: kanały, wymagane dziecko i rekomendowana kolejność dla rodzica."""
    return await svc.forms(p.user_id)


@router.get("/portals/{portal_id}")
async def portal(portal_id: str, _: Principal = Depends(require_parent)) -> dict:
    """Schemat makiety portalu (tytuł, rodzaj, pola) — używany przez trasy `/sim/*`."""
    meta = portal_meta(portal_id)
    fields = [f.model_dump(include={"id", "label", "type", "required", "choices", "default"}) for f in portal_schema(portal_id)]
    return {"portal_id": portal_id, **meta, "fields": fields}


@router.get("")
async def list_applications(
    p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> list[dict]:
    """Wnioski całej rodziny (oboje rodzice widzą wszystkie; `applicant_id` mówi, kto składa)."""
    return [_out(a) for a in await svc.list_for_family(p.user_id)]


@router.post("", status_code=201)
async def create_application(
    body: ApplicationCreate, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> dict:
    return _out(await svc.create(p.user_id, body))


@router.get("/{app_id}")
async def get_application(
    app_id: str, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> dict:
    return _out(await svc.get(p.user_id, app_id))


@router.patch("/{app_id}")
async def patch_application(
    app_id: str,
    body: ApplicationPatch,
    p: Principal = Depends(require_parent),
    svc: ApplicationService = Depends(get_service),
) -> dict:
    """Edycja pól w podglądzie (tylko ten wniosek) i zmiana kanału."""
    return _out(await svc.patch(p.user_id, app_id, body))


@router.post("/{app_id}/answers")
async def answer(
    app_id: str,
    body: AnswersIn,
    p: Principal = Depends(require_parent),
    svc: ApplicationService = Depends(get_service),
) -> dict:
    """Odpowiedzi na pytania o brakujące dane — zapisują się w profilu, więc nie pytamy drugi raz."""
    return _out(await svc.answer(p.user_id, app_id, body.answers))


@router.get("/{app_id}/pdf")
async def preview_pdf(
    app_id: str, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> Response:
    code, pdf = await svc.pdf(p.user_id, app_id)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{code}.pdf"', "Cache-Control": "no-store"},
    )


@router.post("/{app_id}/sign")
async def sign(
    app_id: str, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> dict:
    """Symulowany podpis Profilem Zaufanym."""
    return _out(await svc.sign(p.user_id, app_id))


@router.post("/{app_id}/submit")
async def submit(
    app_id: str, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> dict:
    """Wysyłka (idempotentna: ponowne wywołanie nie wysyła drugi raz)."""
    return _out(await svc.submit(p.user_id, app_id))


@router.post("/{app_id}/agent-plan")
async def agent_plan(
    app_id: str,
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard("agent_plan")),
    llm: LLM = Depends(get_llm),
    svc: ApplicationService = Depends(get_service),
) -> dict:
    """Plan wypełnienia makiety portalu: kroki (pole → wartość) i pytania o braki (`blocked`)."""
    try:
        app, prefill, portal_id = await svc.portal_context(p.user_id, app_id)
        with track_usage() as usage:
            plan = await build_plan(llm, portal_id, prefill)
    except LLMError as e:
        await ctx.release()
        raise HTTPException(503, str(e)) from None
    except Exception:
        await ctx.release()
        raise
    await record_usage(ctx, usage)
    meta = portal_meta(portal_id)
    return {
        "application_id": app.id,
        "portal_id": portal_id,
        "title": meta.get("title"),
        "kind": meta.get("kind"),
        **plan.model_dump(mode="json"),
    }


@router.post("/{app_id}/portal-submitted")
async def portal_submitted(
    app_id: str, p: Principal = Depends(require_parent), svc: ApplicationService = Depends(get_service)
) -> dict:
    """Callback makiety portalu po zatwierdzeniu przez rodzica (idempotentny)."""
    return _out(await svc.portal_submitted(p.user_id, app_id))
