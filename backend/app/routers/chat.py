"""Czat „Zapytaj mRodzinę”: SSE (`POST /api/chat`) oraz sesje rozmów rodzica."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..ai.limits import WARSAW, GuardContext, ai_guard, record_usage
from ..ai.llm import LLM, Usage, get_llm
from ..ai.tools import ToolContext
from ..mcp_server import McpClient
from ..security import Principal, require_parent
from ..services import chat as chat_service
from ..services.chat import MAX_MESSAGE_CHARS, ChatEvent
from ..storage import Store, get_store

logger = logging.getLogger("mrodzina.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

MSG_EMPTY = "Wpisz pytanie."
MSG_TOO_LONG = f"Wiadomość jest za długa (maksymalnie {MAX_MESSAGE_CHARS} znaków)."
MSG_GENERIC_ERROR = "Coś poszło nie tak po stronie asystenta. Spróbuj ponownie za chwilę."


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str


def _sse(event: ChatEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(
    body: ChatIn,
    principal: Principal = Depends(require_parent),
    guard: GuardContext = Depends(ai_guard("chat")),
    store: Store = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> StreamingResponse:
    message = body.message.strip()
    try:
        if not message:
            raise HTTPException(422, MSG_EMPTY)
        if len(message) > MAX_MESSAGE_CHARS:
            raise HTTPException(422, MSG_TOO_LONG)
        session = (
            await chat_service.get_session(store, principal, body.session_id)
            if body.session_id
            else chat_service.new_session(principal)
        )
    except Exception:
        await guard.release()  # odrzucone żądanie nie zużywa budżetu tokenów
        raise

    history = chat_service.history_messages(session)
    today = datetime.now(WARSAW).date()
    mcp = McpClient(ToolContext(principal, store, today))
    system = chat_service.build_system_prompt(today)

    async def stream() -> AsyncIterator[str]:
        usage = Usage()
        answer: list[str] = []
        sources: list[dict] = []
        try:
            async for event in chat_service.run_chat_turn(llm, mcp, history, message, system=system, usage=usage):
                if event.type == "token":
                    answer.append(event.data["text"])
                elif event.type == "sources":
                    sources = event.data["sources"]
                elif event.type == "done":
                    # zapis dopiero po całej turze: przerwane połączenie nie zostawia rozmowy „w trakcie”
                    await chat_service.save_turn(store, session, message, "".join(answer), sources)
                    event.data["session_id"] = session["id"]
                yield _sse(event)
        except Exception as e:  # noqa: BLE001 - treści rozmowy nie logujemy
            logger.error("Błąd tury czatu: %s", type(e).__name__)
            yield _sse(ChatEvent(type="error", data={"message": MSG_GENERIC_ERROR}))
        finally:
            if usage.total > 0:
                await record_usage(guard, usage)
            else:
                await guard.release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions")
async def list_sessions(principal: Principal = Depends(require_parent), store: Store = Depends(get_store)) -> list[dict]:
    docs = await store.find("chat_sessions", user_id=principal.user_id)
    docs.sort(key=lambda d: d["updated_at"], reverse=True)
    return [
        {
            "id": d["id"],
            "updated_at": d["updated_at"],
            "preview": next((m["content"][:80] for m in d["messages"] if m["role"] == "user"), ""),
        }
        for d in docs
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str, principal: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> dict:
    return await chat_service.get_session(store, principal, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str, principal: Principal = Depends(require_parent), store: Store = Depends(get_store)
) -> Response:
    await chat_service.get_session(store, principal, session_id)
    await store.delete("chat_sessions", session_id)
    return Response(status_code=204)

