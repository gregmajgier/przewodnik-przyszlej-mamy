"""Czat „Zapytaj mRodzinę”: POST /api/chat (SSE), historia i usuwanie sesji (tylko właściciel).

Limity: `ai_guard("chat")` (limity użytkownika/IP, budżet tokenów, równoległość); wiadomość <= 2000 znaków;
historia do modelu <= 20 wiadomości; maks. 5 wywołań narzędzi na turę. Tożsamość narzędzi pochodzi z tokena
(`ToolContext`), nigdy z argumentów modelu. Nie logujemy treści wiadomości.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..ai.limits import GuardContext, ai_guard, record_usage, warsaw_today
from ..ai.llm import LLM, LLMMessage, Usage, get_llm
from ..ai.tools import ToolContext
from ..mcp_server import McpClient
from ..security import Principal, require_parent
from ..seed import demo_chat  # noqa: F401  (rejestruje handler trybu demo dla funkcji „chat”)
from ..services.chat import GENERIC_ERROR, McpLike, build_system_prompt, run_chat_turn
from ..storage import Store, get_store

logger = logging.getLogger("mrodzina.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_MESSAGE_CHARS = 2000
MAX_SESSION_MESSAGES = 200
NOT_FOUND = "Nie znaleziono rozmowy."

_guard = ai_guard("chat")
_background: set[asyncio.Task] = set()


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _own_session(store: Store, principal: Principal, session_id: str) -> dict:
    """Sesja rozmowy należy do rodzica, który ją założył; cudza = 404 (nie ujawniamy istnienia)."""
    doc = await store.get("chat_sessions", session_id)
    if doc is None or doc.get("user_id") != principal.user_id:
        raise HTTPException(404, NOT_FOUND)
    return doc


async def event_stream(
    *,
    store: Store,
    principal: Principal,
    llm: LLM,
    mcp: McpLike,
    session: dict | None,
    message: str,
    guard: GuardContext,
    today: date,
) -> AsyncIterator[str]:
    """Strumień SSE jednej tury. Sesja jest zapisywana zawsze (także przy przerwaniu połączenia): wiadomość
    użytkownika od razu, odpowiedź — pełna albo częściowa z flagą `interrupted`. Nie ma stanu „w trakcie”."""
    if session is None:
        session = {
            "id": uuid.uuid4().hex,
            "user_id": principal.user_id,
            "family_id": principal.family_id,
            "title": message[:60],
            "messages": [],
            "created_at": _now(),
        }
    history = [
        LLMMessage(role=m["role"], content=m["content"])
        for m in session["messages"]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    session["messages"].append({"role": "user", "content": message, "at": _now()})
    session["updated_at"] = _now()
    await store.put("chat_sessions", session)

    usage = Usage()
    answer: list[str] = []
    sources: list[dict] = []
    outcome = "interrupted"  # done | error | interrupted

    async def finalize() -> None:
        try:
            text = "".join(answer)
            if outcome == "done":
                session["messages"].append({"role": "assistant", "content": text, "sources": sources, "at": _now()})
            elif text:
                session["messages"].append({"role": "assistant", "content": text, "interrupted": True, "at": _now()})
            session["messages"] = session["messages"][-MAX_SESSION_MESSAGES:]
            session["updated_at"] = _now()
            await store.put("chat_sessions", session)
        except Exception as e:  # noqa: BLE001
            logger.error("Nie zapisano sesji czatu: %s", type(e).__name__)
        if usage.total > 0:
            await record_usage(guard, usage)
        else:
            await guard.release()

    try:
        yield _sse("session", {"session_id": session["id"]})
        async for ev in run_chat_turn(
            llm, mcp, history, message, system=build_system_prompt(today), usage=usage
        ):
            if ev.type == "token":
                answer.append(ev.data["text"])
            elif ev.type == "sources":
                sources = ev.data["sources"]
            elif ev.type == "done":
                outcome = "done"
            elif ev.type == "error":
                outcome = "error"
                answer.clear()
            yield _sse(ev.type, ev.data)
    except Exception as e:  # noqa: BLE001
        logger.error("Błąd strumienia czatu: %s", type(e).__name__)
        outcome = "error"
        answer.clear()
        yield _sse("error", {"message": GENERIC_ERROR})
    finally:
        # także przy GeneratorExit/anulowaniu (rozłączenie klienta): zapis nie może zostać przerwany
        task = asyncio.ensure_future(finalize())
        _background.add(task)
        task.add_done_callback(_background.discard)
        await asyncio.shield(task)


@router.post("")
async def chat(
    body: ChatIn,
    principal: Principal = Depends(require_parent),
    guard: GuardContext = Depends(_guard),
    store: Store = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> StreamingResponse:
    message = body.message.strip()
    try:
        if not message:
            raise HTTPException(422, "Napisz pytanie, a spróbuję pomóc.")
        if len(message) > MAX_MESSAGE_CHARS:
            raise HTTPException(422, f"Wiadomość jest za długa (maksymalnie {MAX_MESSAGE_CHARS} znaków).")
        session = await _own_session(store, principal, body.session_id) if body.session_id else None
        if session is not None and len(session["messages"]) >= MAX_SESSION_MESSAGES:
            raise HTTPException(409, "Ta rozmowa jest już bardzo długa. Zacznij nową rozmowę.")
    except HTTPException:
        await guard.release()  # zapytanie odrzucone przed użyciem modelu: zwracamy rezerwację tokenów
        raise
    today = warsaw_today()
    mcp = McpClient(ToolContext(principal=principal, store=store, today=today))
    stream = event_stream(
        store=store, principal=principal, llm=llm, mcp=mcp, session=session, message=message, guard=guard, today=today
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str, principal: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> dict:
    doc = await _own_session(store, principal, session_id)
    return {
        "id": doc["id"],
        "title": doc.get("title", ""),
        "messages": doc["messages"],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str, principal: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> Response:
    await _own_session(store, principal, session_id)
    await store.delete("chat_sessions", session_id)
    return Response(status_code=204)
