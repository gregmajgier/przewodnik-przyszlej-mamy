# mRodzina — przewodnik developera

## Szybki start (bez Azure)

Wszystko działa lokalnie bez żadnej konfiguracji: dane w pamięci procesu (`MemoryStore`),
symulowany mObywatel/ZUS.

```bash
# backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000/docs

# frontend (drugi terminal)
cd frontend
npm ci
npm run dev                                   # http://localhost:5173
npm test -- --run && npm run lint && npm run build
```

Wymagania: Python 3.12+, Node 22+.

## Persony i konta

- **Rodzice (symulowany mObywatel)** — ekran `/logowanie`: `persona-nowak-anna` (mama, w ciąży, e-ZLA kod B)
  i `persona-nowak-piotr` (tata). Dane z „ZUS” powstają przy pierwszym logowaniu, daty względem dnia
  uruchomienia. Nowe persony = nowy wpis w `backend/app/seed/personas.py`.
- **Urzędnicy** (`POST /api/auth/official`): `urzednik.krakow@mrodzina.local` (gmina Kraków) i
  `urzednik.malopolska@mrodzina.local` (województwo). W trybie `dev` hasło to `demo1234`
  (`OFFICIAL_DEFAULT_PASSWORD`).
- Dołączanie drugiego rodzica: Anna zakłada rodzinę (`/start`), kopiuje kod z `/rodzina`; Piotr loguje się,
  wybiera „Dołącz do rodziny” (`/dolacz`), a Anna akceptuje prośbę w `/rodzina`.

## Punkty rozszerzeń (dla kolejnych funkcji)

- Backend: nowy plik `backend/app/routers/<nazwa>.py` z `router = APIRouter(prefix="/api/...")` jest
  dołączany automatycznie. Zależności: `require_parent`, `require_official`, `current_principal`
  (`app/security.py`), `get_store` (`app/storage.py`). Błędy domenowe: `raise DomainError(status, "po polsku")`.
- Dane startowe: `seed_all` w `backend/app/seed/__init__.py` (idempotentne, stałe `id`).
- Frontend: `frontend/src/features/<nazwa>/` z `routes.tsx` (trasy publiczne oznacz
  `handle: { public: true }`), opcjonalnie `nav.ts`, `widget.tsx` (kafelek dashboardu) oraz
  `profile-section.tsx` (sekcja w „Moje dane”) — wszystko wykrywane automatycznie.
- Testy backendu: fixtury `store`, `client` i funkcje `login(client, persona_id)`,
  `login_official(client, email)` w `backend/tests/conftest.py` (`from conftest import login`).

## Konfiguracja (zmienne środowiskowe, `backend/.env`)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `ENV` | `dev` | `dev` = lokalnie/testy. Dowolna inna wartość (np. `prod`) włącza walidację fail-closed. |
| `SESSION_SECRET` | `dev-secret-change-me` | Klucz HMAC tokenów sesji. Poza `dev` (albo gdy ustawiony `COSMOS_ENDPOINT`) aplikacja **nie wystartuje**, jeśli jest domyślny lub krótszy niż 32 znaki. W `dev` tylko ostrzeżenie w logu. |
| `OFFICIAL_DEFAULT_PASSWORD` | `demo1234` | Hasło początkowe kont urzędników. Seed tworzy tylko brakujące konta i **nigdy nie nadpisuje** istniejących haseł. Poza `dev` (lub z Cosmos) hasło musi mieć min. 12 znaków i różnić się od `demo1234`, inaczej seedowanie urzędników jest pomijane (ostrzeżenie w logu); dodatkowo istniejące konta z hasłem `demo1234` są przy starcie **wyłączane** (`disabled: true`, logowanie → 401). |
| `SESSION_TTL_HOURS` | `12` | Ważność tokenu. |
| `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE` | puste | Puste = `MemoryStore`. Ustawione = `CosmosStore` i tryb produkcyjny. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Dozwolone originy (JSON). |

Losowy sekret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

**Wdrożenie:** ustaw `ENV=prod`, własny `SESSION_SECRET` i `OFFICIAL_DEFAULT_PASSWORD`
(jako sekrety Container App, nigdy w repo).

## AI i limity (plan 02)

Cała komunikacja z modelami idzie przez `backend/app/ai`:

- `get_llm()` (zależność FastAPI) — `FoundryLLM` gdy ustawione `AZURE_OPENAI_ENDPOINT` i `AZURE_OPENAI_API_KEY`,
  inaczej `DemoLLM`. Funkcje rejestrują odpowiedzi demo: `register_demo_handler("czat", fn)`.
  W testach: `app.dependency_overrides[get_llm] = lambda: FakeLLM().script(LLMResult(text="..."))`.
  `llm.chat(messages, feature=..., tools=...)`, `llm.structured(messages, Model, feature=...)`
  (jedna ponowna próba przy niepoprawnym JSON, potem `LLMError`).
- `ai_guard("nazwa-funkcji")` — zależność endpointu AI: limit równoległych żądań, **rezerwacja** tokenów
  z dziennego budżetu (atomowa: check+increment), limity użytkownika i IP; zwraca `GuardContext`. Po wywołaniu
  modelu: `record_usage(ctx, usage)` (rozlicza rezerwację do rzeczywistego zużycia); gdy model nie został
  wywołany/zawiódł: `await ctx.release()` (zwrot rezerwacji). Dla `structured()` użyj
  `with track_usage() as usage: ...` i przekaż `usage` do `record_usage`. Długość wejścia:
  `enforce_max_input(tekst, ...)` (422 powyżej `AI_MAX_INPUT_CHARS`).
- Przekroczenie limitu: HTTP 429 + `Retry-After` + polski `detail`. Błąd wewnątrz limitera/budżetu: HTTP 503
  (fail-closed — nigdy nie przepuszcza bez limitu). `GET /api/ai/status` zwraca `{mode: demo|live}`.
- Narzędzia MCP: nowy plik `backend/app/tools/<nazwa>.py` z `@tool(nazwa, opis, json_schema)`
  (`async def fn(ctx: ToolContext, args: dict)`); `load_all_tools()` importuje je automatycznie,
  `call_tool(name, args, ctx)` waliduje argumenty (JSON Schema) i rzuca tylko `ToolError`.

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | puste | Puste = `DemoLLM`. |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o-mini` | Nazwa wdrożenia modelu w Foundry. |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | Wersja API. |
| `AI_MAX_OUTPUT_TOKENS` | `1500` | Maks. tokenów odpowiedzi. |
| `AI_USER_RPM` / `AI_USER_DAILY` | `20` / `300` | Zapytania AI na użytkownika: na minutę / na dobę (okno przesuwne). |
| `AI_IP_RPM` / `AI_IP_DAILY` | `60` / `1000` | To samo na adres IP. |
| `AI_DAILY_TOKENS` | `500000` | Dzienny budżet tokenów aplikacji (reset o północy Europe/Warsaw). |
| `AI_MAX_INPUT_CHARS` | `8000` | Maks. długość wejścia. |
| `AI_RESERVE_TOKENS` | `4000` | Tokeny rezerwowane z budżetu na żądanie AI (rozliczane po odpowiedzi). |
| `AI_MAX_INFLIGHT` | `20` | Maks. równoległych żądań AI w procesie (powyżej: 429 „obciążony”). |
| `TRUST_PROXY_HOPS` | `0` | `0` = ignoruj `X-Forwarded-For`. `N` = IP to N-ty wpis od **prawej** (Azure Container Apps ingress: `1`). Za mało wpisów/niepoprawny adres = adres połączenia. |

**Poziom 3 (twardy limit TPM) — konfiguracja poza kodem:** w Azure AI Foundry na wdrożeniu modelu ustaw
„Tokens per Minute Rate Limit” na wartość odpowiadającą budżetowi (np. `AI_DAILY_TOKENS` / 1440 × kilka),
jako ostatnią barierę kosztów, gdyby limity aplikacji zawiodły. Dodatkowo ustaw alert budżetowy na subskrypcji.

**Za proxy:** w Azure Container Apps ustaw `TRUST_PROXY_HOPS=1` — bez tego wszyscy użytkownicy dzieliby adres
proxy i limit IP byłby wspólny. Wpisy `X-Forwarded-For` z lewej strony kontroluje klient, więc nigdy z nich nie
korzystamy.

**Ograniczenia:** limiter okien jest w pamięci procesu — przy kilku replikach limit efektywny rośnie
proporcjonalnie (dla demo: jedna replika lub sticky ingress). Budżet tokenów jest w Store (Cosmos), więc jest
wspólny, ale rezerwacja jest atomowa tylko w obrębie procesu (`asyncio.Lock`; `Store` nie ma atomowego inkrementu).
Przy wielu replikach potrzebny jest inkrement po stronie bazy (Cosmos patch/ETag) — inaczej możliwe przekroczenie
budżetu rzędu liczby replik × rezerwacja. Limit równoległych żądań (`AI_MAX_INFLIGHT`) też jest per proces.

## /jaskolka — ścieżka publiczna (plan 05)

Spokojna, monochromatyczna ścieżka **bez logowania**, ciasteczek i analityki: wybór sytuacji → checklista
uprawnień i dokumentów → baza fundacji. Dane i frontend:

- Treść: `backend/app/data/jaskolka.json` (5 sytuacji: `martwe-urodzenie`, `poronienie`, `wczesniak`,
  `ciezka-choroba`, `smierc-dziecka`; ≥15 fundacji). Każdy punkt ma `source_url`, niepewne `verify: true`.
- API (publiczne, bez tokena): `GET /api/jaskolka/situations`, `GET /api/jaskolka/situations/{id}`,
  `GET /api/jaskolka/foundations?situation=ID`. Nieznana sytuacja → 404 po polsku.
- Frontend: trasy `/jaskolka` i `/jaskolka/:situationId` (`features/jaskolka`, `handle: { public: true }`,
  ładowane leniwie, motyw `mono`). Odhaczenia checklisty żyją tylko w `sessionStorage`.
- Link z landingu: stopka sekcji CTA wskazuje na `${VITE_APP_URL}/jaskolka`.
- Sprawdzenie linków fundacji (wymaga sieci): `python backend/scripts/check_jaskolka_urls.py`
  — wypisuje kod HTTP każdego adresu; uruchamiaj przed demo i po zmianach w danych.
- Dodanie sytuacji/fundacji = edycja samego JSON-a (testy sprawdzają źródła, HTTPS i spójność filtrów).

## Czat „Zapytaj mRodzinę” (plan 06)

Rozmowę prowadzi backend: LLM (plan 02) ↔ narzędzia ↔ odpowiedź strumieniowana przez SSE. Narzędzia model dostaje
z serwera MCP w procesie backendu (`app/mcp_server.py`, SDK `mcp`); backend jest jego klientem. Narzędzia z rejestru
`app/ai/tools.py` pojawiają się automatycznie — własne: `profil_rodziny`, `szukaj_w_przepisach`, `szukaj_w_sieci`
(`app/tools/chat_tools.py`); `swiadczenia`, `ryzyka`, `kalendarz` z innych planów wystarczy zarejestrować `@tool`.

- **API:** `POST /api/chat {session_id|null, message}` → `text/event-stream` (zdarzenia `tool`, `token`, `sources`,
  `done` z `session_id`, `error`); `GET /api/chat/sessions`, `GET|DELETE /api/chat/sessions/{id}` (tylko własne
  sesje rodzica). Wiadomość ≤ 2000 znaków (422), historia do modelu ≤ 20 wiadomości, maks. 5 wywołań narzędzi na
  turę, `ai_guard("chat")` (429 + `Retry-After`).
- **Tryb demo (bez Azure):** `DemoLLM` przez handler `app/seed/demo_chat.py` wyszukuje przepisy narzędziem MCP i wypisuje
  3 najtrafniejsze artykuły z linkami (bez interpretacji). Po ustawieniu `AZURE_OPENAI_*` działa prawdziwy model.
- **Indeks przepisów:** dane w `backend/app/data/laws/*.json` (8 aktów, ~450 artykułów, commitowane). Odświeżenie
  (wymaga sieci): `cd backend && .venv/bin/python scripts/build_laws_index.py [kp zasilkowa …]` — skrypt wyszukuje
  aktualny tekst jednolity w API Sejmu (ELI `…/eli/acts/search`), pobiera PDF, dzieli po „Art. N.”, naprawia
  rozdzielone znaki diakrytyczne i przepisuje JSON. Wyszukiwanie to własny BM25 (`app/services/laws.py`) z normalizacją
  polskich znaków i stemmingiem prefiksowym (5 znaków). Zmiana limitu artykułów dla aktu: `ACTS` w skrypcie.
- **Web search:** zmienne `WEB_SEARCH_PROVIDER` (`none`|`brave`|`serper`) i `WEB_SEARCH_API_KEY`. Wyniki są
  rankingowane (domeny urzędowe — gov.pl, BIP, zus.pl, PUP, urzędy gmin — najpierw). Bez dostawcy narzędzie zwraca
  błąd, a model odpowiada na podstawie przepisów lub kieruje do urzędu.
- **Bezpieczeństwo:** wyniki narzędzi trafiają do modelu w `<wynik_narzedzia>` jako dane (znaczniki wewnątrz wyniku są
  neutralizowane), tożsamość pochodzi z tokena (nie z argumentów modelu), `profil_rodziny` nie zawiera PESEL ani
  zarobków, a tura jest zapisywana do `chat_sessions` dopiero po zakończeniu (przerwane połączenie nic nie zostawia).
- **Frontend:** `features/chat` — trasa `/czat`, kafelek `widget.tsx` (order 5, pole pytania + przykłady → `/czat?q=…`),
  `useChatStream` czyta SSE (`fetch` + `ReadableStream`).

## Tryb jaskółki i „Za życiem” (plan 10)

Zgłoszenie straty dziecka przełącza **całą rodzinę** w spokojny, monochromatyczny tryb; oznaczenie „Za życiem” dodaje
świadczenia bez trybu. Serwis: `backend/app/services/situations.py`, API: `backend/app/routers/situations.py`.

- **API (parent):** `POST|DELETE /api/families/me/children/{id}/situation {kind}` (`poronienie` | `martwe-urodzenie` |
  `smierc-dziecka`; DELETE = cofnięcie), `POST /api/families/me/mode/exit` („Wróć do zwykłego widoku”, 204),
  `PATCH /api/families/me/children/{id}/serious-illness {value}`, `GET /api/me/mode → {mode, since, undo_until, child_id}`.
  Zwykłe `PATCH /children/{id}` **nie** zmienia już `situation*` (tylko serwis ma skutki uboczne).
- **Skutki zgłoszenia (obojga rodziców, bez powiadomień):** szkice wniosków o to dziecko → `status: "cancelled"`
  (nie wracają po cofnięciu); wysłane → `child_loss_note`; dziecko zostaje w profilu. Zgłoszenie jest idempotentne
  (pierwsze wygrywa, także przy jednoczesnym zgłoszeniu przez oboje rodziców).
- **Cofnięcie:** do `UNDO_WINDOW_DAYS` (7) dni — potem 409 po polsku; w trybie zostaje tylko ręczne wyjście. Z trybu
  nie wychodzi się automatycznie.
- **Reguły dla innych modułów** (czyste funkcje w `situations.py`): `family_mode(children)`, `event_policy(children)`
  (`skip` dla dziecka w sytuacji, `mute` dla pozostałych w trybie — dla `calendar_gen`), `loss_support_applies(tags, children)`
  (świadczenia z tagiem `loss_support`, dane w `backend/app/data/benefits_loss.json` — dla seedu i dopasowania).
- **Frontend:** `features/situations` — `useFamilyMode` (kontekst z `/api/me/mode`), `SituationMenu` (jedno kliknięcie, bez
  potwierdzeń; na karcie dziecka w `FamilyPage`), `JaskolkaHome` (lista „Dla Was”; `AppShell` podstawia ją pod `/` w
  trybie i ustawia `data-theme="mono"`), trasa `/dla-was`.
- **Scenariusz całości:** `backend/tests/test_e2e_nowak.py` (czytaj jak dokumentację).
