# mRodzina — wspólne konwencje dla wszystkich planów

Spec: `docs/superpowers/specs/2026-11-21-mrodzina-design.md` (czytaj razem z planem). Język UI i danych: **polski**. Identyfikatory w kodzie: **angielski** (wyjątek: istniejący router `wnioski` i pliki danych).

## Kolejność i zależności planów

| # | Plan | Zależy od |
|---|------|-----------|
| 01 | foundation | — |
| 02 | ai-gateway | 01 |
| 03 | benefits | 01, 02 |
| 04 | contracts | 01, 02 |
| 05 | jaskolka-public | 01 |
| 06 | chat | 01, 02 |
| 07 | municipal-panel | 03 |
| 08 | applications | 01, 02, 03 |
| 09 | mail-calendar | 08 |
| 10 | jaskolka-mode-and-polish | 03, 08, 09, 05 |

Plany tej samej fali mają **rozłączne pliki** (każdy dodaje własne moduły; wspólne punkty rozszerzeń są auto-wykrywane, patrz niżej). Nie edytuj plików należących do innego planu — jeśli musisz, zrób minimalną zmianę i opisz w commicie.

## Git
- Pracuj na przydzielonej gałęzi/worktree. **Nie dotykaj `main` ani `dev`, nie rób `git push`.**
- Commit po każdym tasku, wiadomość `feat|fix|test|docs|chore: ...` + pusta linia + `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Nigdy nie commituj `.env`, `.venv`, `node_modules`, kluczy.

## Komendy weryfikacji
- Backend: `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest -q`
- Frontend: `cd frontend && npm ci && npm test -- --run && npm run lint && npm run build`
- Kod musi działać na Pythonie 3.12 (obraz Dockera) i Node 22.

## Backend — układ i punkty rozszerzeń (tworzy plan 01)
```
backend/app/
  main.py        create_app(store: Store | None = None) -> FastAPI ; auto-dołącza KAŻDY moduł z app/routers/ eksponujący `router`
  config.py      Settings (pydantic-settings), env
  storage.py     Store (Protocol), MemoryStore, CosmosStore, get_store()
  security.py    tokeny, Principal, current_principal / require_parent / require_official
  models/        modele pydantic (jeden plik na obszar)
  routers/       jeden plik na funkcję; eksponuje `router = APIRouter(prefix="/api/...")`
  services/      logika domenowa (czysta, testowalna bez HTTP)
  seed/          dane startowe + seed_all(store) (idempotentne: stałe id, put = upsert)
  ai/            llm.py, limits.py, tools.py (plan 02)
  tools/         moduły narzędzi MCP, auto-importowane (plan 02)
backend/tests/   pytest; fixtury w conftest.py: `store` (MemoryStore + seed), `client` (TestClient), `login(client, persona_id) -> headers`
```
**Store** (async): `get(coll, id) -> dict|None`, `put(coll, doc) -> dict` (doc["id"] wymagane, upsert), `delete(coll, id)`, `find(coll, **eq) -> list[dict]` (równość na polach top-level). Kolekcje: `users, units, families, join_requests, profiles, children, contracts, benefits, benefit_answers, applications, calendar_events, notifications, mail_messages, chat_sessions, ai_usage`. Dokumenty = `model.model_dump(mode="json")`. Bez Cosmos (`COSMOS_ENDPOINT` puste) działa `MemoryStore` — **cała aplikacja i testy mają działać bez Azure**.

**Auth**: `Authorization: Bearer <token>` (HMAC podpisany `SESSION_SECRET`). `Principal(user_id, role, family_id|None, unit_id|None)`. Rodzic: `require_parent`; urzędnik: `require_official`. Wszystkie `/api/*` poza `/api/auth/*`, `/api/jaskolka/*`, `/health` wymagają tokena.

**AI**: zawsze przez `app/ai` (plan 02): `get_llm()`, `ai_guard(feature)`. Bez konfiguracji Foundry działa `DemoLLM` (kanoniczne odpowiedzi rejestrowane per feature przez `register_demo_handler(feature, fn)`), więc demo działa offline. Testy używają `FakeLLM` (skrypt odpowiedzi).

**Narzędzia MCP**: moduł `app/tools/<nazwa>.py` rejestruje narzędzia dekoratorem `@tool(...)` (plan 02) — nie edytuj żadnego wspólnego pliku.

## Frontend — układ i punkty rozszerzeń (tworzy plan 01)
```
frontend/src/
  main.tsx, App.tsx      router (react-router-dom) składany z features/*/routes.tsx
  theme.css              tokeny: --bg #f8fbef, --fg #191919, --primary #ef4363, fonty Nunito/Sniglet; [data-theme="mono"] = tryb monochromatyczny
  lib/api.ts             api<T>(path, init?) -> Promise<T> (dokleja Bearer, rzuca ApiError{status, detail})
  lib/session.tsx        SessionProvider, useSession() -> { user, family, token, login, logout, refresh }
  components/            wspólne (AppShell, Button, Card, ...)
  features/<nazwa>/
    routes.tsx           export default RouteObject[]            (auto: import.meta.glob)
    nav.ts               export default { label, path, order, area: "parent"|"official" }   (opcjonalny)
    widget.tsx           export default { order: number, Component }   (opcjonalny; kafelek dashboardu)
```
Testy: vitest + @testing-library/react (`*.test.tsx` obok kodu). Teksty UI po polsku. Dostępność: etykiety, kontrast, `prefers-reduced-motion`.

## Zasady wspólne
- TDD: test → czerwony → minimalna implementacja → zielony → commit.
- Żadnych sekretów w repo; konfiguracja przez env (`backend/.env.example` — plan 01 tworzy, kolejne plany dopisują swoje zmienne).
- Polskie komunikaty błędów dla użytkownika; `detail` w API po polsku.
- Dane wrażliwe (PESEL, zarobki, skany umów, treść maili) nie trafiają do logów.
- Wartości prawne/kwoty z oficjalnych źródeł, z linkiem `source_url`; niepewne oznacz `"verify": true` w danych.

## Branding (obowiązkowe dla każdego frontendu — wzór: `landing/`)
Zanim zbudujesz UI, obejrzyj `landing/src/App.tsx`, `landing/src/App.css`, `landing/src/index.css`, `landing/src/components/Logo.tsx`. Aplikacja ma wyglądać jak ta sama marka.
- **Kolory**: tło `#f8fbef`, tekst `#191919`, akcent marki `#ef4363` (w interfejsie na przyciskach i linkach używaj ciemniejszego `--primary` ze względu na kontrast, patrz `docs/dev.md`); duże pasy/nagłówki w pełnym kolorze akcentu z tekstem w kolorze tła (`#f8fbef`, nie czysta biel); ciemne („`#191919`”) panele z jasnym tekstem jako kontrast. Zawsze przez tokeny z `frontend/src/theme.css` (nie wpisuj hexów w komponentach).
- **Typografia**: Nunito (400/600/800) do całej treści; Sniglet **tylko** dla słowa „Rodzina” we wordmarku (logo-wstążka „m” + „Rodzina”). Nagłówki Nunito 800.
- **Kształty**: przyciski-pigułki (`border-radius: 999px`), karty `border-radius: 1.5rem` z cieniem `0 6px 24px rgb(25 25 25 / 0.08)`, mniejsze kafelki `1rem`; okrągłe ikonowe przyciski z cieniem `0 4px 12px rgb(25 25 25 / 0.2)`. Duże odstępy, dużo powietrza.
- **Logo**: używaj komponentu `Logo`/wordmarku z `frontend/src/components` (animacja rysowania wstążki, wyłączona przy `prefers-reduced-motion`); nagłówek aplikacji: logo + „Rodzina” po lewej, nawigacja po prawej, na tle akcentu z tekstem `#f8fbef`.
- **Ton tekstów**: ciepły, bezpośredni, „ty” (np. „Mamo! Tato!”, „Pozwól, że mRodzina pomoże.”), krótkie zdania, bez urzędniczego żargonu; wyjaśniaj „dlaczego”. Wyjątek: `/jaskolka` i tryb jaskółki — spokojny, rzeczowy, bez wykrzykników i bez kolorów akcentu (`data-theme="mono"`), ale ta sama typografia i kształty.
- **Dekoracje**: wstążki/ikony jak na landingu tylko tam, gdzie nie przeszkadzają w pracy (np. ekran analizy, puste stany, nagłówek dashboardu); nie na formularzach i listach. Ruch minimalny, respektuj `prefers-reduced-motion`.
- **Elementy AI i demonstracyjne** (makiety portali, etykieta „DANE TESTOWE”, plan agenta) mają osobny kolor `--ai` i wyraźną etykietę.
- **Dostępność**: kontrast AA (biały/`#f8fbef` tekst na `#ef4363` tylko dla dużego/pogrubionego tekstu; drobny tekst na akcencie → `#191919` lub użyj ciemniejszego odcienia), widoczny fokus, cele dotykowe ≥ 44 px, układ od 360 px.
