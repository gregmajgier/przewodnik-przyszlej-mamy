# mRodzina — „Zasiłkowy Przewodnik Przyszłego Rodzica”

Jedno miejsce dla rodzica w Polsce, który spodziewa się dziecka: **zna rodzinę** (dane z ZUS/mObywatela, umowy),
**mówi, co jej przysługuje i dlaczego**, **wypełnia wnioski** i **pilnuje terminów**. Osobno, bez logowania, działa
spokojna ścieżka `/jaskolka` dla rodziców po stracie lub w ciężkiej chorobie dziecka.

Pełna specyfikacja: [`docs/superpowers/specs/2026-11-21-mrodzina-design.md`](docs/superpowers/specs/2026-11-21-mrodzina-design.md) ·
plany wdrożenia: [`docs/superpowers/plans/`](docs/superpowers/plans/) · przewodnik developera: [`docs/dev.md`](docs/dev.md).

## Struktura repozytorium

| Katalog | Zawartość |
|---|---|
| `backend/` | FastAPI (Python 3.12): auth, rodzina, profil, brama AI, czat + serwer MCP, `/api/jaskolka`, tryb jaskółki. Routery z `app/routers/` dołączają się same. |
| `frontend/` | Aplikacja rodzica (React + Vite + TypeScript). Funkcje w `src/features/<nazwa>/` rejestrują się same (`routes.tsx`, `nav.ts`, `widget.tsx`). |
| `landing/` | Strona wizerunkowa z linkiem do aplikacji i do `/jaskolka`. |
| `docs/` | Specyfikacja, plany, notatki decyzji (`NOTES-*.md`), podział pracy (`docs/assignments/`). |

## Jak uruchomić (bez Azure)

Wszystko działa lokalnie bez konfiguracji: dane w pamięci procesu, asystent AI w trybie demo, symulowany mObywatel/ZUS.

```bash
# backend → http://localhost:8000/docs
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q && .venv/bin/uvicorn app.main:app --reload

# aplikacja → http://localhost:5173   (Node 22+)
cd frontend && npm ci && npm run dev

# strona wizerunkowa
cd landing && npm ci && npm run dev
```

Weryfikacja: `cd backend && .venv/bin/pytest -q` oraz `cd frontend && npm test -- --run && npm run lint && npm run build`
(to samo w `landing/`: `npm run lint && npm run build`).

## Persony i konta

| Rola | Logowanie | Opis |
|---|---|---|
| Mama | persona `persona-nowak-anna` (ekran `/logowanie`) | Anna Nowak, 31 lat, Kraków, w ciąży z trzecim dzieckiem; umowa o pracę, e-ZLA kod B. |
| Tata | persona `persona-nowak-piotr` | Piotr Nowak, 34 lata, Kraków. Dołącza do rodziny kodem od Anny (ona akceptuje prośbę). |
| Urzędnik gminy | `urzednik.krakow@mrodzina.local` | Gmina Kraków. Hasło w trybie `dev`: `demo1234`. |
| Urzędnik województwa | `urzednik.malopolska@mrodzina.local` | Województwo małopolskie. Hasło j.w. |

Poza trybem `dev` aplikacja wymaga własnego `SESSION_SECRET` (≥ 32 znaki) i hasła urzędników (≥ 12 znaków) — patrz niżej.

## Zmienne środowiskowe

Wszystkie opcjonalne lokalnie; pełna lista z opisami: [`backend/.env.example`](backend/.env.example) i [`docs/dev.md`](docs/dev.md).

| Zmienna | Znaczenie |
|---|---|
| `ENV` | `dev` (domyślnie) lub inna wartość = produkcja z walidacją fail-closed. |
| `SESSION_SECRET`, `OFFICIAL_DEFAULT_PASSWORD` | Sekret tokenów i hasło kont urzędników (wymagane poza `dev`). |
| `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE` | Puste = `MemoryStore`; ustawione = Cosmos DB. |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Puste = tryb demo AI; ustawione = Azure AI Foundry. |
| `AI_USER_RPM`, `AI_USER_DAILY`, `AI_IP_RPM`, `AI_IP_DAILY`, `AI_DAILY_TOKENS`, `TRUST_PROXY_HOPS` … | Limity zapytań AI i dzienny budżet tokenów. |
| `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY` | Wyszukiwarka czatu: `none` \| `brave` \| `serper`. |
| `UNDO_WINDOW_DAYS` | Ile dni można cofnąć zgłoszenie w trybie jaskółki (domyślnie 7). |
| `VITE_API_URL`, `VITE_APP_URL` | Adres API dla frontendu; adres aplikacji dla linków z landingu. |

## Co jest prawdziwe, a co symulowane

| Obszar | Stan |
|---|---|
| Logowanie mObywatelem, dane ZUS (PESEL, ubezpieczenia, e-ZLA, dzieci) | **Symulowane** — persony z wymyślonymi danymi, daty względem dnia uruchomienia. |
| Przepisy w czacie | **Prawdziwe** — 8 aktów z oficjalnego API Sejmu (ELI), podział na artykuły, linki do ISAP. Nie zastępują porady prawnej. |
| Asystent AI | **Prawdziwy** po podłączeniu Azure AI Foundry; bez konfiguracji tryb demo (wskazuje artykuły bez interpretacji). |
| Wyszukiwanie w sieci | Prawdziwe po ustawieniu dostawcy (`brave`/`serper`); domyślnie wyłączone. |
| `/jaskolka` (sytuacje, checklisty, fundacje) | **Prawdziwa** treść z oficjalnych źródeł; punkty niepewne mają `verify: true`. Linki fundacji sprawdza `backend/scripts/check_jaskolka_urls.py`. |
| Tryb jaskółki w koncie, flaga „Za życiem” | **Prawdziwe** (logika, API, interfejs). |
| Portale eZUS / Emp@tia, podpis Profilem Zaufanym, poczta | **Symulowane** (makiety, `SimMailProvider`) — zawsze z oznaczeniem „SYMULACJA”. |

## Zakres: prototyp [P] i wizja [W]

Oznaczenia ze specyfikacji: **[P]** buduje się w prototypie, **[W]** to wizja produktu (opisana, niebudowana).
Kolumna „Stan” pokazuje, co jest gotowe **w tej gałęzi**; reszta [P] powstaje w pozostałych planach.

| Funkcja | Zakres | Plan | Stan |
|---|---|---|---|
| Konto rodzica, rodzina, dołączanie drugiego rodzica, „Moje dane” | [P] | 01 | gotowe |
| Brama AI: limity, budżet tokenów, rejestr narzędzi MCP | [P] | 02 | gotowe |
| Katalog i dopasowanie świadczeń, analiza, dashboard | [P] | 03 | w toku (inny autor) |
| Skan umów o pracę, ryzyka | [P] | 04 | w toku (inny autor) |
| `/jaskolka` — ścieżka publiczna | [P] | 05 | gotowe |
| Czat „Zapytaj mRodzinę” (przepisy, dane rodziny, sieć; źródła w odpowiedzi) | [P] | 06 | gotowe |
| Panel jednostki samorządu | [P] | 07 | w toku (inny autor) |
| Wnioski, agent w makiecie portalu | [P] | 08 | w toku (inny autor) |
| Poczta symulowana, kalendarz, powiadomienia w aplikacji | [P] | 09 | w toku (inny autor) |
| Tryb jaskółki w koncie, „Za życiem”, test całości | [P] | 10 | gotowe w części niezależnej od planów 03/08/09 (patrz `docs/superpowers/plans/NOTES-10.md`) |
| Kalkulator urlopu | zaparkowany | — | osobny autor |
| Powiadomienia e-mail i SMS | [W] | — | tylko wzmianka w UI |
| Prawdziwe Gmail/Outlook (OAuth), prawdziwy Profil Zaufany | [W] | — | — |
| Agent na prawdziwym Playwright w kontenerze, model on-premise | [W] | — | — |
| Panel admina ZUS, strona `/demo` | poza zakresem | — | świadoma decyzja zespołu |

## Zasady produktu, których pilnujemy

- Po stracie dziecka aplikacja **nie** przypomina o 800+, PESEL-u i nie gratuluje — test treści w `features/situations`.
- Czat zawsze cytuje artykuł i link; bez podstawy mówi „nie wiem” i wskazuje, gdzie zapytać. Nie składa wniosków.
- Dane wrażliwe (PESEL, zarobki, treść maili) nie trafiają do logów; AI tylko przez `app/ai` z limitami.
- Język interfejsu: polski; identyfikatory w kodzie: angielski.
