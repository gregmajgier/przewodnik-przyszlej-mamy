# NOTES-02 — decyzje i odstępstwa (plan 02 brama AI)

## Rozszerzenia kontraktów (nie łamią planu)
- `app/ai/llm.py`: dodatkowo `track_usage()` (context manager zbierający `Usage` ze wszystkich wywołań LLM
  w bieżącym kontekście, także z `structured()`, które zwraca tylko model) i `Usage.total`. Wywołujący
  funkcje AI: `with track_usage() as u: ...; await record_usage(ctx, u)`.
- `FakeLLM.script(...)` zwraca `self` (łańcuchowanie), wyczerpany skrypt -> `LLMError`; `calls` to lista
  `FakeCall(messages, feature, tools, schema)`. `FakeLLM`/`DemoLLM` przy `structured` przyjmują też gotową
  instancję `BaseModel`. Podmiana w testach: `app.dependency_overrides[get_llm] = lambda: fake`.
- `DemoLLM.structured` dla funkcji bez handlera rzuca `LLMError` (nie ma sensownej odpowiedzi), `chat` zwraca
  grzeczny komunikat „tryb demo”. Handler może być sync lub async.
- `Settings` (`config.py`) dostało: `azure_openai_*`, `ai_max_output_tokens` (1500), `ai_user_rpm/daily`,
  `ai_ip_rpm`, **`ai_ip_daily` (1000, dodane — spec wymaga okna dziennego także dla IP)**, `ai_daily_tokens`,
  `ai_max_input_chars`, `trust_proxy_hops`, `ai_reserve_tokens`, `ai_max_inflight`.
- `RateLimiter.hit(key, limit, window_s, scope="user")` + `hit_all(rules)` (atomowe „wszystko albo nic” —
  odrzucone żądanie nie zużywa żadnego z okien), `sweep()`, `size()`.
- `GuardContext(user_id, ip, feature, budget, reservation)` — `budget`/`reservation` dodatkowe pola (dla `record_usage`), `await ctx.release()`.
- `enforce_max_input(*texts)` -> HTTP 422 (wołane w endpointach AI; guard nie widzi body).
- `main.py`: `_include_routers` woła opcjonalny hak `install(app)` z każdego modułu routera (zamiast jednej
  linii specyficznej dla AI). `routers/ai_status.py`: `GET /api/ai/status` -> `{mode: demo|live, available}`
  oraz handler `AILimitExceeded` -> 429 + `Retry-After`.
- `app/tools/__init__.py` jest tylko pakietem; logika auto-importu jest w `app.ai.tools.load_all_tools()`
  (unika cyklicznych importów). `@tool` wymaga funkcji `async` i poprawnego JSON Schema (inaczej
  `TypeError`/`ValueError` przy rejestracji); duplikat nazwy -> `ValueError`. `call_tool` rzuca wyłącznie
  `ToolError`; komunikaty walidacji nie zawierają wartości argumentów (mogą być PII).
  `app/tools/_example.py` ma `register_example()` (wołane tylko w testach).

## Bezpieczeństwo / zachowanie
- Fail-closed: dowolny błąd limitera lub budżetu (np. Store/Cosmos niedostępny) -> HTTP 503 + `Retry-After`,
  nigdy przepuszczenie. `record_usage` nie rzuca (log z typem błędu); kolejne `check()` i tak padnie, jeśli
  Store nie działa.
- Kolejność w `ai_guard`: slot równoległości, rezerwacja budżetu, limity (odmowa budżetu nie zużywa limitów; odmowa limitu zwraca rezerwację).
- Logi zawierają tylko `feature` i typ wyjątku — nigdy treści promptów/odpowiedzi. Błędy SDK -> `LLMError`
  z ogólnym komunikatem (`from None`, bez łańcucha z treścią).
- IP: `TRUST_PROXY_HOPS` (zamiast boolowskiego `TRUST_PROXY`, po przeglądzie bezpieczeństwa). 0 = ignoruj
  `X-Forwarded-For`; N = N-ty wpis od prawej (ACA ingress: 1); za mało wpisów / niepoprawny adres = `request.client.host`.
- Budżet tokenów jest rezerwacyjny: `TokenBudget.reserve(n) -> Reservation` (check+increment atomowo pod
  `asyncio.Lock`), `Reservation.settle(actual)` / `release()` (idempotentne, wzajemnie wykluczające się).
  `ai_guard(feature, reserve_tokens=None)` rezerwuje `AI_RESERVE_TOKENS` (4000) i jest zależnością z `yield`;
  `record_usage` rozlicza, `ctx.release()` zwraca. Niezrealizowana rezerwacja zostaje (ostrożnie).
  Odmowa limitu użytkownika/IP lub błąd limitera zwraca rezerwację i slot. `check()`/`record()` zostały
  (bez rezerwacji). `AI_MAX_INFLIGHT` (20): `InflightGate`, nadmiar -> 429 „Asystent AI jest teraz mocno obciążony”.
- Limiter jest per proces (replika); budżet tokenów w Store (`ai_usage`, id = data Europe/Warsaw), zapis
  serializowany `asyncio.Lock` w procesie; między replikami wymaga atomowego inkrementu w bazie (Store go nie ma).
- `ai_guard` wymaga zalogowania (dowolna rola) — publiczne `/jaskolka` nie używa AI.

## Niezweryfikowane
- `FoundryLLM` testowany wyłącznie atrapą klienta `openai` (bez prawdziwego wywołania Azure);
  `max_completion_tokens` i `response_format=json_schema` zależą od wersji API/modelu wdrożenia
  (domyślnie `2024-10-21`, `gpt-4o-mini`).
- Wersje `openai==3.57.0`, `jsonschema==4.26.0`, `tzdata==2026.6` przypięte z tego, co pip zainstalował lokalnie
  (Python 3.14); `tzdata` dodane, bo obraz `python:3.12-slim` może nie mieć strefy Europe/Warsaw.
  Obraz Dockera nie był budowany.
