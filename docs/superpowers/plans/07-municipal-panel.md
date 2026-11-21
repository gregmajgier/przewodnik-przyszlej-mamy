# Panel gminy / województwa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Urzędnik (konto nadane przez nas, przypisane do jednej jednostki) dodaje lokalne świadczenia z kryteriami strukturalnymi i polem „Dodatkowe wymogi”, które LLM rozbija na warunki do zatwierdzenia przed publikacją.

**Architecture:** Router `official_benefits` (za `require_official`), serwis `conditions.py` (LLM → `list[Condition]`), serwis `resolution_prefill.py` (tekst uchwały → draft kryteriów), frontend `/urzednik/*` z własnym logowaniem. Dopasowanie u rodziców jest z planu 03 (bez zmian).

**Spec:** §3.3, §7.2. Konwencje: `00-conventions.md`. Zależy od 03 (model `Benefit`, `covers`), 01 (auth urzędnika), 02 (LLM).

## Global Constraints
- Urzędnik widzi i edytuje **tylko świadczenia swojej jednostki** (`benefit.unit_id == principal.unit_id`). Publikuje tylko po zatwierdzeniu listy warunków.
- Zakres widoczności dla rodziców: gmina → mieszkańcy gminy; województwo → wszystkie gminy województwa (wynika z `covers` planu 03).
- LLM pracuje **raz, przy zapisie** („Wyodrębnij warunki”) i przy „Wypełnij z uchwały” — nigdy przy dopasowywaniu; oba za `ai_guard`.
- Warunek `auto` musi mieć `profile_key` istniejący w znanym słowniku (np. `residence_months`, `child_in_public_nursery`); nieznany → zamień na `ask` z pytaniem tak/nie.
- Status: `draft` → (`extract`) → `awaiting_approval`→ `published`; edycja opublikowanego wraca do `draft`.

## Review Focus
- Urzędnik jednostki A próbuje czytać/edytować/publikować świadczenie jednostki B → 404/403.
- Publikacja bez zatwierdzonej listy warunków przy niepustym `extra_text` → 409.
- LLM zwraca warunki sprzeczne/puste/duplikaty → normalizacja, bez zapisu śmieci; błąd LLM → komunikat „Nie udało się wyodrębnić warunków — dodaj je ręcznie”.
- Rodzic spoza obszaru nie widzi świadczenia po publikacji (test end-to-end z planem 03).
- Rodzic może dostać token urzędnika? Nie: token rodzica na `/api/official/*` → 403.

---

### Task 1: Warunki z tekstu (LLM)
**Files:** Create `backend/app/services/conditions.py`, `backend/tests/test_conditions.py`; demo handler `backend/app/seed/demo_conditions.py` (+ jedna linia importu w `seed/__init__`).
**Interfaces:** Produces `PROFILE_KEYS: dict[str,str]` (klucz→opis), `async def extract_conditions(llm: LLM, text: str) -> list[Condition]` (normalizuje: unikalne `id` slug, `kind=auto` tylko dla `PROFILE_KEYS`, reszta `ask` z `question` kończącym się „?”), `async def prefill_from_resolution(llm: LLM, text: str) -> BenefitDraft(name, description, amount_text, criteria: Criteria, extra_text)`.
- [ ] Testy z `FakeLLM`: `test_unknown_profile_key_becomes_ask`, `test_duplicates_removed`, `test_empty_text_returns_empty_without_llm_call`, `test_llm_error_raises_conditions_error`, `test_prefill_maps_age_and_income`, `test_demo_handler_extracts_residency_condition` („zameldowanie w gminie od co najmniej 12 miesięcy” → `ask`/`auto`). Commit.

### Task 2: API urzędnika
**Files:** Create `backend/app/routers/official_benefits.py`, `backend/tests/test_official_benefits.py`.
**Interfaces:** `GET /api/official/me -> {user, unit}`; `GET /api/official/benefits` (tylko własna jednostka); `POST /api/official/benefits` (draft; `scope` i `unit_id` ustawiane serwerowo z jednostki — `municipal` dla gminy, `regional` dla województwa); `GET|PUT|DELETE /api/official/benefits/{id}`; `POST /api/official/benefits/{id}/extract-conditions` (zapisuje `extra_conditions` jako propozycję, status `awaiting_approval`); `POST /api/official/benefits/{id}/approve-conditions {conditions:[Condition]}` (urzędnik poprawia/zatwierdza); `POST /api/official/benefits/{id}/publish`; `POST /api/official/benefits/{id}/unpublish`; `POST /api/official/prefill-from-text {text} -> BenefitDraft`.
- [ ] Testy: wszystkie z Review Focus + `test_scope_and_unit_set_from_official`, `test_publish_makes_benefit_visible_to_residents_only` (rodzina Nowaków widzi świadczenie Krakowa, nie widzi Gdańska), `test_voivodeship_benefit_visible_to_krakow_family`, `test_edit_published_goes_back_to_draft`, `test_ai_endpoints_rate_limited`. Commit.

### Task 3: Seed przykładowych świadczeń lokalnych
**Files:** Create `backend/app/data/benefits_local_sample.json`, `backend/app/seed/benefits_local.py`.
- [ ] 3–4 przykładowe, **wyraźnie oznaczone jako przykładowe** (`name` z dopiskiem „(przykład)”), np. dopłata do żłobka w Krakowie, rekrutacja/wsparcie dla rodzin 3+ w Małopolsce — zgodne z modelem planu 03, opublikowane; test seeda ładuje i waliduje. Commit.

### Task 4: Frontend `/urzednik`
**Files:** Create `frontend/src/features/official/{routes.tsx,OfficialLogin.tsx,OfficialLayout.tsx,BenefitsList.tsx,BenefitEditor.tsx,ConditionsReview.tsx,nav.ts}`, testy.
**Interfaces:** Trasy `/urzednik/logowanie`, `/urzednik` (lista), `/urzednik/swiadczenia/:id` (edytor). `nav.ts` z `area: "official"` (osobna nawigacja w `OfficialLayout`, nie w AppShell rodzica). Edytor: pola kryteriów (wiek od–do w latach/miesiącach, maks. dochód na osobę, min. dzieci, niepełnosprawność, rodzina zastępcza, zatrudnienie), opis, kwota, termin, sposób złożenia, link/PDF, pole „Dodatkowe wymogi” z przyciskiem „Wyodrębnij warunki”, lista warunków do edycji i zatwierdzenia, przycisk „Opublikuj” aktywny dopiero po zatwierdzeniu; „Wklej uchwałę → wypełnij” (prefill).
- [ ] Testy: logowanie urzędnika; edytor blokuje publikację do zatwierdzenia warunków; wyodrębnione warunki można edytować i usuwać; błąd AI pokazuje komunikat z fallbackiem ręcznym. Commit.

### Task 5: Weryfikacja
- [ ] Testy i build zielone; `docs/dev.md`: konta urzędników. Commit.
