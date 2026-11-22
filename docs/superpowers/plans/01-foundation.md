# Fundament — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Szkielet backendu i frontendu: storage, auth (persona mObywatel + urzędnik), rodzina z kodem dołączania, dzieci, profil „Moje dane” z testowymi danymi ZUS dla Nowaków, powłoka aplikacji z motywem.

**Architecture:** FastAPI z auto-wykrywanymi routerami i `Store` (Memory/Cosmos); React + react-router z auto-wykrywanymi `features/*`. Wszystko działa bez Azure.

**Tech Stack:** FastAPI, pydantic v2, pytest(+asyncio, httpx), azure-cosmos; React 19, react-router-dom, vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-21-mrodzina-design.md` §3, §4, §5.1, §5.3, §5.4, §14, §15. Konwencje: `00-conventions.md` (przeczytaj najpierw).

## Global Constraints
- Kolory `#EF4363` (primary), `#f8fbef` (tło), `#191919` (tekst); Nunito (treść), Sniglet tylko wordmark „Rodzina”.
- Każdy rodzic = osobne konto; po dołączeniu oboje widzą wszystko (dane obojga, dzieci, umowy).
- Kod dołączania: założyciel generuje, drugi rodzic wpisuje, założyciel akceptuje; max 2 rodziców.
- Dziecko może być „w drodze” (`status="expected"`, `due_date`).
- Persona: Nowakowie, Kraków, Małopolskie (mama Anna, tata Piotr), dane wymyślone, daty względne do dnia uruchomienia.
- Działa bez Cosmos i bez Azure.

## Review Focus
- Nieprawidłowy/wygasły/już użyty kod dołączania → 404/409 z polskim komunikatem, nie 500.
- Rodzic z cudzej rodziny nie widzi dzieci/profilu innej rodziny (izolacja po `family_id`).
- Próba dołączenia do własnej rodziny; drugi rodzic próbujący dołączyć, gdy rodzina ma już 2 członków.
- Token podrobiony/wygasły/bez nagłówka → 401; urzędnik na endpointach rodzica (i odwrotnie) → 403.
- Rodzic samotnie wychowujący (rodzina bez drugiego rodzica) działa w każdym widoku.

---

### Task 1: Repo hygiene, zależności, test harness
**Files:** Create `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/tests/conftest.py`, `backend/.env.example`, root `.gitignore` (dopisz `.venv/`, `node_modules/`, `__pycache__/`, `.DS_Store`, `.env`); Modify `backend/requirements.txt`, `.github/workflows/ci.yml` (job backend: `pip install -r requirements-dev.txt && pytest -q` przed `docker build`; job frontend: dodaj `npm test -- --run` dla `frontend`).
**Interfaces:** Produces fixtury `store`, `client`, `login`.
- [ ] Dodaj do `requirements.txt` bez zmian wersji istniejących; `requirements-dev.txt`: `-r requirements.txt`, `pytest`, `pytest-asyncio`, `httpx`. `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.
- [ ] Test `tests/test_health.py::test_health_ok`: `client.get("/health").json() == {"status":"ok"}` (czerwony: brak `create_app`).
- [ ] Zaimplementuj w Task 2; ten task kończy się, gdy venv + `pytest --collect-only` działa. Commit `chore: test harness and gitignore`.

### Task 2: Storage + app factory
**Files:** Create `backend/app/storage.py`, `backend/app/seed/__init__.py` (`async def seed_all(store: Store) -> None`), Modify `backend/app/main.py`, `backend/app/config.py` (dodaj `session_secret: str = "dev-secret-change-me"`, `session_ttl_hours: int = 12`); Test `tests/test_storage.py`.
**Interfaces:** Produces `Store` Protocol, `MemoryStore`, `CosmosStore(client_db)`, `get_store(request) -> Store`, `create_app(store=None) -> FastAPI`; `main.py` eksportuje też `app = create_app()`; auto-include routerów przez `pkgutil.iter_modules(app.routers.__path__)`.
- [ ] Testy: `test_put_get_roundtrip`, `test_find_filters_equality`, `test_delete_removes`, `test_put_requires_id` (ValueError), `test_get_returns_copy` (mutacja zwróconego dict nie zmienia store).
- [ ] `MemoryStore`: dict kolekcja→dict id→doc, `copy.deepcopy`. `CosmosStore`: kontener per kolekcja (`partition_key=/id`, `create_container_if_not_exists`), `find` przez zapytanie parametryzowane (nazwy pól walidowane regexem `^[A-Za-z_][A-Za-z0-9_]*$`).
- [ ] `create_app`: lifespan buduje store (`Cosmos` gdy `cosmos_endpoint`, inaczej `MemoryStore`), woła `seed_all`; CORS jak dotąd; istniejący router `wnioski` ma nadal działać (jest w `routers/`). Commit.

### Task 3: Auth (tokeny, persony, urzędnicy)
**Files:** Create `backend/app/security.py`, `backend/app/models/user.py`, `backend/app/routers/auth.py`, `backend/app/seed/personas.py`, `backend/app/seed/officials.py`, `backend/app/seed/units.py`; Test `tests/test_auth.py`.
**Interfaces:** Produces `Principal` dataclass, `issue_token(principal) -> str`, `verify_token(token) -> Principal` (rzuca `AuthError`), dependencies `current_principal`, `require_parent`, `require_official`; modele `User(id, role, name, email|None, persona_id|None, family_id|None, unit_id|None)`; endpointy `GET /api/auth/personas -> [{id,name,role_label}]`, `POST /api/auth/mobywatel {persona_id} -> {token,user}`, `POST /api/auth/official {email,password} -> {token,user}`, `GET /api/me -> User`.
- [ ] Testy: `test_login_persona_creates_user_once` (dwa loginy → to samo `user.id`), `test_unknown_persona_404`, `test_me_requires_token_401`, `test_tampered_token_401`, `test_expired_token_401` (ttl=−1), `test_parent_token_forbidden_on_official_dep_403`, `test_official_login_ok_and_wrong_password_401`.
- [ ] Persony: `persona-nowak-anna` (mama, 31, Kraków, ciąża, umowa o pracę na czas nieokreślony pełny etat), `persona-nowak-piotr` (tata, 34). Urzędnicy seed: `urzednik.krakow@mrodzina.local` (unit `unit-krakow`), `urzednik.malopolska@mrodzina.local` (`unit-malopolskie`), hasło z env `OFFICIAL_DEFAULT_PASSWORD` (domyślnie `demo1234`), hasła hashowane (`hashlib.scrypt`). Units seed: `unit-krakow` (level gmina, gmina "Kraków", powiat "Kraków", voivodeship "Małopolskie"), `unit-malopolskie` (level voivodeship).
- [ ] Token: base64url(JSON payload + exp) + HMAC-SHA256 (`hmac.compare_digest`). Commit.

### Task 4: Rodzina, kod dołączania, dzieci
**Files:** Create `backend/app/models/family.py`, `backend/app/services/families.py`, `backend/app/routers/families.py`; Test `tests/test_families.py`.
**Interfaces:** Produces modele `Family(id,name,owner_id,member_ids,invite_code)`, `JoinRequest(id,family_id,user_id,status: pending|accepted|rejected)`, `Child(id,family_id,name,birth_date|None,due_date|None,status: expected|born,pesel|None,has_disability=False,foster=False,situation: None|"loss"=None,situation_kind: None|"poronienie"|"martwe-urodzenie"|"smierc-dziecka"=None,situation_at: datetime|None=None,serious_illness: bool=False)`; serwis `FamilyService(store)` z `create_family`, `rotate_invite_code`, `request_join(user_id, code) -> JoinRequest`, `decide(owner_id, request_id, accept: bool)`, `add_child/update_child/delete_child`, `get_family_view(user_id) -> FamilyView(family, members:[User], children:[Child], pending_requests)`; endpointy: `POST /api/families`, `GET /api/families/me`, `POST /api/families/me/invite-code`, `POST /api/families/join {code}`, `GET /api/families/me/join-requests`, `POST /api/families/me/join-requests/{id}/accept|reject`, `GET|POST /api/families/me/children`, `PATCH|DELETE /api/families/me/children/{id}`.
- [ ] Testy (serwis + API): `test_create_family_sets_owner_and_code`, `test_second_family_for_same_user_409`, `test_join_flow_pending_then_accept_adds_member`, `test_reject_keeps_user_out`, `test_only_owner_can_decide_403`, `test_invalid_code_404`, `test_join_own_family_409`, `test_third_member_409`, `test_single_parent_family_view_ok`, `test_child_requires_birth_or_due_date_422`, `test_children_isolated_between_families`, `test_expected_child_allowed_with_due_date`.
- [ ] Kod: `NOWAK-` nie; losowy 8 znaków `[A-Z2-9]`, `secrets`. Commit.

### Task 5: Profil „Moje dane” + testowe dane ZUS
**Files:** Create `backend/app/models/profile.py`, `backend/app/services/zus_sim.py`, `backend/app/routers/profile.py`; Test `tests/test_profile.py`, `tests/test_zus_sim.py`.
**Interfaces:** Produces `ParentProfile(user_id, first_name, last_name, pesel, birth_date, address: Address(city,gmina,powiat,voivodeship,postal_code), insurance: list[Insurance(kind: "employment"|"mandate"|"jdg", payer, contribution_base: float, voluntary_sickness: bool|None, since: date)], ezla: list[Ezla(code,from_date,to_date)], contribution_debt: Debt|None, known_children: list[KnownChild(name,birth_date|None,due_date|None)], answers: dict[str,bool|str])`; `fetch_zus_data(persona_id: str, today: date) -> ParentProfile` (daty względne do `today`); endpointy `GET /api/profile -> {members:[ParentProfile+user name]}` (profile obojga rodziców rodziny), `GET /api/profile/me`, `PATCH /api/profile/me/answers {key: value}`, `GET /api/profile/me/zus` (testowy podgląd PUE: konto, składki).
- [ ] Testy: `test_zus_sim_nowak_anna_has_employment_ezla_b_and_known_children` (e-ZLA code "B", 2 znane dzieci + 1 w drodze z `due_date` ≈ today+60d), `test_zus_sim_dates_relative_to_today`, `test_login_creates_profile_from_zus`, `test_profile_visible_to_both_parents_after_join`, `test_profile_not_visible_to_other_family`, `test_patch_answers_merges_and_persists`, `test_pesel_not_in_logs` (caplog bez PESEL).
- [ ] Logowanie mObywatel (Task 3) po utworzeniu usera zapisuje `profiles/{user_id}` z `fetch_zus_data`. Persony w danych (`app/seed/personas.py`), nie w kodzie logiki. Commit.

### Task 6: Frontend — shell, motyw, API, sesja, auto-routing
**Files:** Modify `frontend/package.json` (dodaj `react-router-dom`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`; skrypt `test: vitest`), `frontend/vite.config.ts` (test env jsdom), `frontend/index.html` (Nunito + Sniglet z Google Fonts, `lang="pl"`, tytuł „mRodzina”), usuń szablon Vite (`App.css`, `assets/react.svg` itd.); Create `frontend/src/theme.css`, `lib/api.ts`, `lib/session.tsx`, `components/AppShell.tsx`, `components/Logo.tsx` (skopiuj logikę z `landing/src/components/Logo.tsx`), `App.tsx`, `main.tsx`, `features/registry.ts`; Test `lib/api.test.ts`, `lib/session.test.tsx`, `features/registry.test.ts`.
**Interfaces:** Produces `api<T>(path, init?)`, `ApiError`, `useSession()`, `features/registry.ts` eksportuje `featureRoutes: RouteObject[]`, `navItems: NavItem[]` (posortowane po `order`), `widgets: Widget[]` — oparte na `import.meta.glob('./*/routes.tsx', {eager:true})` itd.; `AppShell` renderuje nawigację z `navItems` (area parent) i `<Outlet/>`, przekierowuje niezalogowanych na `/logowanie`.
- [ ] Testy: `api` dokleja Bearer z `localStorage('token')` i mapuje 401→`ApiError.status`; `registry` sortuje nav po `order`; `AppShell` bez sesji → przekierowanie na `/logowanie`.
- [ ] `theme.css`: tokeny z Global Constraints; `[data-theme="mono"]` nadpisuje `--primary` na neutralną szarość i usuwa kolorowe akcenty; fokus widoczny. Commit.

### Task 7: Frontend — logowanie, onboarding rodziny, Moje dane
**Files:** Create `features/auth/{routes.tsx,LoginPage.tsx}`, `features/family/{routes.tsx,nav.ts,OnboardingPage.tsx,FamilyPage.tsx,JoinPage.tsx}`, `features/profile/{routes.tsx,nav.ts,ProfilePage.tsx}`; Test obok każdej strony.
**Interfaces:** Consumes API z Tasków 3–5. Trasy: `/logowanie` (karty person z `GET /api/auth/personas`), `/start` (onboarding: 1) rodzina, 2) dzieci prefilowane z `known_children` do zatwierdzenia, 3) zaproszenie drugiego rodzica z kodem lub „Dołącz do rodziny” lub „Wychowuję dziecko samodzielnie”), `/rodzina` (członkowie, kod, prośby o dołączenie z przyciskami Akceptuj/Odrzuć, dzieci), `/dane` (profil obojga z podziałem na źródła: ZUS/mObywatel, umowy (miejsce na plan 04), formularz).
- [ ] Testy: `LoginPage` pokazuje persony i po kliknięciu wywołuje login + przekierowuje; `OnboardingPage` pozwala pominąć drugiego rodzica; `FamilyPage` pokazuje prośbę pending i wywołuje accept; `JoinPage` błąd kodu pokazuje komunikat po polsku.
- [ ] Po logowaniu: brak rodziny → `/start`, inaczej `/` (dashboard dostarcza plan 03; do tego czasu `/` → `/rodzina`). Commit.

### Task 8: Weryfikacja końcowa i dokumentacja
- [ ] `backend: pytest -q` zielone; `frontend: npm test -- --run && npm run lint && npm run build` zielone; `docker build backend` (jeśli docker dostępny).
- [ ] Zaktualizuj `backend/.env.example` i dodaj `docs/dev.md` (jak uruchomić lokalnie, persony, hasło urzędnika). Commit `docs: dev guide`.
