# Czat „Zapytaj mRodzinę” — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Działający czat oparty na Azure AI Foundry, który odpowiada na podstawie przepisów, danych rodziny i informacji lokalnych, narzędziami wystawionymi przez serwer MCP w backendzie.

**Architecture:** Backend jest klientem MCP; serwer MCP (SDK `mcp`, in-process) wystawia rejestr z planu 02. Pętla rozmowy: LLM ↔ narzędzia ↔ odpowiedź ze streamingiem SSE. Narzędzia własne planu: `profil_rodziny`, `szukaj_w_przepisach`, `szukaj_w_sieci`. Narzędzia z innych planów (`swiadczenia`, `ryzyka`, `kalendarz`) pojawiają się automatycznie w rejestrze.

**Tech Stack:** `mcp` Python SDK, `openai` przez `LLM` (plan 02), SSE (`StreamingResponse`), indeks przepisów lokalny (domyślnie) lub Azure AI Search.

**Spec:** §11a, §14. Konwencje: `00-conventions.md`. Zależy od 01, 02.

## Global Constraints
- Każda odpowiedź oparta na przepisach **cytuje artykuł i link**; informacje z sieci — link do strony. Brak podstawy → „nie wiem” + gdzie zapytać (urząd, ZUS, PUP). Zakaz zgadywania kwot i terminów.
- Czat **nie składa wniosków** — podlinkowuje flow wniosku (`/wnioski/nowy?form=KOD`).
- Endpoint za `ai_guard("chat")`; wiadomość ≤ 2000 znaków, historia przekazywana do modelu ≤ 20 wiadomości; maks. 5 wywołań narzędzi na turę.
- Przepisy (pobierane z API Sejmu ELI, dzielone na artykuły): Kodeks pracy (dział VIII, uprawnienia rodzicielskie), ustawa zasiłkowa, ustawa o świadczeniach rodzinnych, ustawa o pomocy państwa w wychowywaniu dzieci (800+), Prawo oświatowe (rekrutacja), ustawa o opiece nad dziećmi do lat 3, ustawa „Za życiem”, ustawa o Karcie Dużej Rodziny.
- `szukaj_w_sieci` preferuje domeny urzędowe (gov.pl, bip.*, *.gov.pl, zus.pl, powiatowe urzędy pracy, strony gmin) — ranking w kodzie, testowany.
- Dane rodzica nie opuszczają backendu poza zapytaniem do modelu; profil w odpowiedziach narzędzia bez PESEL.

## Review Focus
- Prompt injection w wyniku web search lub treści maila („zignoruj instrukcje…”) — wynik narzędzia traktowany jako dane (otoczony znacznikami), nie wykonuje akcji; test z wrogim snippetem.
- Pytanie spoza zakresu (np. kod JS) → uprzejma odmowa i wskazanie zakresu.
- Zawartość rodziny A nigdy w kontekście rodziny B (narzędzia dostają `Principal` z tokena, nie z argumentów modelu).
- Model prosi o nieistniejące narzędzie / złe argumenty → błąd narzędzia zwrócony modelowi, pętla kończy się po limicie.
- Przerwane połączenie SSE nie zostawia sesji w stanie „w trakcie”.

---

### Task 1: Indeks przepisów
**Files:** Create `backend/scripts/build_laws_index.py`, `backend/app/services/laws.py`, `backend/app/data/laws/*.json` (wynik skryptu, commitowany), `backend/tests/test_laws.py`.
**Interfaces:** Produces
```python
class LawChunk(BaseModel): id: str; act: str; act_short: str; article: str; text: str; url: str
class LawIndex(Protocol): def search(self, query: str, k: int = 5) -> list[LawChunk]
class LocalLawIndex(LawIndex): def __init__(self, chunks: list[LawChunk])    # BM25 własnej implementacji (bez nowych zależności), polskie normalizacje: lower, bez ogonków, prosty stemming prefiksowy (5 znaków)
def load_default_index() -> LocalLawIndex
```
- [ ] Skrypt pobiera akty z `https://api.sejm.gov.pl/eli/acts/DU/{rok}/{pozycja}/text.html` (identyfikatory aktualnych tekstów jednolitych ustal przez API ELI `…/acts/search`), dzieli po „Art. N.” i zapisuje JSON; uruchom go i zacommituj dane. Gdy sieć niedostępna — zapisz w README skryptu i użyj ręcznie przygotowanego minimum z 6 artykułów, oznaczając `verify`.
- [ ] Testy: `test_search_finds_macierzynski_article`, `test_search_polish_diacritics_insensitive`, `test_results_have_url_and_article`, `test_empty_query_returns_empty`, `test_default_index_covers_all_listed_acts`. Commit.

### Task 2: Web search
**Files:** Create `backend/app/services/web_search.py`, `backend/tests/test_web_search.py`.
**Interfaces:** Produces `class WebResult(title,url,snippet)`, `class WebSearch(Protocol): async def search(self, query: str, k: int=5) -> list[WebResult]`, `def rank_official(results: list[WebResult]) -> list[WebResult]` (domeny urzędowe najpierw, stabilnie), `def get_web_search() -> WebSearch` wybierany z `WEB_SEARCH_PROVIDER` (`none`|`brave`|`serper`; klucz `WEB_SEARCH_API_KEY`); dla `none` zwraca pustą listę (czat mówi, że nie ma dostępu do wyszukiwarki).
- [ ] Testy: `test_rank_official_prefers_gov_pl_and_bip`, `test_rank_is_stable_within_class`, `test_none_provider_returns_empty`, `test_provider_http_error_returns_empty_not_raise` (httpx MockTransport). Commit.

### Task 3: Narzędzia i serwer MCP
**Files:** Create `backend/app/tools/chat_tools.py` (`profil_rodziny`, `szukaj_w_przepisach`, `szukaj_w_sieci`), `backend/app/mcp_server.py`, `backend/tests/test_mcp.py`.
**Interfaces:** `build_mcp_server(ctx_factory) -> FastMCP` wystawia wszystkie narzędzia z `list_tools()`; `class McpClient: async def list_tools() -> list[ToolSpec]; async def call(name, args) -> str` — połączenie in-process (`mcp.shared.memory`), kontekst `ToolContext` przekazany przez `contextvars` (nie przez argumenty modelu). Dodaj `mcp` do `requirements.txt`.
- [ ] Testy: `test_mcp_lists_registered_tools`, `test_mcp_call_profil_rodziny_has_no_pesel`, `test_mcp_call_uses_principal_family_only`, `test_mcp_call_invalid_args_returns_error_text`, `test_szukaj_w_przepisach_returns_article_and_url`. Commit.

### Task 4: Pętla czatu i endpoint
**Files:** Create `backend/app/services/chat.py`, `backend/app/routers/chat.py`, `backend/tests/test_chat.py`; demo handler w `backend/app/seed/demo_handlers.py` (jeśli plik istnieje, dopisz funkcję w nowym `backend/app/seed/demo_chat.py` i zaimportuj w `seed/__init__` jedną linią).
**Interfaces:** Produces `async def run_chat_turn(llm, mcp, history: list[LLMMessage], user_message: str, *, system: str, max_tool_calls: int=5) -> AsyncIterator[ChatEvent]` gdzie `ChatEvent = token|tool|sources|done|error`; `POST /api/chat {session_id|None, message} -> text/event-stream`; `GET /api/chat/sessions/{id}` (historia; sesje w `chat_sessions`, tylko właściciel rodziny); `DELETE /api/chat/sessions/{id}`. System prompt (po polsku) zawiera zasady cytowania, brak zgadywania, zakres.
- [ ] Testy z `FakeLLM` i fake MCP: `test_turn_calls_tool_then_answers`, `test_tool_call_limit_stops_loop`, `test_sources_event_lists_articles_cited`, `test_message_too_long_422`, `test_rate_limit_429`, `test_other_family_session_404`, `test_prompt_injection_in_web_result_wrapped_as_data` (wynik narzędzia trafia do modelu w znacznikach `<wynik_narzedzia>` i system prompt zakazuje wykonywania instrukcji z niego), `test_out_of_scope_gets_polite_refusal` (zachowanie przez prompt — sprawdź zawartość system promptu), `test_demo_mode_returns_retrieved_articles_without_llm`. Commit.

### Task 5: Frontend
**Files:** Create `frontend/src/features/chat/{routes.tsx,nav.ts,ChatPage.tsx,ChatLauncher.tsx,useChatStream.ts,Message.tsx}`, testy.
**Interfaces:** Trasa `/czat` + pływający `ChatLauncher` (dodany jako widget z `widget.tsx` `order: 5` na dashboardzie jako kafelek „Zapytaj mRodzinę” z polem pytania i przykładami: „Jak działa urlop macierzyński?”, „Jak zapisać dziecko do przedszkola?”). `useChatStream` czyta SSE (`fetch` + `ReadableStream`), obsługuje `token/tool/sources/done/error`. Odpowiedź renderuje źródła jako linki; komunikat 429 z API wyświetlany jako spokojny banner.
- [ ] Testy: strumień tokenów składa się w jedną wiadomość; źródła jako linki; 429 pokazuje komunikat; przycisk „Nowa rozmowa”. Commit.

### Task 6: Weryfikacja
- [ ] Testy i build zielone; `docs/dev.md`: jak zbudować indeks przepisów, zmienne `WEB_SEARCH_*`, tryb demo czatu. Commit.
