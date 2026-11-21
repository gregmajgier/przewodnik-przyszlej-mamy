"""Jedna warstwa dostępu do modeli: FoundryLLM (produkcja), DemoLLM (offline), FakeLLM (testy).

Zasady: nigdy nie logujemy treści promptów ani odpowiedzi; błędy SDK są zamieniane na `LLMError`
bez treści wiadomości.
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import settings

logger = logging.getLogger("mrodzina.ai")

T = TypeVar("T", bound=BaseModel)

LLM_UNAVAILABLE = "Asystent AI jest chwilowo niedostępny. Spróbuj ponownie za chwilę."
LLM_BAD_OUTPUT = "Asystent AI zwrócił niepoprawną odpowiedź. Spróbuj ponownie."
DEMO_FALLBACK = (
    "To jest tryb demo — asystent AI nie jest tu podłączony do modelu, "
    "więc nie mogę odpowiedzieć na to pytanie."
)


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict  # JSON Schema


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = []
    tool_call_id: str | None = None
    images: list[str] = []  # data URL-e (np. "data:image/png;base64,..."); część obrazowa wiadomości użytkownika


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMResult(BaseModel):
    text: str | None = None
    tool_calls: list[ToolCall] = []
    usage: Usage = Usage()


class LLMError(Exception):
    """Błąd modelu (niedostępność, niepoprawna odpowiedź). Komunikat jest bezpieczny dla użytkownika."""


class LLM(Protocol):
    async def chat(
        self, messages: list[LLMMessage], *, feature: str, tools: list[ToolSpec] | None = None
    ) -> LLMResult: ...

    async def structured(self, messages: list[LLMMessage], schema: type[T], *, feature: str) -> T: ...


# --- zliczanie tokenów -------------------------------------------------------------------------

_usage_sink: ContextVar[Usage | None] = ContextVar("mrodzina_ai_usage_sink", default=None)


@contextmanager
def track_usage() -> Iterator[Usage]:
    """Zbiera zużycie tokenów ze wszystkich wywołań LLM (także `structured`) w bieżącym kontekście.

    Użycie: `with track_usage() as u: ...; await record_usage(ctx, u)`.
    """
    total = Usage()
    token = _usage_sink.set(total)
    try:
        yield total
    finally:
        _usage_sink.reset(token)


def _report(usage: Usage) -> None:
    sink = _usage_sink.get()
    if sink is not None:
        sink.prompt_tokens += usage.prompt_tokens
        sink.completion_tokens += usage.completion_tokens


# --- wspólna logika structured() ---------------------------------------------------------------

_RETRY_HINT = LLMMessage(
    role="system",
    content="Poprzednia odpowiedź nie była poprawnym JSON zgodnym ze schematem. "
    "Zwróć wyłącznie poprawny JSON.",
)


def _coerce(raw: LLMResult | BaseModel, schema: type[T]) -> T:
    """Zamienia odpowiedź (tekst JSON albo gotowy model) na `schema`; rzuca ValidationError."""
    if isinstance(raw, LLMResult):
        _report(raw.usage)
        return schema.model_validate_json(raw.text or "")
    if isinstance(raw, schema):
        return raw
    return schema.model_validate(raw.model_dump())


class _BaseLLM:
    async def _complete(
        self,
        messages: list[LLMMessage],
        *,
        feature: str,
        tools: list[ToolSpec] | None = None,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult | BaseModel:
        raise NotImplementedError

    async def chat(
        self, messages: list[LLMMessage], *, feature: str, tools: list[ToolSpec] | None = None
    ) -> LLMResult:
        raw = await self._complete(messages, feature=feature, tools=tools)
        if isinstance(raw, LLMResult):
            _report(raw.usage)
            return raw
        return LLMResult(text=raw.model_dump_json())

    async def structured(self, messages: list[LLMMessage], schema: type[T], *, feature: str) -> T:
        convo = list(messages)
        for attempt in range(2):  # pierwsza próba + dokładnie jedna ponowna
            raw = await self._complete(convo, feature=feature, schema=schema)
            try:
                return _coerce(raw, schema)
            except (ValidationError, ValueError):
                logger.warning("LLM structured: niepoprawny JSON (feature=%s, próba %d)", feature, attempt + 1)
                if attempt == 0:
                    convo = [*messages, _RETRY_HINT]
        raise LLMError(LLM_BAD_OUTPUT)


# --- FoundryLLM --------------------------------------------------------------------------------


def _to_openai_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""})
            continue
        content: Any = m.content
        if m.images:
            content = [{"type": "text", "text": m.content or ""}] + [
                {"type": "image_url", "image_url": {"url": url}} for url in m.images
            ]
        item: dict[str, Any] = {"role": m.role, "content": content}
        if m.role == "assistant" and m.tool_calls:
            item["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
        out.append(item)
    return out


class FoundryLLM(_BaseLLM):
    """Azure AI Foundry / Azure OpenAI przez `openai.AsyncAzureOpenAI`."""

    def __init__(self, client: Any = None, deployment: str | None = None) -> None:
        self._client = client
        self._deployment = deployment or settings.azure_openai_deployment

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncAzureOpenAI

            self._client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                timeout=60.0,
                max_retries=2,
            )
        return self._client

    async def _complete(
        self,
        messages: list[LLMMessage],
        *,
        feature: str,
        tools: list[ToolSpec] | None = None,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self._deployment,
            "messages": _to_openai_messages(messages),
            "max_completion_tokens": settings.ai_max_output_tokens,
        }
        if settings.azure_openai_reasoning_effort:
            kwargs["reasoning_effort"] = settings.azure_openai_reasoning_effort
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            }
        try:
            completion = await self._get_client().chat.completions.create(**kwargs)
            message = completion.choices[0].message
            calls = [
                ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments or "{}"))
                for tc in (message.tool_calls or [])
            ]
            usage = Usage(
                prompt_tokens=getattr(completion.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(completion.usage, "completion_tokens", 0) or 0,
            )
            return LLMResult(text=message.content, tool_calls=calls, usage=usage)
        except LLMError:
            raise
        except json.JSONDecodeError:
            raise LLMError(LLM_BAD_OUTPUT) from None
        except Exception as e:  # noqa: BLE001 - SDK rzuca wiele typów; logujemy tylko typ (bez treści)
            logger.error("Błąd wywołania Foundry (feature=%s): %s", feature, type(e).__name__)
            raise LLMError(LLM_UNAVAILABLE) from None


# --- DemoLLM -----------------------------------------------------------------------------------

DemoHandler = Callable[[list[LLMMessage]], "LLMResult | BaseModel"]
_demo_handlers: dict[str, DemoHandler] = {}


def register_demo_handler(feature: str, fn: DemoHandler) -> None:
    """Rejestruje kanoniczną odpowiedź trybu demo dla funkcji `feature` (nadpisuje poprzednią)."""
    _demo_handlers[feature] = fn


class DemoLLM(_BaseLLM):
    """Tryb offline: odpowiedzi z handlerów zarejestrowanych per funkcja; poza tym grzeczny komunikat."""

    async def _complete(
        self,
        messages: list[LLMMessage],
        *,
        feature: str,
        tools: list[ToolSpec] | None = None,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult | BaseModel:
        handler = _demo_handlers.get(feature)
        if handler is None:
            if schema is not None:
                raise LLMError("Ta funkcja AI nie jest dostępna w trybie demo.")
            return LLMResult(text=DEMO_FALLBACK)
        result = handler(messages)
        if inspect.isawaitable(result):
            result = await result
        return result


# --- FakeLLM (testy) ---------------------------------------------------------------------------


@dataclass
class FakeCall:
    messages: list[LLMMessage]
    feature: str
    tools: list[ToolSpec] | None = None
    schema: type[BaseModel] | None = None


@dataclass
class FakeLLM(_BaseLLM):
    """Skryptowane odpowiedzi w kolejności; wyjątek ze skryptu jest rzucany. `calls` rejestruje wywołania."""

    calls: list[FakeCall] = field(default_factory=list)
    _script: list[LLMResult | BaseModel | Exception] = field(default_factory=list)

    def script(self, *responses: LLMResult | BaseModel | Exception) -> FakeLLM:
        self._script.extend(responses)
        return self

    async def _complete(
        self,
        messages: list[LLMMessage],
        *,
        feature: str,
        tools: list[ToolSpec] | None = None,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult | BaseModel:
        self.calls.append(FakeCall(list(messages), feature, tools, schema))
        if not self._script:
            raise LLMError("FakeLLM: skrypt odpowiedzi wyczerpany.")
        nxt = self._script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


# --- fabryka -----------------------------------------------------------------------------------

_demo = DemoLLM()
_foundry_cache: dict[tuple[str, str, str, str], FoundryLLM] = {}


def get_llm() -> LLM:
    """Zależność FastAPI: Foundry gdy skonfigurowany (endpoint + klucz), inaczej DemoLLM.

    Testy podmieniają ją przez `app.dependency_overrides[get_llm] = lambda: FakeLLM()...`.
    """
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        key = (
            settings.azure_openai_endpoint,
            settings.azure_openai_api_key,
            settings.azure_openai_deployment,
            settings.azure_openai_api_version,
        )
        if key not in _foundry_cache:
            _foundry_cache.clear()
            _foundry_cache[key] = FoundryLLM()
        return _foundry_cache[key]
    return _demo
