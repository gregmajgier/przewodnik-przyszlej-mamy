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

## Świadczenia (plan 03)

**Katalog.** Świadczenia krajowe są w `backend/app/data/benefits_national.json` (22 pozycje), ładuje je `seed_all`
(`app/seed/benefits.py`, upsert po stałym `id`). Model: `app/models/benefit.py` (`Benefit`, `Criteria`, `Condition`,
`Deadline`). Świadczenia gminne i wojewódzkie dodaje urzędnik (plan 07) do tej samej kolekcji `benefits`;
rodzina widzi tylko te, które obejmują jej adres (`services/units.py`: gmina → tylko własna, województwo → wszystkie
gminy województwa).

**Jak dodać świadczenie krajowe** — nowy obiekt w `benefits_national.json`:

| Pole | Uwagi |
|---|---|
| `id`, `name`, `scope: "national"`, `category` | `id` unikalne i stałe (`nat-...`); `category`: `benefit` (pieniądze, wlicza się do szacunku rocznego) albo `perk` (uprawnienie/ulga). |
| `criteria` | Kryteria strukturalne sprawdzane kodem. Wiek dziecka w **pełnych ukończonych miesiącach**, obie granice włącznie: „do ukończenia 18 lat” = `child_age_max_months: 215` (w dniu 18. urodzin wiek to już 216 → nie pasuje). Brak danych o dochodzie → `maybe` + pytanie, nigdy `no`. |
| `extra_conditions` | Warunki dodatkowe: `kind: "auto"` (sprawdzane po `profile_key`) albo `"ask"` (pytanie tak/nie; odpowiedź zapisuje się w `profile.answers["benefit:<id>:<warunek>"]`, więc nie pytamy drugi raz). |
| `amount_text`, `annual_value_estimate`, `deadline` | Kwota opisowa, szacunek roczny w zł (tylko dla `benefit`) i termin (`anchor`: `birth`/`due`/`child_age`/`fixed`). |
| `form_codes` | Kody z `katalog_wnioskow_pdf.json` (lub puste). Kod z kreatorem wniosków (patrz niżej) daje przycisk „Złóż wniosek” działający od razu; pozostałe kody pokażą wyjaśnienie i link do pustego formularza. |
| `source_url` | **Obowiązkowy**, `https://`, oficjalne źródło (ZUS, gov.pl, MRPiPS, ISAP). Wątpliwe dane oznacz `"verify": true`. |

`backend/tests/test_benefits_seed.py` waliduje każdy rekord (model, `https`, unikalne `id`, istniejące `form_codes`,
co najmniej 16 pozycji) i scenariusz rodziny Nowaków — po dodaniu wpisu uruchom `pytest -q`.

**Silnik** (`services/matching.py`) to czysta, deterministyczna funkcja `match_benefit(ctx, benefit)`; **LLM nie bierze
udziału w dopasowaniu**. Wynik: `fits` (pasuje), `maybe` (spełnione kryteria, ale są nierozstrzygnięte pytania) albo
`no` (z powodem w `unmet`); każdy wynik ma ludzkie uzasadnienia w `reasons`.

**API** (rodzic): `GET /api/benefits` (opublikowane, obejmujące adres rodziny), `GET /api/benefits/{id}`,
`POST /api/benefits/{id}/answers {condition_id, answer}`, `GET /api/analysis` (kroki ekranu analizy + liczby),
`GET /api/summary` (agregat dla dashboardu + `parameters_label`). Narzędzie MCP `swiadczenia` (`app/tools/benefits.py`)
zwraca te same dopasowania asystentowi czatu.

**Frontend:** po onboardingu rodzic trafia na `/analiza` (kroki ujawniane co ~700 ms; przy `prefers-reduced-motion`
wszystko od razu), potem na `/` — dashboard (nagłówek z podsumowaniem, stawki z `GET /api/parametry` z etykietą
„Parametry ZUS 2026 – aktywne” i siatka kafelków). Kafelek dokłada każda funkcja plikiem
`features/<nazwa>/widget.tsx` (`{ order, Component }`) — dashboard ich nie zna z nazwy. Lista świadczeń: `/swiadczenia`.

## Wnioski, agent i makiety portali (plan 08)

**Kanały** (`services/applications.py::channels_for`, dane z `katalog_wnioskow_pdf.json`):

| Wniosek | Kanały |
|---|---|
| do pracodawcy (`URLOP-*`, `REZYGNACJA-MAC`) | `employer_email` (PDF generowany + e-mail) lub `pdf_download` |
| ZUS/gmina z makietą portalu (`ZAM`, `KDR`, `ZA-ZYCIEM`) | `portal_agent`; `ZAM` także `pdf_download` (AcroForm) |
| tylko elektroniczne (`800PLUS`, `AKTYWNY-RODZIC`) | wyłącznie `portal_agent` (PDF → 422) |
| ZUS z samym PDF (`ZAS-53`, `ZAS-26`, …) | `pdf_download` |

Rozgałęzienie z diagramu: pracownik → najpierw wniosek o urlop u pracodawcy, potem `ZAM`; zlecenie/JDG → od razu `ZAM`
(`prefill.recommend_flow`, zwracane w `GET /api/applications/forms`).

**Przepływ:** `POST /api/applications {form_code, child_id?, channel?}` → szkic z prefillem (`services/prefill.py`:
profil ZUS, odpowiedzi zapisane w profilu, dziecko) → `needs_input` + lista `missing`, gdy czegoś brakuje (nigdy puste pole
w PDF) → `POST /{id}/answers` (odpowiedź zapisuje się w profilu; PESEL dziecka przy dziecku) → `GET /{id}/pdf` (podgląd) →
`POST /{id}/sign` (**symulowany** Profil Zaufany) → `POST /{id}/submit`. Zasady:

- Wnioskodawcą jest rodzic, który założył wniosek; drugi rodzic widzi go na liście rodziny, ale nie edytuje (403).
  Cudzy wniosek lub dziecko cudzej rodziny → 404.
- Podpis obejmuje **odcisk danych** (kanał, adresat, wartości). Zmiana czegokolwiek po podpisie (także danych dziecka)
  unieważnia go — `submit` odpowie 409 „podpisz ponownie”.
- `submit` jest **idempotentny po `application.id`** (blokada na wniosek + status): podwójne kliknięcie = jedna wiadomość.
  Blokada jest per proces (jak limity AI); przy wielu replikach potrzebny byłby warunkowy zapis w bazie.
- Poczta: `app/mail/provider.py` — `MailProvider` (protokół) i `SimMailProvider`, który **nie wysyła prawdziwych
  e-maili**, tylko zapisuje wiadomość w `mail_messages` (folder `sent`, w bazie tylko nazwa i rozmiar załącznika).
  Prawdziwego dostawcę podpinasz, podmieniając zależność `get_mail`.
- Tryb straty: `cancel_drafts_for_child(store, child_id)` (`services/applications.py`, dostępne też z
  `routers/applications`) anuluje niewysłane wnioski dziecka; tworzenie/podpis/wysyłka dla takiego dziecka → 409.

**Agent w makiecie portalu.** `POST /api/applications/{id}/agent-plan` (za `ai_guard("agent_plan")`) zwraca kroki
`pole → wartość + uzasadnienie` i listę `blocked` (pytania o braki). Model dostaje **tylko schemat pól**
(id, etykieta, typ, „czy wartość jest znana”) — żadnych danych osobowych; wartości zawsze pochodzą z prefillu i są
walidowane typem/wyborem, więc model nie może ich zmyślić ani podmienić. Pole spoza schematu lub niepoprawna wartość
nie trafia do planu; brak wymaganej wartości → `blocked`, nigdy zgadywanie. Bez Foundry działa deterministyczny
handler demo (`app/seed/demo_agent.py`).

Frontend (`features/portal-sim`): makiety `/sim/ezus/:portalId` i `/sim/empatia/:portalId` (trasy publiczne, wyraźny
znacznik „SYMULACJA”, kolor `--ai`) renderują pola z `GET /api/applications/portals/{id}`. `AgentFrame` osadza je w
`<iframe>`, wykonuje plan krok po kroku z widocznym kursorem, zatrzymuje się na brakach (pyta rodzica) i przed wysyłką;
dopiero „Zatwierdzam i wysyłam” wysyła, a po `submitted` woła `portal-submitted`. Protokół `postMessage`
(`agentBridge.ts`): aplikacja → makieta `fill`/`submit`, makieta → aplikacja `ready`/`ack`/`edited`/`invalid`/`submitted`.
Obie strony przyjmują wiadomości **tylko z tego samego originu i od właściwego okna**, walidują ich kształt i wysyłają
z jawnym `targetOrigin`. Makieta odrzuca pola spoza schematu i wartości niezgodne z typem.

**Jak dodać wniosek z kreatorem**
1. Wniosek z PDF-em AcroForm: zbadaj pola (`pypdf.PdfReader(...).get_fields()`), dodaj mapę
   `backend/app/data/form_field_maps/<KOD>.json` (pole PDF → `source_key`) — `test_map_fields_exist_in_pdf` wykryje
   rozjazd mapy z PDF-em.
2. Wniosek przez makietę portalu: dodaj wpis w `backend/app/data/portal_schemas.json` i kod w `CODE_TO_PORTAL`
   (`services/prefill.py`).
3. Kod musi istnieć w `katalog_wnioskow_pdf.json`; kanały wynikają z powyższej tabeli.

**Ograniczenia:** wzory wniosków do pracodawcy wymagają weryfikacji prawnej przed użyciem produkcyjnym; podpis, poczta
i portale są symulacjami; linki „Zobacz w kalendarzu” i „Zobacz pocztę” w ostatnim kroku kreatora (`/kalendarz`,
`/poczta`) działają dopiero po wdrożeniu planu 09.
