# mRodzina — przewodnik developera

## Szybki start Windows (bez Azure)

Wszystko działa lokalnie bez żadnej konfiguracji: dane w pamięci procesu (`MemoryStore`),
demonstracyjne dane mObywatela/ZUS.

Wymagania: Python 3.12+, Node 22+.
Jeśli PowerShell nie rozpoznaje `node`, a Node jest zainstalowany w standardowym katalogu, dodaj go do `PATH`:
`$env:Path = 'C:\Program Files\nodejs;' + $env:Path`.

Backend — pierwszy terminal PowerShell:

```powershell
Set-Location backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend — drugi terminal:

```powershell
Set-Location frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

Landing — trzeci terminal:

```powershell
Set-Location landing
npm ci
npm run dev -- --port 5174 --strictPort
```

Adresy: API `http://localhost:8000/docs`, aplikacja `http://localhost:5173`,
landing `http://localhost:5174`.

Testy frontendu uruchom w katalogu `frontend/`: `npm test -- --run`, `npm run lint`,
`npm run build`. W `landing/` uruchom `npm run lint` i `npm run build`.

### Linux/macOS

Wymień `py -3 -m venv .venv` na `python3 -m venv .venv`, a polecenia
`.\.venv\Scripts\python.exe` na `.venv/bin/python`. Polecenia npm pozostają takie same.

## Persony i konta

- **Rodzice (mObywatel i Profil Zaufany w wersji demonstracyjnej)** — ekran `/logowanie`: `persona-nowak-anna` (mama, w ciąży,
  e-ZLA kod B) i `persona-nowak-piotr` (tata). Obie opcje korzystają z tych samych przykładowych profili; rzeczywiste
  logowanie zewnętrzne wymaga osobnej integracji. Dane z „ZUS” powstają przy pierwszym logowaniu, daty względem dnia
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

## /jaskolka (ścieżka publiczna, bez logowania)

- Frontend: `http://localhost:5173/jaskolka` (motyw monochromatyczny, osobny chunk). Strona nie wysyła tokenu
  ani ciasteczek; odhaczenia checklisty żyją tylko w `sessionStorage`. Landing linkuje tu przez
  `${VITE_APP_URL}/jaskolka`.
- API: `GET /api/jaskolka/situations`, `/situations/{id}`, `/foundations?situation=ID`; treść w
  `backend/app/data/jaskolka.json` (pole `verify: true` = do potwierdzenia człowiekiem; lista rzeczy do
  sprawdzenia: `docs/superpowers/plans/NOTES-05.md`).
- Sprawdzenie, czy wszystkie adresy w danych odpowiadają (wymaga internetu):
  `cd backend && .venv/bin/python scripts/check_jaskolka_urls.py`.

## Konfiguracja (zmienne środowiskowe, `backend/.env`)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `ENV` | `dev` | `dev` = lokalnie/testy. Dowolna inna wartość (np. `prod`) włącza walidację fail-closed. |
| `SESSION_SECRET` | `dev-secret-change-me` | Klucz HMAC tokenów sesji. Poza `dev` (albo gdy ustawiony `COSMOS_ENDPOINT`) aplikacja **nie wystartuje**, jeśli jest domyślny lub krótszy niż 32 znaki. W `dev` tylko ostrzeżenie w logu. |
| `OFFICIAL_DEFAULT_PASSWORD` | `demo1234` | Hasło początkowe kont urzędników. Seed tworzy tylko brakujące konta i **nigdy nie nadpisuje** istniejących haseł. Poza `dev` (lub z Cosmos) hasło musi mieć min. 12 znaków i różnić się od `demo1234`, inaczej seedowanie urzędników jest pomijane (ostrzeżenie w logu); dodatkowo istniejące konta z hasłem `demo1234` są przy starcie **wyłączane** (`disabled: true`, logowanie → 401). |
| `SESSION_TTL_HOURS` | `12` | Ważność tokenu. |
| `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE` | puste | Puste = `MemoryStore`. Ustawione = `CosmosStore` i tryb produkcyjny. |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:5174","http://127.0.0.1:5173","http://127.0.0.1:5174"]` | Dozwolone originy (JSON), w tym aplikacja i landing lokalny. |

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

### Silnik uprawnień i kalkulator (kontrakt v1.1, `app/engine/`)

Drugi, niezależny silnik (autor: Eryk, gałąź `prompt_eryka`) liczy **kwoty i okresy**: reguły JSONLogic z
`data/reguly_uprawnien.json` oceniane trójwartościowo (brak danych → `brak_danych`, nigdy fałszywe „nie”), zmienne
wyliczane `wyl.*` (`derived.py`) i kalkulator (`calculator.py`, `Decimal`, kwoty brutto). W aplikacji o uprawnieniach
dalej decyduje `services/matching.py`; silnik działa obok.

**API (publiczne, bez logowania):** `POST /api/silnik/ocena[?data_oceny=YYYY-MM-DD]` (profil `UserProfile` z
`engine/schemas.py` → statusy, kwoty, ryzyka, wnioski, kalendarz) i `GET /api/silnik/formularz`. Wejście ma twarde
limity: zakresy dat `od ≤ do` i najwyżej 3 lata, listy do 50 pozycji (inaczej 422) — silnik rozwija okresy dzień po dniu.

**Kalkulator na landingu** (`landing/src/components/Calculator.tsx`, adapter `calcEngine.ts`) obsługuje ciążę
(osobno bieżące uprawnienia i prognozę po porodzie), dziecko urodzone oraz adopcję/rodzinę zastępczą niezawodową.
Zbiera m.in. dokładne daty ubezpieczenia i osobne podstawy składek obojga rodziców, skład rodziny i dochód, miejsce
zamieszkania, e-ZLA, dane o wcześniactwie/„Za życiem” oraz plan łączenia urlopu z pracą (także przy adopcji).
Miesięczne podstawy są przypisane do konkretnych miesięcy przed terminem porodu; miesiące przed objęciem
ubezpieczeniem są pomijane, a puste miesiące objęte ubezpieczeniem pozostają nieznane i nie są zastępowane
szacunkiem. Bieżący profil ciąży nie udaje już profilu po porodzie; prognoza po porodzie jest liczona osobno.
Silnik zwraca statusy (także „brak danych” i niespełnione warunki), kwoty, ryzyka, wymagane wnioski i terminy;
landing nie wylicza kwot samodzielnie ani nie zapisuje danych.

Miasto i gmina wskazują właściwy urząd w podsumowaniu, ale aktualny katalog lokalnych programów nie jest podłączony.
`benefits_local_sample.json` zawiera wyłącznie przykłady demonstracyjne — nie wyświetlaj ich jako prawdziwych ofert.
Domyślna konfiguracja CORS dopuszcza lokalny landing; przy własnym `CORS_ORIGINS` trzeba dodać origin, z którego
otwierasz stronę.

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
`POST /{id}/sign` (testowy podpis Profilem Zaufanym) → `POST /{id}/submit`. Zasady:

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
znacznik „DANE TESTOWE”, kolor `--ai`) renderują pola z `GET /api/applications/portals/{id}`. `AgentFrame` osadza je w
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

**Ograniczenia:** wzory wniosków do pracodawcy wymagają weryfikacji prawnej przed użyciem produkcyjnym; podpis i poczta
korzystają z trybu testowego, a portale są makietami; linki „Zobacz w kalendarzu” i „Zobacz pocztę” w ostatnim kroku kreatora (`/kalendarz`,
`/poczta`) działają dopiero po wdrożeniu planu 09.

## Umowy i ostrzeżenia o ryzyku (plan 04)

- Rodzic wgrywa umowę (`/umowy` albo opcjonalny krok `/start/umowy`): `POST /api/contracts/scan` (multipart
  `file`, PDF/PNG/JPG/TXT, maks. 5 MB, za `ai_guard("contract_scan")`) → szkic (`confirmed=false`) z listą
  `missing`. Dane trafiają do profilu dopiero po `POST /api/contracts/{id}/confirm` (scalane z wpisem
  ubezpieczenia z ZUS o tym samym płatniku i rodzaju). Maks. 5 zatwierdzonych umów na rodzica.
- Typ pliku sprawdzamy po magic bytes (musi zgadzać się z `Content-Type`); PDF z JavaScriptem/załącznikami
  jest odrzucany. Sam plik nie jest przechowywany — zapisujemy tylko nazwę, widoczną wyłącznie dla właściciela;
  partner widzi zatwierdzone dane. Tekst umowy jest przycinany do `AI_MAX_INPUT_CHARS`.
- `GET /api/risks` — ostrzeżenia obojga rodziców (`services/risk.py`: umowa terminowa kończąca się przed
  porodem, zlecenie bez dobrowolnego chorobowego, zadłużenie JDG). Narzędzie MCP: `ryzyka`.
  Ryzyka pojawiają się tylko, gdy w rodzinie jest dziecko „w drodze” z terminem porodu.

**Umowy z e-teczki pracodawcy (demo, onboarding):** każda persona ma w `seed/personas.py` (`employment_docs`) umowę
o pracę i umowę zlecenia. `GET /api/contracts/documents` — lista umów zalogowanego rodzica,
`GET /api/contracts/documents/{id}/pdf` — PDF generowany na żądanie (`services/employment_docs.py`, nic nie
przechowujemy), `POST /api/contracts/documents/{id}/import` — dodaje umowę jako zatwierdzoną (idempotentnie).
W onboardingu przycisk „Załącz umowy” wrzuca obie umowy i pokazuje poglądowy odczyt przez AI (DANE PRZYKŁADOWE — dane
pochodzą z persony, model nie jest wołany). Asystent czatu widzi umowy w `profil_rodziny` (bez wynagrodzenia) i może
cytować ich paragrafy narzędziem `tresc_umowy` — tylko umowy własne, bez paragrafu o wynagrodzeniu.

**Skan w trybie demo (bez Azure):** `DemoLLM` odczytuje umowę regexami (`app/seed/demo_handlers.py`) — działa
dla plików tekstowych/PDF z etykietami „Pracodawca:”, „Stanowisko:”, „Wynagrodzenie:” itd. (zdjęć w demo nie
odczytamy). Przykładowa umowa Anny Nowak jest w repo: `backend/app/seed/sample_umowa_anna_nowak.pdf`.
Wygenerowanie jej od nowa (wymaga `fpdf2` z `requirements-dev.txt` i czcionki TTF z polskimi znakami):

```bash
cd backend && .venv/bin/python scripts/make_sample_contract.py   # opcjonalnie --font /ścieżka/do.ttf
```

Test ręczny: zaloguj się jako Anna, załóż rodzinę, wejdź w „Umowy”, wgraj ten PDF, zatwierdź — umowa pojawi się
w „Moich danych”. Żeby zobaczyć ostrzeżenie, wgraj plik `.txt` z „UMOWA ZLECENIA”, „Zleceniodawca: …”,
„Dobrowolne ubezpieczenie chorobowe: nie” (dziecko w drodze musi być dodane w „Rodzina”).

**Node:** frontend (vite 8 / rolldown) wymaga Node **≥ 22.12** — na 22.9 `npm ci` pomija natywny binding
i testy nie startują („Cannot find native binding”).

## Panel gminy / województwa (plan 07)

Panel urzędnika: `http://localhost:5173/urzednik/logowanie` (osobna powłoka, poza nawigacją rodzica).

| Konto | Jednostka | Zasięg świadczeń |
|---|---|---|
| `urzednik.krakow@mrodzina.local` | Gmina Miejska Kraków (`unit-krakow`) | `municipal` — widzą mieszkańcy Krakowa |
| `urzednik.malopolska@mrodzina.local` | Województwo Małopolskie (`unit-malopolskie`) | `regional` — widzą wszystkie gminy województwa |

Hasło w trybie `dev`: `demo1234` (`OFFICIAL_DEFAULT_PASSWORD`). Nowe konto = wpis w `backend/app/seed/officials.py`
(+ jednostka w `seed/units.py`); samorejestracji nie ma.

- API: `/api/official/*` (tylko token urzędnika; świadczenia innej jednostki → 404). `scope` i `unit_id` ustawia
  serwer z jednostki urzędnika. Status: `draft` → „Wyodrębnij warunki” (`awaiting_approval`) → „Zatwierdź warunki”
  → `published`. Każda edycja wraca do `draft`; publikacja z niezatwierdzonymi warunkami → 409.
- AI (za `ai_guard`): `benefit_conditions` (warunki z „Dodatkowych wymogów”) i `resolution_prefill` („Wklej
  uchwałę → wypełnij”). Warunek `auto` tylko dla kluczy z `PROFILE_KEYS` (`services/conditions.py`), reszta
  to pytania tak/nie. W trybie demo działają reguły słów kluczowych (`seed/demo_conditions.py`).
- Przykładowe świadczenia lokalne (z dopiskiem „(przykład)”): `backend/app/data/benefits_local_sample.json`.
  Seed ich nie nadpisuje, jeśli urzędnik je zmienił.
- Edytor urzędnika używa wspólnego modelu `Benefit` (plan 03) rozszerzonego o `awaiting_approval`, `deadline_text`
  i `apply_url`; widoczność świadczeń po adresie: `services/benefit_service.visible_benefits`.

## Poczta, statusy wniosków, kalendarz i powiadomienia (plan 09)

- **Poczta testowa, domyślnie podłączona** (`/poczta`, ustawienia `/poczta/ustawienia` — „Gmail podłączony”).
  Skrzynka rodziny ma też 6 maili niezwiązanych (sklep, szkoła, przychodnia…), które filtr pomija.
- **Filtr** (`services/mail_filter.py`): czytamy wątek wniosku, dokładny adres odbiorcy oraz domenę tylko dla
  instytucji (`zus.pl`, `gov.pl`, domeny z katalogu, `um.krakow.pl`) — nigdy całych domen publicznych
  (`gmail.com`, `onet.pl`, `wp.pl`, `outlook.com`…). Maile sprzed wysyłki wniosku są ignorowane.
- **Klasyfikacja** (`services/mail_classify.py`, LLM `mail_classify`): `received|more_info|accepted|rejected|other`.
  Pewność ≥ 0,8 → status wniosku zmienia się sam + powiadomienie; poniżej → „Nowa wiadomość w sprawie wniosku X —
  sprawdź” bez zmiany statusu. Błąd modelu → „do sprawdzenia”. Synchronizacja jest idempotentna.
  W trybie demo klasyfikują słowa kluczowe (`seed/demo_mail.py`).
- **Odpowiedzi urzędów** (`mail/sim_inbox.py`): pracodawca → „otrzymaliśmy”, potem „zatwierdzony”; ZUS → „wezwanie
  do uzupełnienia”; gmina → „decyzja pozytywna”. Przychodzą po `MAIL_SIM_REPLY_DELAY_S` (20 s) przy kolejnym
  sprawdzeniu poczty albo od razu przyciskiem „Symuluj odpowiedzi” (`POST /api/mail/simulate-replies`).
- **Sprawdzanie w tle:** pętla w `lifespan` co `MAIL_POLL_S` s (0 = wyłączona; testy ustawiają 0 w `conftest.py`);
  tokeny z dziennego budżetu AI. Ręcznie: „Sprawdź pocztę” (`POST /api/mail/sync`, za `ai_guard`).
- **Kalendarz** (`/kalendarz`, widżet „Najbliższe terminy”, narzędzie MCP `kalendarz`): terminy świadczeń względem
  porodu/urodzenia, złożone wnioski („kto złożył”, do kogo, status), termin porodu i ostrzeżenia z ryzyk (plan 04).
  Przy wnioskach data oznacza utworzenie szkicu albo złożenie, nie termin końcowy; dopóki brak decyzji, koniec sprawy
  nie ma znanej daty. Po złożeniu wykonana czynność trafia do „Zrobione”, a status sprawy pozostaje widoczny.
  Terminy świadczeń na dziecko generują się tylko dla dzieci spełniających kryteria wieku. Wpisy mają stałe `id`
  (zmiana daty porodu nie dubluje), odkliknięcie przeżywa regenerację, terminy po czasie są oznaczone „po terminie”.
  Powiadomienia: dzwonek w nagłówku (`/api/notifications`). E-mail/SMS — tylko wzmianka
  „Wkrótce”.
- **Wysyłka wniosku uruchamia przygotowanie odpowiedzi testowej:** `ApplicationService.submit` (e-mail do pracodawcy) i
  `portal_submitted` (eZUS → adresat `wnioski@zus.pl`, Emp@tia → `swiadczenia@um.krakow.pl`) wołają
  `mail.sim_inbox.schedule_reply`. Scenariusz: Anna składa wniosek w `/wnioski` → `/poczta` → „Symuluj odpowiedzi” →
  status „Zaakceptowany”, powiadomienia, wpis w kalendarzu. Wiadomości (wysłane i odebrane) to jeden model
  `models/mail.MailMessage`; `SimMailProvider` (plan 08) zapisuje folder `sent`, `SimInbox` (plan 09) dokłada `inbox`.

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

## Wygląd i dostępność (konwencje po przeglądzie UX)

- **Kolory.** Czysty róż marki `#EF4363` (`--pink`, `--brand`) ma na bieli kontrast tylko 3,7:1 (WCAG AA wymaga 4,5:1). Tło
  pod białym tekstem (przyciski `.btn`, plakietki z liczbą, „Zapytaj”, wysyłka w czacie) bierze `--primary: #C8234A`,
  drobny tekst w kolorze marki na jasnym tle `--pink-700`. Czysty róż zostaje dla logo, wordmarku, ekranów przejściowych
  i dekoracji. Nie wpisuj kolorów w komponentach, używaj tokenów z `theme.css`.
- **Nawigacja.** Panel główny z kafelkami i przycisk „wstecz” na podstronach (bez dolnego paska zakładek).
- **Cele dotyku ≥ 44 px**: przyciski, samodzielne linki, pola formularzy i `summary`. Tekst plakietek i etykiet nie jest
  mniejszy niż 0,875rem (ok. 15 px).
- **Szerokość.** Żadna podstrona nie może się przewijać w bok: siatki używają `minmax(0, …)`, a długie wartości
  `overflow-wrap`.
- **Fonty** (Nunito, Sniglet) są hostowane lokalnie przez pakiety `@fontsource/*` (importy w `main.tsx`), bez Google Fonts:
  działają offline i nie ujawniają adresu IP użytkownika Google. Polskie znaki wymagają importu podzbioru `latin-ext`.
- **Teksty.** Bez długich myślników (—) w tekstach widocznych dla użytkownika: zdanie rozdziel kropką, przecinkiem albo
  dwukropkiem.
- **Wdrożenie (Azure Static Web Apps).** `frontend/public/staticwebapp.config.json` przekierowuje trasy aplikacji na
  `index.html` (inaczej odświeżenie `/kalendarz` albo ramka agenta `/sim/...` dają 404).
- **Terminy w podsumowaniu i kalendarzu.** „Najbliższy termin” bierze pod uwagę także kamienie milowe ciąży i porodu
  (`services/milestones.py`: zaświadczenie lekarskie dla pracodawcy, zgłoszenie urodzenia w USC), a kalendarz pokazuje też
  terminy „po porodzie” (urlop rodzicielski, 800+) liczone orientacyjnie od przewidywanego porodu.
- **Czat w trybie demo** odpowiada konkretnie (kwota, sytuacja rodziny, jak złożyć wniosek, oficjalne źródło) z katalogu
  świadczeń; narzędzie MCP `swiadczenia` przyjmuje `query` i zwraca wtedy tylko najtrafniejsze pozycje z opisem.
