# Brama AI, limity zapytań i rejestr narzędzi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jedna warstwa dostępu do modeli (Azure AI Foundry + tryb demo + fake do testów), trzypoziomowe limity zapytań oraz rejestr narzędzi MCP używany przez kolejne plany.

**Architecture:** `app/ai/llm.py` (protokół `LLM`, `FoundryLLM`, `DemoLLM`, `FakeLLM`), `app/ai/limits.py` (okna czasowe + dzienny budżet tokenów + dependency `ai_guard`), `app/ai/tools.py` (rejestr `@tool`, `call_tool`) z auto-importem `app/tools/*`.

**Tech Stack:** `openai` SDK (AzureOpenAI / Foundry endpoint), pydantic, pytest.

**Spec:** §14 (AI, limity), §11a (narzędzia). Konwencje: `00-conventions.md`.

## Global Constraints
- Limity (spec §14), wszystkie funkcje AI: (1) na użytkownika i IP, okno minutowe i dzienne; (2) dzienny budżet tokenów całej aplikacji — po przekroczeniu AI odpowiada łagodnym komunikatem „spróbuj jutro”, reszta aplikacji działa; (3) twardy TPM po stronie wdrożenia Foundry (dokumentacja, nie kod).
- Domyślne wartości (env): `AI_USER_RPM=20`, `AI_USER_DAILY=300`, `AI_IP_RPM=60`, `AI_DAILY_TOKENS=500000`, `AI_MAX_INPUT_CHARS=8000`.
- Bez `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_API_KEY` → `DemoLLM`; testy → `FakeLLM`. Nigdy nie loguj treści promptów ani odpowiedzi.

## Review Focus
- Równoległe żądania tego samego użytkownika nie przekraczają limitu (atomowość licznika).
- IP za proxy: używaj `X-Forwarded-For` wg `TRUST_PROXY_HOPS` (N-ty wpis od prawej; zmienione po przeglądzie bezpieczeństwa).
- Budżet tokenów odświeża się o północy (strefa Europe/Warsaw) i przeżywa restart (zapis w `ai_usage` w Store).
- Przekroczony limit → HTTP 429 z `detail` po polsku i nagłówkiem `Retry-After`, nie 500.
- Model zwraca niepoprawny JSON → `structured()` próbuje 1 raz ponownie, potem `LLMError`, nie wyjątek surowy.

---

### Task 1: Protokół LLM, FakeLLM, DemoLLM
**Files:** Create `backend/app/ai/__init__.py`, `backend/app/ai/llm.py`, `backend/tests/test_llm.py`.
**Interfaces:** Produces
```python
class ToolSpec(BaseModel): name: str; description: str; parameters: dict   # JSON Schema
class ToolCall(BaseModel): id: str; name: str; arguments: dict
class LLMMessage(BaseModel): role: Literal["system","user","assistant","tool"]; content: str | None = None; tool_calls: list[ToolCall] = []; tool_call_id: str | None = None
class Usage(BaseModel): prompt_tokens: int = 0; completion_tokens: int = 0
class LLMResult(BaseModel): text: str | None; tool_calls: list[ToolCall]; usage: Usage
class LLMError(Exception): ...
class LLM(Protocol):
    async def chat(self, messages: list[LLMMessage], *, feature: str, tools: list[ToolSpec] | None = None) -> LLMResult
    async def structured(self, messages: list[LLMMessage], schema: type[T], *, feature: str) -> T   # T: BaseModel
def get_llm() -> LLM          # FastAPI dependency; Foundry gdy skonfigurowany, inaczej DemoLLM
def register_demo_handler(feature: str, fn: Callable[[list[LLMMessage]], LLMResult | BaseModel]) -> None
class FakeLLM: script(self, *responses: LLMResult | BaseModel | Exception); calls: list[...]
```
- [ ] Testy: `test_fake_llm_returns_scripted_in_order`, `test_fake_llm_records_calls`, `test_structured_parses_json_into_model`, `test_structured_retries_once_on_invalid_json_then_llmerror`, `test_demo_llm_uses_registered_handler`, `test_demo_llm_unknown_feature_returns_polite_fallback`.
- [ ] `FoundryLLM` używa `openai.AsyncAzureOpenAI(azure_endpoint, api_key, api_version)`; `structured` z `response_format` json_schema; `usage` z odpowiedzi. Konfiguracja w `Settings`: `azure_openai_endpoint`, `azure_openai_api_key`, `azure_openai_deployment="gpt-4o-mini"`, `azure_openai_api_version`. Dodaj `openai` do `requirements.txt`. Commit.

### Task 2: Limity zapytań
**Files:** Create `backend/app/ai/limits.py`, `backend/tests/test_limits.py`; Modify `backend/app/config.py`.
**Interfaces:** Produces
```python
class AILimitExceeded(Exception): retry_after: int; scope: Literal["user","ip","budget"]
class RateLimiter:  # sliding window, async-safe (asyncio.Lock)
    def __init__(self, clock: Callable[[], float] = time.time)
    async def hit(self, key: str, limit: int, window_s: int) -> None   # rzuca AILimitExceeded
class TokenBudget:
    def __init__(self, store: Store, daily_limit: int, today: Callable[[], date])
    async def check(self) -> None; async def record(self, tokens: int) -> None
def ai_guard(feature: str) -> Callable   # FastAPI dependency: sprawdza user RPM/dzienny, IP RPM, budżet; zwraca GuardContext(user_id, ip, feature)
async def record_usage(ctx: GuardContext, usage: Usage) -> None
```
Handler wyjątku `AILimitExceeded` rejestrowany w `create_app`-niezależny sposób: moduł `app/routers/ai_status.py` (`router` + `app.add_exception_handler` nie jest dostępne w routerze — dlatego eksportuj `install(app)` wołane przez `create_app` jeśli istnieje; dodaj tę jedną linię do `main.py`). Komunikaty: user/ip → „Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.”, budget → „Asystent AI jest dziś przeciążony. Spróbuj jutro — reszta aplikacji działa normalnie.”.
- [ ] Testy z wstrzykniętym zegarem: `test_allows_up_to_limit_then_raises`, `test_window_slides_after_expiry`, `test_keys_isolated`, `test_concurrent_hits_never_exceed_limit` (asyncio.gather 50 wywołań, limit 20 → dokładnie 20 OK), `test_budget_blocks_after_limit_and_resets_next_day`, `test_budget_persists_in_store`, `test_guard_returns_429_with_retry_after_and_polish_detail`, `test_ip_from_forwarded_for_only_when_trusted`, `test_max_input_chars_rejected_422`.
- [ ] Commit.

### Task 3: Rejestr narzędzi
**Files:** Create `backend/app/ai/tools.py`, `backend/app/tools/__init__.py` (auto-import: `pkgutil` po modułach pakietu), `backend/app/tools/_example.py` (tylko w testach, nie auto-importowany — nazwa z `_`), `backend/tests/test_tools.py`.
**Interfaces:** Produces
```python
@dataclass class ToolContext: principal: Principal; store: Store; today: date
class RegisteredTool: name, description, parameters: dict, fn: Callable[[ToolContext, dict], Awaitable[Any]]
def tool(name: str, description: str, parameters: dict) -> Callable   # dekorator
def list_tools() -> list[ToolSpec]
async def call_tool(name: str, args: dict, ctx: ToolContext) -> Any    # waliduje args wg JSON Schema (jsonschema), rzuca ToolError
class ToolError(Exception)
def load_all_tools() -> None     # importuje app.tools.* (idempotentne)
```
- [ ] Testy: `test_register_and_list`, `test_duplicate_name_raises`, `test_call_validates_arguments`, `test_call_unknown_tool_raises_toolerror`, `test_load_all_tools_idempotent`, `test_tool_receives_context`. Dodaj `jsonschema` do `requirements.txt`.
- [ ] Commit.

### Task 4: Dokumentacja i weryfikacja
- [ ] `backend/.env.example`: zmienne AI i limitów; `docs/dev.md`: sekcja „AI i limity” + zalecenie ustawienia TPM na wdrożeniu Foundry (poziom 3). `pytest -q` zielone. Commit `docs: ai gateway`.
