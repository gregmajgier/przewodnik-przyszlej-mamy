# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

mRodzina is a Polish app for expecting parents: it knows the family (simulated mObywatel/ZUS data and employment contracts), tells them which benefits they qualify for and why, fills in applications, and tracks deadlines. A separate public path, `/jaskolka`, needs no login and serves parents after a loss or during a child's serious illness.

**Detailed docs** (Polish): `docs/dev.md` is the developer guide. Every subsystem has a section there: env vars, AI limits, benefits engine, applications/agent, contracts, official panel, mail/calendar, chat, loss mode. Product spec: `docs/superpowers/specs/2026-11-21-mrodzina-design.md`. Implementation plans and conventions: `docs/superpowers/plans/` (start with `00-conventions.md`; decision notes are in `NOTES-*.md`). Read the relevant `docs/dev.md` section before changing a subsystem.

## Commands

Requirements: Python 3.12 (the Docker image and CI use 3.12) and Node ≥ 22.12. On older Node 22.x, `npm ci` skips the rolldown native binding and tests fail with "Cannot find native binding".

```bash
# backend (FastAPI) → http://localhost:8000/docs
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q                                   # all tests
.venv/bin/pytest tests/test_matching.py -q            # one file
.venv/bin/pytest tests/test_matching.py::test_name -q # one test
.venv/bin/pytest -k "jaskolka" -q                     # by keyword
.venv/bin/uvicorn app.main:app --reload

# frontend (parent + official app, React/Vite/TS) → http://localhost:5173
cd frontend && npm ci && npm run dev
npm test -- --run                                     # vitest, all tests once
npm test -- --run src/features/family/FamilyPage.test.tsx   # one file
npm test -- --run -t "<test name substring>"          # by test name
npm run lint && npm run build                         # oxlint; tsc -b + vite build

# landing (marketing site)
cd landing && npm ci && npm run dev    # verify with: npm run lint && npm run build
```

Full verification, the same as CI: `cd backend && .venv/bin/pytest -q` plus `cd frontend && npm test -- --run && npm run lint && npm run build` plus `cd landing && npm run build`. CI also runs `docker build backend`.

Data/maintenance scripts in `backend/scripts/` need network access: `build_laws_index.py` refreshes the law index from the Sejm ELI API, `check_jaskolka_urls.py` checks the foundation links, and `make_sample_contract.py` regenerates the sample contract PDF.

## Runs fully offline by default

With no env configured, the app uses `MemoryStore` (in-process data, reset on restart), `DemoLLM` (deterministic demo answers) and simulated ZUS/mObywatel/mail/e-signature. Code and tests **must keep working without Azure**. Setting `COSMOS_*` switches the backend to `CosmosStore`, and setting `AZURE_OPENAI_*` switches it to the real model (`FoundryLLM`). `ENV` other than `dev` (or a set `COSMOS_ENDPOINT`) turns on fail-closed startup validation: a real `SESSION_SECRET` of at least 32 characters is required, and the `demo1234` official password is disabled. All env vars are listed in `backend/.env.example`. The frontend reads `VITE_API_URL` (see `frontend/.env.example`).

Login personas: parents `persona-nowak-anna` and `persona-nowak-piotr` (on `/logowanie`). Officials `urzednik.krakow@mrodzina.local` and `urzednik.malopolska@mrodzina.local` log in at `/urzednik/logowanie` with password `demo1234` in dev.

## Architecture

### Backend (`backend/app/`)

- **Auto-discovery, no central registration.** `main.py::create_app(store=None)` includes every module in `routers/` that exposes `router` (and calls its optional `install(app)` hook). `ai/tools.py::load_all_tools()` imports every module in `tools/`, and those modules register MCP tools with `@tool(name, description, json_schema)`. To add a feature, add a file. Don't edit shared wiring.
- **Layers:** `routers/` handles HTTP only. `services/` holds the domain logic as pure functions/classes that can be tested without HTTP. `models/` holds pydantic models, stored as `model_dump(mode="json")`. `seed/` contains `seed_all(store)`, which runs on startup and is idempotent: fixed `id`s and upserts. Static domain data (benefit catalogue, law index, form catalogue, PDF field maps, portal schemas, jaskolka content) lives in `data/` as committed JSON/PDF.
- **Storage:** `storage.py` defines the `Store` protocol, which has only four async methods: `get`, `put` (upsert; `id` is required), `delete` and `find(coll, **eq)` (equality on top-level fields). Collections are fixed in `COLLECTIONS`. Get the store with the `get_store` dependency.
- **Auth:** HMAC bearer tokens. Use the `require_parent`, `require_official` and `current_principal` dependencies from `security.py`. Everything under `/api/*` needs a token except `/api/auth/*`, `/api/jaskolka/*` and `/health`. Domain errors: `raise DomainError(status, "polski komunikat")`. The API's `detail` is always Polish.
- **All LLM access goes through `app/ai`:** `get_llm()` (FastAPI dependency) plus `ai_guard("feature")` (rate limits, atomic token-budget reservation, fail-closed 503). After the call, use `record_usage(ctx, usage)`; if the model wasn't called, use `await ctx.release()`. Demo answers are registered per feature with `register_demo_handler` in `seed/demo_*.py`. Tests override `get_llm` with `FakeLLM().script(LLMResult(...))`.
- **Benefit matching is deterministic code; the LLM never decides eligibility.** `services/matching.py::match_benefit` returns `fits | maybe | no`, each with `reasons`. A missing income → `maybe` plus a question, never `no`. Child age is in full completed months, and both bounds are inclusive.
- **Chat** (`services/chat.py`, `routers/chat.py`) streams SSE. The model gets tools through the in-process MCP server (`mcp_server.py`). Tool results are wrapped as data, and identity always comes from the token, never from model arguments.
- **Applications** (`services/applications.py`, `services/prefill.py`): draft → `needs_input` → sign (fingerprint of the data; any later change invalidates the signature, and submit returns 409) → submit (idempotent). The portal agent gets only the field schema and never any personal data.
- **Loss mode** (`services/situations.py`): reporting a child's loss switches the whole family into a mono "jaskółka" mode. Other modules consult the pure helpers (`family_mode`, `event_policy`, `loss_support_applies`). `tests/test_e2e_nowak.py` is the end-to-end scenario and doubles as documentation.

Backend tests: the fixtures `store` and `client`, and the helpers `login(client, persona_id)` and `login_official(client, email)` are in `tests/conftest.py` (`from conftest import login`). pytest-asyncio runs in auto mode.

### Frontend (`frontend/src/`)

- **Feature registry:** `features/registry.ts` collects `features/*/routes.tsx` (default export `RouteObject[]`; mark public routes with `handle: { public: true }`), plus the optional `nav.ts`, `widget.tsx`, `profile-section.tsx` and `header-slot.tsx`, all via `import.meta.glob`. A feature plugs itself in without touching shared files.
- `lib/api.ts`: `api<T>(path, init)` adds the bearer token and throws `ApiError{status, detail}`. `lib/session.tsx`: `useSession()`. `components/AppShell.tsx` is the parent shell; it switches to `JaskolkaHome` and `data-theme="mono"` in loss mode. `features/official/` is a separate shell for officials.
- Styling: plain CSS, one file per feature. Always use the tokens in `theme.css`, never hard-coded hex values. Shared UI primitives are in `ui/`, brand elements in `brand/`. The visual style follows `landing/` (Nunito; Sniglet only for the word "Rodzina" in the wordmark; pill buttons; accent `#ef4363` on `#f8fbef`). Simulated or AI elements use `--ai` and carry a visible "SYMULACJA" label. Transition/splash screens always show the logo together with the "Rodzina" text.
- Tests: vitest + Testing Library, `*.test.tsx` next to the code. Use the helpers in `src/test/` (`renderWithSession`, `makeSession`, fixtures, `routeApi` for mocking API routes).

## Product rules that tests enforce

- UI and API text is Polish: warm, direct, informal "ty" voice. Code identifiers are English (exceptions: the `wnioski` router and data files).
- After a loss, the app never reminds the family about 800+ or PESEL and never congratulates them (content test in `features/situations`). `/jaskolka` and loss mode are calm, with no exclamation marks and no accent colour.
- The chat always cites an article with a link. Without a source it says "nie wiem" and points to where to ask. It never submits applications.
- Sensitive data (PESEL, earnings, contract scans, email bodies) must never reach logs or the model's `profil_rodziny` tool.
- Legal values and amounts come from official sources with an `https` `source_url`. Uncertain entries get `"verify": true`. `tests/test_benefits_seed.py` validates every catalogue record.
- Respect `prefers-reduced-motion`, keep touch targets ≥ 44 px, support layouts down to 360 px, and meet AA contrast.

## Git and deploy

- Work on `dev` (or a feature branch merged into `dev`). A required check allows PRs into `main` **only from `dev`**.
- Pushing to `main` deploys: `deploy-backend.yml` builds in ACR and deploys to Azure Container App `ca-mrodzina-backend`; `deploy-swa.yml` builds landing and frontend to Static Web Apps, with `VITE_APP_URL` and `VITE_API_URL` baked in at build time.
- Commit style: `feat|fix|test|docs|chore: ...`. Never commit `.env`, `.venv` or keys.
