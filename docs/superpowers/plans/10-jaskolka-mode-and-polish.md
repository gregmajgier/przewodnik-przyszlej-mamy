# Tryb jaskółki w koncie, „Za życiem” i integracja końcowa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zgłoszenie straty dziecka w koncie przełącza całą rodzinę w spokojny tryb monochromatyczny (bez przypomnień i wniosków o dziecko, z właściwymi świadczeniami i wstępnie wypełnionymi wnioskami); oznaczenie „Za życiem” dodaje świadczenia bez trybu; spinamy całość scenariuszem end-to-end.

**Architecture:** Pole `Child.situation`/`situation_at` (plan 01) + serwis `situations.py` z efektami ubocznymi (anulowanie szkiców, wyciszenie kalendarza, filtr dopasowania), endpointy w `routers/situations.py`, tryb UI przez `data-theme="mono"` ustawiany na podstawie `/api/me/mode`.

**Spec:** §13.2, §13.3, §2 (anty-cele). Konwencje: `00-conventions.md`. Zależy od 03, 05, 08, 09.

## Global Constraints
- Zgłosić może **każde z rodziców**; opcja „Zmiana sytuacji” na karcie dziecka jest spokojna, bez pól, uzasadnień i „czy na pewno?”. Wybór z tej samej listy co `/jaskolka`: `poronienie`, `martwe-urodzenie`, `smierc-dziecka`.
- **Cofnięcie przez 7 dni** (`UNDO_WINDOW_DAYS=7`); po tym czasie tylko ręczne wyjście z trybu przez „Wróć do zwykłego widoku”.
- Efekty u **obojga** rodziców: znikają przypomnienia, świadczenia i teksty o tym dziecku (800+, PESEL, „gratulacje”, plan urlopu); szkice wniosków o to dziecko anulowane po cichu; wnioski już wysłane oznaczone `child_loss_note`; drugi rodzic **nie dostaje powiadomienia**.
- Tryb: monochromatyczny motyw, jedna lista „Dla Was” z właściwymi świadczeniami (urlop/zasiłek macierzyński po stracie, zasiłek pogrzebowy, akt urodzenia martwego dziecka, urlop okolicznościowy drugiego rodzica, fundacje z planu 05) i wnioskami **wstępnie wypełnionymi z profilu**.
- Nie usuwamy dziecka z profilu (imię zostaje); nie wychodzimy z trybu automatycznie; inne dzieci zostają, ich krytyczne terminy wyciszone, w tym samym stylu.
- „Za życiem”: flaga `serious_illness` na dziecku → dodaje świadczenia (4000 zł, wsparcie) **bez** trybu jaskółki.
- Czat zna sytuację (przez narzędzie `profil_rodziny`) i nie proponuje świadczeń o utraconym dziecku.

## Review Focus
- Zgłoszenie straty dla dziecka, które jest „w drodze” (poronienie) i dla urodzonego (śmierć) — oba działają; przy wielu dzieciach tylko jedno przechodzi w sytuację.
- Cofnięcie w 7. dniu działa, w 8. → 409 z komunikatem po polsku; po cofnięciu szkice anulowane wcześniej **nie** wracają (zapisane jako anulowane), ale świadczenia i kalendarz wracają.
- Drugi rodzic bez żadnego powiadomienia widzi tryb przy następnym wejściu (sprawdź `notifications`).
- Żadna strona/komponent trybu nie renderuje słów „gratulacje”, „800+”, „PESEL dziecka” dla tego dziecka (test snapshot/tekstu).
- Jednoczesne zgłoszenie przez oboje rodziców — idempotentne.

---

### Task 1: Serwis sytuacji i efekty
**Files:** Create `backend/app/services/situations.py`, `backend/tests/test_situations.py`; Modify (minimalnie) `backend/app/services/matching.py` — odfiltrowanie świadczeń związanych z dzieckiem w sytuacji `loss` i dodanie świadczeń z tagiem `loss_support` (dodaj `tags: list[str]` do `Benefit` jeśli brak; seed kilku pozycji w `backend/app/data/benefits_loss.json` ze źródłami), `backend/app/services/calendar_gen.py` (pomiń zdarzenia dziecka w sytuacji, wycisz inne dzieci), `backend/app/tools/chat_tools.py` (profil_rodziny zawiera `situation`).
**Interfaces:** `async def set_situation(store, principal, child_id, kind: Literal["poronienie","martwe-urodzenie","smierc-dziecka"]) -> Child` (idempotentne; ustawia `situation="loss"`, `situation_kind`, `situation_at`; woła `cancel_drafts_for_child`, oznacza wysłane wnioski `child_loss_note`); `async def undo_situation(store, principal, child_id) -> Child` (409 po oknie); `async def exit_mode(store, principal) -> None`; `def family_mode(children) -> Literal["normal","jaskolka"]`; `async def set_serious_illness(store, principal, child_id, value: bool)`.
- [ ] Testy: wszystkie z Review Focus + `test_no_notification_created_for_partner`, `test_benefits_for_lost_child_hidden_and_loss_support_shown`, `test_other_children_events_muted_not_removed`, `test_serious_illness_adds_za_zyciem_without_mode`, `test_chat_tool_profile_includes_situation`. Commit.

### Task 2: API
**Files:** Create `backend/app/routers/situations.py`, `backend/tests/test_situations_api.py`.
**Interfaces:** `POST /api/families/me/children/{id}/situation {kind}`, `DELETE /api/families/me/children/{id}/situation` (cofnięcie), `POST /api/families/me/mode/exit`, `PATCH /api/families/me/children/{id}/serious-illness {value}`, `GET /api/me/mode -> {mode, since, undo_until|None, child_id|None}`.
- [ ] Testy API: autoryzacja (rodzic innej rodziny 404), idempotencja, `mode` zwracany obojgu. Commit.

### Task 3: Frontend — tryb jaskółki
**Files:** Create `frontend/src/features/situations/{routes.tsx,SituationMenu.tsx,JaskolkaHome.tsx,useFamilyMode.ts}`, Modify (minimalnie) `frontend/src/components/AppShell.tsx` (ustaw `data-theme` wg `useFamilyMode`; w trybie „jaskolka” renderuj tylko `JaskolkaHome` jako stronę główną i ukryj kolorowe widgety), dodaj w `features/family/FamilyPage.tsx` spokojną opcję „Zmiana sytuacji” na karcie dziecka (menu `SituationMenu`).
**Interfaces:** `JaskolkaHome`: jedna lista „Dla Was” (świadczenia `loss_support` z `/api/benefits` + wnioski wstępnie wypełnione + fundacje z `/api/jaskolka/foundations`), na dole „Cofnij zgłoszenie” (do końca okna) i „Wróć do zwykłego widoku”; wyciszone terminy innych dzieci w tym samym stylu; brak animacji; flaga „Za życiem” jako przełącznik w karcie dziecka z komunikatem o dodanych świadczeniach.
- [ ] Testy: `SituationMenu` bez dialogu potwierdzenia (jedno kliknięcie wybiera opcję); w trybie `jaskolka` brak tekstów zakazanych („gratulacje”, „800+”, „PESEL dziecka”); `data-theme="mono"` ustawione; cofnięcie widoczne tylko w oknie. Commit.

### Task 4: Test end-to-end całego produktu
**Files:** Create `backend/tests/test_e2e_nowak.py`.
- [ ] Jeden scenariusz API: Anna loguje się (persona) → tworzy rodzinę i dzieci z `known_children` → generuje kod → Piotr loguje się, dołącza, Anna akceptuje → `/api/analysis` zwraca dopasowania (w tym `maybe` z pytaniem; odpowiedź zmienia status) → wgranie umowy (demo LLM) i zatwierdzenie → `/api/risks` → wniosek urlopowy → submit → symulowane odpowiedzi → status i kalendarz → czat (FakeLLM) odpowiada z cytatem artykułu → urzędnik Krakowa publikuje świadczenie, rodzina Nowaków je widzi → Anna zgłasza stratę dziecka w drodze, Piotr widzi tryb bez powiadomienia, szkice anulowane → cofnięcie. Test ma być czytelny jako dokumentacja scenariusza.
- [ ] Commit.

### Task 5: Dokumentacja i weryfikacja końcowa
- [ ] `README.md` w korzeniu (opis produktu, struktura, jak uruchomić, persony, konta urzędników, zmienne środowiskowe, co jest symulowane a co prawdziwe, funkcje „wizja” z podziałem [P]/[W]); `docs/dev.md` spójne. Pełne testy backend/frontend/landing + build, `docker build backend` (jeśli dostępny), lint. Commit `docs: readme and final verification`.
