"""Poczta „ZUS / urzędy” (plan 09): symulowana skrzynka (domyślnie podłączona), wątki wniosków, sync."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..ai.limits import GuardContext, ai_guard, get_budget, record_usage
from ..ai.llm import LLM, get_llm
from ..errors import DomainError
from ..mail.sim_inbox import SimInbox
from ..services.applications import list_family_applications
from ..security import Principal, require_parent
from ..seed.mail_seed import ensure_seed_inbox
from ..services.mail_sync import SyncReport, sync_family_mail
from ..storage import Store, get_store

router = APIRouter(prefix="/api/mail", tags=["mail"])

SCOPE_NOTE = (
    "Czytamy tylko wiadomości w sprawie wysłanych przez Was wniosków i tylko po dacie wysyłki: odpowiedzi "
    "w wątku wniosku, maile z dokładnego adresu odbiorcy oraz z domen instytucji (np. zus.pl, gov.pl). "
    "Nigdy nie czytamy reszty skrzynki ani maili z całych domen publicznych (gmail.com, onet.pl, wp.pl…)."
)


def get_inbox(request: Request) -> SimInbox:
    return SimInbox(request.app.state.store)


def _family(p: Principal) -> str:
    if not p.family_id:
        raise DomainError(404, "Najpierw załóż rodzinę albo dołącz do niej.")
    return p.family_id


@router.get("/status")
async def status(
    p: Principal = Depends(require_parent), inbox: SimInbox = Depends(get_inbox)
) -> dict:
    fid = _family(p)
    return {
        "connected": True,
        "provider": "gmail-sim",
        "simulated": True,
        "address": await inbox.address(fid, p.user_id),
        "scope_note": SCOPE_NOTE,
    }


@router.get("/threads")
async def threads(
    p: Principal = Depends(require_parent), store: Store = Depends(get_store), inbox: SimInbox = Depends(get_inbox)
) -> list[dict]:
    """Tylko wątki powiązane z wnioskami (wysłany mail + przetworzone odpowiedzi), najnowsze najpierw."""
    fid = _family(p)
    await ensure_seed_inbox(store, fid, datetime.now(timezone.utc))
    users = {}
    msgs = sorted(await inbox.list_messages(fid), key=lambda m: (m.received_at, m.id))
    out = []
    for app in await list_family_applications(store, fid):
        if app.sent_at is None:
            continue
        if app.applicant_id not in users:
            u = await store.get("users", app.applicant_id)
            users[app.applicant_id] = (u or {}).get("name", "Rodzic")
        related = [
            m for m in msgs
            if (m.folder == "sent" and app.thread_id and m.thread_id == app.thread_id)
            or (m.folder == "inbox" and m.related_application_id == app.id)
        ]
        out.append(
            {
                "application": {
                    "id": app.id,
                    "form_code": app.form_code,
                    "status": app.status,
                    "applicant_id": app.applicant_id,
                    "applicant_name": users[app.applicant_id],
                    "recipient_email": app.recipient_email,
                    "sent_at": app.sent_at.isoformat(),
                },
                "needs_review": any(m.needs_review for m in related),
                "messages": [
                    m.model_dump(
                        mode="json",
                        include={
                            "id", "folder", "from_addr", "to_addr", "subject", "body", "received_at",
                            "classification_status", "classification_confidence", "classification_summary",
                            "needs_review",
                        },
                    )
                    for m in related
                ],
            }
        )
    out.sort(key=lambda t: t["application"]["sent_at"], reverse=True)
    return out


async def _sync(store: Store, inbox: SimInbox, llm: LLM, fid: str, ctx: GuardContext, request: Request) -> SyncReport:
    # rezerwacja guarda pokrywa pierwsze klasyfikacje; kolejne idą z budżetu (rezerwacja per wiadomość)
    await ctx.release()
    return await sync_family_mail(store, inbox, llm, fid, datetime.now(timezone.utc), budget=get_budget(request))


@router.post("/sync")
async def sync(
    request: Request,
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard("mail_classify")),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
    inbox: SimInbox = Depends(get_inbox),
) -> SyncReport:
    try:
        fid = _family(p)
    except DomainError:
        await ctx.release()
        raise
    return await _sync(store, inbox, llm, fid, ctx, request)


@router.post("/simulate-replies")
async def simulate_replies(
    request: Request,
    p: Principal = Depends(require_parent),
    ctx: GuardContext = Depends(ai_guard("mail_classify")),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
    inbox: SimInbox = Depends(get_inbox),
) -> dict:
    """Demo: dostarcza od razu wszystkie oczekujące odpowiedzi urzędów, potem synchronizuje."""
    try:
        fid = _family(p)
        delivered = await inbox.deliver_due(fid, datetime.now(timezone.utc), force=True)
    except BaseException:
        await ctx.release()
        raise
    report = await _sync(store, inbox, llm, fid, ctx, request)
    return {"delivered": delivered, **report.model_dump()}
