# mRodzina — „Zasiłkowy Przewodnik Przyszłego Rodzica”

Jedno miejsce dla rodzica w Polsce, który spodziewa się dziecka: **zna rodzinę** (dane z ZUS/mObywatela, umowy),
**mówi, co jej przysługuje i dlaczego**, **wypełnia wnioski** i **pilnuje terminów**. Osobno, bez logowania, działa
spokojna ścieżka `/jaskolka` dla rodziców po stracie lub w ciężkiej chorobie dziecka.

Pełna specyfikacja: [`docs/superpowers/specs/2026-11-21-mrodzina-design.md`](docs/superpowers/specs/2026-11-21-mrodzina-design.md) ·
plany wdrożenia: [`docs/superpowers/plans/`](docs/superpowers/plans/) · przewodnik developera: [`docs/dev.md`](docs/dev.md).

## Struktura repozytorium

| Katalog | Zawartość |
|---|---|
| `backend/` | FastAPI (Python 3.12): auth, rodzina, profil, świadczenia i silnik uprawnień, umowy i ryzyka, wnioski z agentem portalu, poczta testowa, kalendarz, powiadomienia, panel urzędnika, brama AI, czat + serwer MCP, `/api/jaskolka`, tryb jaskółki. Routery z `app/routers/` dołączają się same. |
| `frontend/` | Aplikacja rodzica i osobny panel urzędnika (React + Vite + TypeScript). Funkcje w `src/features/<nazwa>/` rejestrują się same (`routes.tsx`, `nav.ts`, `widget.tsx`). |
| `landing/` | Strona wizerunkowa z kalkulatorem świadczeń, linkiem do aplikacji i do `/jaskolka`. |
| `brand/` | Logo i materiały marki. |
| `docs/` | Specyfikacja, plany, notatki decyzji (`NOTES-*.md`), podział pracy (`docs/assignments/`). |

## Uruchomienie na Windowsie — krok po kroku

Nie potrzebujesz Azure ani żadnych kluczy. Lokalnie aplikacja używa przykładowych profili logowania, testowych danych
ZUS, testowej poczty i odpowiedzi AI w trybie demo. Dane trzyma w pamięci, więc po restarcie backendu zaczynasz od zera.

Potrzebujesz:

- **Git**,
- **Pythona 3.12** (na tej wersji działają CI i obraz Dockera),
- **Node.js 22.12 lub nowszego**. Na starszym Node 22.x `npm ci` pomija natywny moduł i testy kończą się błędem
  „Cannot find native binding”.

Wersje sprawdzisz poleceniami `py -3.12 --version` i `node --version`.

### 1. Pobierz projekt

Bieżąca praca trafia na gałąź `dev`, a `main` to wersja wdrożona. Jeśli nie masz jeszcze repozytorium:

```powershell
git clone https://github.com/gregmajgier/przewodnik-przyszlej-mamy.git
Set-Location przewodnik-przyszlej-mamy
git switch dev
```

Otwórz folder projektu w VS Code. Z menu wybierz **Terminal → New Terminal**. Polecenia poniżej zakładają,
że terminal otwiera się w głównym folderze projektu (tam, gdzie jest ten README).

### 2. Przygotuj projekt — tylko za pierwszym razem

W pierwszym terminalu wklej:

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Wybierz **Terminal → New Terminal** jeszcze dwa razy. W drugim terminalu wklej:

```powershell
Set-Location frontend
npm ci
```

W trzecim terminalu wklej:

```powershell
Set-Location landing
npm ci
```

Poczekaj, aż instalacje się zakończą. Nie zamykaj terminali z błędem.

Jeśli PowerShell mówi, że `npm` albo `node` nie jest rozpoznawane, a Node.js jest zainstalowany w standardowym
katalogu, w każdym terminalu frontendu wklej najpierw:

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
```

### 3. Uruchom aplikację

W pierwszym terminalu (backend) wklej:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

W drugim terminalu (frontend) wklej:

```powershell
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

W trzecim terminalu (landing, opcjonalnie) wklej:

```powershell
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

**Zostaw te terminale otwarte.** Otwórz w przeglądarce:

- Aplikacja: <http://localhost:5173>
- Panel urzędnika: <http://localhost:5173/urzednik/logowanie>
- Ścieżka `/jaskolka` (bez logowania): <http://localhost:5173/jaskolka>
- Strona wizerunkowa z kalkulatorem: <http://localhost:5174>
- Dokumentacja API: <http://localhost:8000/docs>

Aby wyłączyć serwer, kliknij jego terminal i naciśnij **Ctrl+C**. Jeśli zobaczysz błąd „port already in use”,
serwer już działa — nie uruchamiaj drugiej kopii.

### 4. Po pobraniu nowych zmian

Nie musisz za każdym razem instalować wszystkiego od nowa. Pobierz zmiany:

```powershell
git switch dev
git pull origin dev
```

Potem sprawdź, czy zmieniły się pliki z zależnościami. `ORIG_HEAD` to stan sprzed `git pull`:

```powershell
git diff --stat ORIG_HEAD HEAD -- backend/requirements.txt backend/requirements-dev.txt frontend/package-lock.json landing/package-lock.json
```

- Pusty wynik: nic nie instalujesz, uruchamiasz jak w kroku 3.
- Na liście jest plik z `backend/`: w folderze `backend` uruchom `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
- Na liście jest plik z `frontend/` albo `landing/`: w tym folderze uruchom `npm ci`.

Jeśli przy starcie zobaczysz `ModuleNotFoundError` (backend) albo `Cannot find module` (frontend), brakuje paczki:
doinstaluj zależności tylko w tej części, która zgłosiła błąd.

### Testy (opcjonalnie)

- Backend: w terminalu z głównego folderu projektu uruchom `.\backend\.venv\Scripts\python.exe -m pytest -q`.
  Jeden plik: `.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_matching.py -q`.
- Frontend: w folderze `frontend` uruchom `npm test -- --run`, potem `npm run lint` i `npm run build`.
- Landing: w folderze `landing` uruchom `npm run lint` i `npm run build`.

Te same kroki wykonuje CI przy każdym pull requeście (dodatkowo buduje obraz Dockera backendu).

### Linux/macOS

W backendzie utwórz środowisko poleceniem `python3.12 -m venv .venv`, a polecenia
`.\.venv\Scripts\python.exe` zamień na `.venv/bin/python`. Polecenia `npm` i `git` pozostają takie same.

## Persony i konta

| Rola | Logowanie | Opis |
|---|---|---|
| Mama | persona `persona-nowak-anna` (ekran `/logowanie`) | Anna Nowak, 31 lat, Kraków, w ciąży z trzecim dzieckiem; umowa o pracę, e-ZLA kod B. |
| Tata | persona `persona-nowak-piotr` | Piotr Nowak, 34 lata, Kraków. Dołącza do rodziny kodem od Anny. |
| Urzędnik gminy | `urzednik.krakow@mrodzina.local` (ekran `/urzednik/logowanie`) | Gmina Kraków. Hasło w trybie `dev`: `demo1234`. |
| Urzędnik województwa | `urzednik.malopolska@mrodzina.local` | Województwo małopolskie. Hasło j.w. |

Poza trybem `dev` aplikacja wymaga własnego `SESSION_SECRET` (≥ 32 znaki) i hasła urzędników (≥ 12 znaków) — patrz niżej.

## Pierwszy spacer po aplikacji

Krótki scenariusz, który pokazuje większość funkcji:

1. Na `/logowanie` wybierz Annę. Załóż rodzinę (`/start`), opcjonalnie załącz umowy z e-teczki pracodawcy.
2. Ekran `/analiza` pokazuje, co aplikacja wie o rodzinie, a panel `/` — podsumowanie i kafelki.
3. `/swiadczenia` — co przysługuje, z uzasadnieniem; przy części świadczeń aplikacja zada pytanie tak/nie.
4. `/wnioski` → nowy wniosek: prefill danych, uzupełnienie braków, testowy podpis i wysyłka (e-mailem do pracodawcy,
   jako PDF albo przez agenta w makiecie portalu eZUS / Emp@tia).
5. Po ok. 20 sekundach kliknij na liście wniosków „Sprawdź pocztę teraz” (albo poczekaj, aż poczta sprawdzi się sama
   w tle): testowe odpowiedzi urzędów zmieniają status wniosku i dodają powiadomienie (dzwonek w nagłówku).
6. `/kalendarz` — terminy świadczeń, złożone wnioski i ostrzeżenia; `/czat` — pytania z cytatami przepisów.
7. Zaloguj się jako urzędnik Krakowa i dodaj lokalne świadczenie: po publikacji Anna zobaczy je na swojej liście.

Pełny scenariusz, łącznie z trybem jaskółki, opisuje test `backend/tests/test_e2e_nowak.py`.

## Mapa ekranów

| Adres | Co tam jest |
|---|---|
| `/logowanie`, `/start`, `/dolacz` | Logowanie personą, założenie rodziny, dołączenie drugiego rodzica kodem. |
| `/`, `/analiza` | Panel z podsumowaniem i kafelkami; ekran analizy po onboardingu. |
| `/swiadczenia` | Świadczenia krajowe i lokalne: pasuje, może pasować (z pytaniem) albo nie pasuje — zawsze z powodami. |
| `/wnioski`, `/wnioski/nowy`, `/wnioski/:id` | Lista wniosków rodziny, kreator, statusy i poczta w sprawie wniosku. |
| `/sprawy/:who` | Oś spraw całej rodziny, rodzica albo dziecka. |
| `/kalendarz` | Terminy, złożone wnioski, ostrzeżenia z ryzyk. |
| `/umowy`, `/start/umowy` | Skan i zatwierdzanie umów, ostrzeżenia o ryzyku. |
| `/czat` | „Zapytaj mRodzinę” — asystent z przepisami i danymi rodziny. |
| `/rodzina`, `/dane` | Członkowie rodziny i dzieci; „Moje dane”. |
| `/dla-was` | Widok rodziny w trybie jaskółki. |
| `/jaskolka`, `/jaskolka/:situationId` | Publiczna ścieżka po stracie lub w chorobie dziecka (bez logowania). |
| `/urzednik/logowanie`, `/urzednik` | Panel gminy / województwa: świadczenia lokalne. |
| `/sim/ezus/...`, `/sim/empatia/...` | Makiety portali, w których działa agent (oznaczone jako testowe). |

## Zmienne środowiskowe

Wszystkie opcjonalne lokalnie — bez pliku `.env` aplikacja działa w trybie offline. Pełna lista z opisami:
[`backend/.env.example`](backend/.env.example), [`frontend/.env.example`](frontend/.env.example) i [`docs/dev.md`](docs/dev.md).
Własne wartości wpisz w `backend/.env` (nie commituj go).

| Zmienna | Znaczenie |
|---|---|
| `ENV` | `dev` (domyślnie) lub inna wartość = produkcja z walidacją fail-closed. |
| `SESSION_SECRET`, `OFFICIAL_DEFAULT_PASSWORD` | Sekret tokenów i hasło kont urzędników (wymagane poza `dev`). |
| `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE` | Puste = `MemoryStore`; ustawione = Cosmos DB. |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Puste = tryb demo AI; ustawione = Azure AI Foundry. |
| `AI_USER_RPM`, `AI_USER_DAILY`, `AI_IP_RPM`, `AI_IP_DAILY`, `AI_DAILY_TOKENS`, `TRUST_PROXY_HOPS` … | Limity zapytań AI i dzienny budżet tokenów. |
| `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY` | Wyszukiwarka czatu: `none` \| `brave` \| `serper`. |
| `MAIL_SIM_REPLY_DELAY_S`, `MAIL_POLL_S` | Opóźnienie testowych odpowiedzi urzędów i cykl sprawdzania poczty w tle (`0` = wyłączony). |
| `UNDO_WINDOW_DAYS` | Ile dni można cofnąć zgłoszenie w trybie jaskółki (domyślnie 7). |
| `VITE_API_URL`, `VITE_APP_URL` | Adres API dla frontendu (domyślnie `http://localhost:8000`); adres aplikacji dla linków z landingu. |
| `CORS_ORIGINS` | Dozwolone adresy frontendów; lokalnie domyślnie aplikacja i landing. |

## Co jest rzeczywiste, a co demonstracyjne

| Obszar | Stan |
|---|---|
| Logowanie mObywatelem, dane ZUS (PESEL, ubezpieczenia, e-ZLA, dzieci) | **Dane demonstracyjne** — przykładowe persony, daty względem dnia uruchomienia. |
| Dopasowanie świadczeń | **Prawdziwa logika** — deterministyczny kod, nie AI; katalog z oficjalnych źródeł (`source_url`), punkty niepewne mają `verify: true`. |
| Kalkulator i silnik uprawnień (`/api/silnik`) | **Prawdziwe reguły** liczące kwoty i okresy; świadczenia lokalne w kalkulatorze to wyłącznie przykłady. |
| Przepisy w czacie | **Prawdziwe** — 8 aktów z oficjalnego API Sejmu (ELI), podział na artykuły, linki do ISAP. Nie zastępują porady prawnej. |
| Asystent AI (czat, skan umów, agent portalu, klasyfikacja poczty) | **Prawdziwy** po podłączeniu Azure AI Foundry; bez konfiguracji tryb demo z deterministycznymi odpowiedziami. |
| Wyszukiwanie w sieci | Prawdziwe po ustawieniu dostawcy (`brave`/`serper`); domyślnie wyłączone. |
| `/jaskolka` (sytuacje, checklisty, fundacje) | **Prawdziwa** treść z oficjalnych źródeł; punkty niepewne mają `verify: true`. Linki fundacji sprawdza `backend/scripts/check_jaskolka_urls.py`. |
| Tryb jaskółki w koncie, flaga „Za życiem” | **Prawdziwe** (logika, API, interfejs). |
| Portale eZUS / Emp@tia, podpis Profilem Zaufanym, poczta i odpowiedzi urzędów | **Wersje demonstracyjne** (makiety, `SimMailProvider`, testowa skrzynka) — oznaczone jako testowe, nic nie jest naprawdę wysyłane. |

## Zakres: prototyp [P] i wizja [W]

Oznaczenia ze specyfikacji: **[P]** buduje się w prototypie, **[W]** to wizja produktu (opisana, niebudowana).
Kolumna „Stan” pokazuje, co jest gotowe na gałęzi `dev`.

| Funkcja | Zakres | Plan | Stan |
|---|---|---|---|
| Konto rodzica, rodzina, dołączanie drugiego rodzica, „Moje dane” | [P] | 01 | gotowe |
| Brama AI: limity, budżet tokenów, rejestr narzędzi MCP | [P] | 02 | gotowe |
| Katalog i dopasowanie świadczeń, analiza, dashboard | [P] | 03 | gotowe |
| Skan umów o pracę, umowy z e-teczki, ryzyka | [P] | 04 | gotowe |
| `/jaskolka` — ścieżka publiczna | [P] | 05 | gotowe |
| Czat „Zapytaj mRodzinę” (przepisy, dane rodziny, sieć; źródła w odpowiedzi) | [P] | 06 | gotowe |
| Panel jednostki samorządu | [P] | 07 | gotowe |
| Wnioski, agent w makiecie portalu | [P] | 08 | gotowe |
| Poczta testowa, kalendarz, powiadomienia w aplikacji | [P] | 09 | gotowe |
| Tryb jaskółki w koncie, „Za życiem”, test całości | [P] | 10 | gotowe |
| Kalkulator świadczeń (publiczny landing + API) | [P] | silnik `backend/app/engine/` | gotowe |
| Powiadomienia e-mail i SMS | [W] | — | tylko wzmianka w UI |
| Prawdziwe Gmail/Outlook (OAuth), prawdziwy Profil Zaufany | [W] | — | — |
| Agent na prawdziwym Playwright w kontenerze, model on-premise | [W] | — | — |
| Panel admina ZUS, strona `/demo` | poza zakresem | — | świadoma decyzja zespołu |

## Praca z repozytorium

- Pracujemy na gałęzi `dev` albo na gałęzi funkcji, którą łączymy do `dev`. Pull request do `main` jest dozwolony
  **tylko z `dev`**.
- Push do `main` wdraża aplikację: backend do Azure Container Apps, frontend i landing do Azure Static Web Apps.
- Commity: `feat|fix|test|docs|chore: ...`. Nigdy nie commitujemy `.env`, `.venv` ani kluczy.
- Nową funkcję dodajesz nowym plikiem (router w `backend/app/routers/`, narzędzie MCP w `backend/app/tools/`,
  folder w `frontend/src/features/`) — bez edycji wspólnej konfiguracji. Szczegóły: [`docs/dev.md`](docs/dev.md).

## Zasady produktu, których pilnujemy

- Po stracie dziecka aplikacja **nie** przypomina o 800+, PESEL-u i nie gratuluje — test treści w `features/situations`.
- O uprawnieniach decyduje kod, nie AI. Brak danych o dochodzie daje „może” i pytanie, nigdy „nie”.
- Czat zawsze cytuje artykuł i link; bez podstawy mówi „nie wiem” i wskazuje, gdzie zapytać. Nie składa wniosków.
- Dane wrażliwe (PESEL, zarobki, skany umów, treść maili) nie trafiają do logów ani do modelu; AI tylko przez `app/ai` z limitami.
- Kwoty i przepisy pochodzą z oficjalnych źródeł z linkiem `https`; wątpliwe wpisy mają `verify: true`.
- Język interfejsu: polski; identyfikatory w kodzie: angielski.
