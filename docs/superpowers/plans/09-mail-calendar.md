# Poczta testowa (podłączona domyślnie), statusy wniosków i kalendarz — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Symulowana skrzynka rodziny Nowaków (domyślnie podłączona) z predefiniowanymi mailami i odpowiedziami urzędów, filtr tylko wątków wniosków, klasyfikacja LLM odpowiedzi → status wniosku, kalendarz terminów i ostrzeżeń oraz powiadomienia w aplikacji.

**Architecture:** Rozszerza `SimMailProvider` (plan 08) o inbox i reakcje na wysłane wnioski; `services/mail_filter.py` (czysty filtr), `services/mail_classify.py` (LLM → status+pewność), `services/mail_sync.py` (cykl pobierania), `services/calendar_gen.py`, router `calendar`, `mail`, `notifications`; zadanie w tle w `lifespan` (opcjonalne, wyłączane w testach).

**Spec:** §9, §10. Konwencje: `00-conventions.md`. Zależy od 08 (Application, MailProvider), 03 (Benefit.deadline), 02 (LLM).

## Global Constraints
- Poczta testowa, **domyślnie podłączona**; w ustawieniach „Gmail podłączony” z opisem: czytamy tylko wątki wniosków i maile z dokładnych adresów odbiorców (+ domeny instytucjonalne: `zus.pl`, `gov.pl`, domeny urzędów z katalogu); **nigdy cała domena publiczna** (`gmail.com`, `onet.pl`, `wp.pl`, `outlook.com`, …). Skrzynka zawiera też maile niezwiązane, które filtr pomija.
- Klasyfikacja LLM: statusy `received|more_info|accepted|rejected|other`; `confidence ≥ 0.8` → status zmienia się automatycznie + powiadomienie; poniżej → powiadomienie „Nowa wiadomość w sprawie wniosku X — sprawdź” bez zmiany statusu.
- Odpowiedzi testowe: pracodawca → „otrzymaliśmy” (potem „zatwierdzony”), ZUS → „wezwanie do uzupełnienia”, gmina → „decyzja pozytywna”; dostarczane po `MAIL_SIM_REPLY_DELAY_S` (domyślnie 20 s) albo natychmiast przez `POST /api/mail/simulate-replies` (do demo).
- Kalendarz: wpisy można odkliknąć (`done`), mają przyjazne podsumowanie, uwzględniają „do kiedy złożyć” i „jak długo trwa efekt”, zagrożenie utraty świadczenia, zmiany stawek; widać „kto złożył”.
- Prototyp: ostrzeżenia **tylko w aplikacji**. E-mail/SMS = wizja (nie implementować; zostaw w UI wzmiankę „Wkrótce: przypomnienia mailem i SMS-em”).
- Treść maili nie trafia do logów.

## Review Focus
- Mail od `jan@gmail.com` do rodzica o tej samej domenie co pracodawca na gmail.com nie jest czytany ani zapisany jako powiązany z wnioskiem.
- Ten sam mail przetworzony dwa razy (kolejne sync) → jedna zmiana statusu i jedno powiadomienie (idempotencja po `message_id`).
- Klasyfikator zwraca śmieć/timeout → wiadomość trafia do „do sprawdzenia”, status bez zmian.
- Rodzic A nie widzi skrzynki rodziny B; partner widzi wspólne wątki rodziny.
- Wniosek przedawniony / termin w przeszłości → wpis oznaczony „po terminie”, nie crash przy generowaniu.
- Zmiana daty porodu przelicza terminy, nie duplikuje wpisów (stabilne `id` wpisów generowanych).

---

### Task 1: Filtr i skrzynka testowa
**Files:** Create `backend/app/models/mail.py`, `backend/app/services/mail_filter.py`, `backend/app/mail/sim_inbox.py`, `backend/app/seed/mail_seed.py`, `backend/tests/test_mail_filter.py`.
**Interfaces:** Produces `MailMessage(id, family_id, folder: inbox|sent, from_addr, to_addr, subject, body, thread_id|None, message_id, in_reply_to|None, received_at, related_application_id|None, classified: bool)`; `PUBLIC_DOMAINS: frozenset[str]`, `INSTITUTIONAL_DOMAINS: frozenset[str]` (z katalogu + `zus.pl`, `gov.pl`); `def matches_application(msg: MailMessage, app: Application) -> bool` (reguły: `in_reply_to`/`thread_id` zgodny, albo `from_addr == app.recipient_email`, albo domena nadawcy ∈ institutional i == `app.recipient_domain`; wiadomość sprzed `sent_at` nie pasuje); `SimMailProvider.deliver_reply(app)`.
- [ ] Testy: `test_thread_match`, `test_exact_address_match`, `test_institutional_domain_match`, `test_public_domain_never_matches_by_domain`, `test_message_before_sent_at_ignored`, `test_unrelated_inbox_mails_present_in_seed_and_ignored`. Seed: 5–6 niezwiązanych maili Nowaków (sklep, szkoła, przychodnia, newsletter). Commit.

### Task 2: Klasyfikacja i synchronizacja
**Files:** Create `backend/app/services/mail_classify.py`, `backend/app/services/mail_sync.py`, `backend/app/seed/demo_mail.py`, `backend/tests/test_mail_sync.py`.
**Interfaces:** `class Classification(BaseModel): status: Literal["received","more_info","accepted","rejected","other"]; confidence: float; summary: str`; `async def classify(llm, msg) -> Classification` (błąd → `other`, 0.0); `async def sync_family_mail(store, mail, llm, family_id, now) -> SyncReport(new_messages:int, status_changes:int, to_review:int)`; powiadomienia (`notifications`: `Notification(id, family_id, user_ids, kind, text, link, created_at, read)`).
- [ ] Testy z `FakeLLM`: `test_high_confidence_changes_status_and_notifies`, `test_low_confidence_notifies_without_status_change`, `test_sync_is_idempotent`, `test_classifier_error_goes_to_review`, `test_unrelated_mail_not_classified` (LLM niewywołany), `test_demo_handler_classifies_by_keywords`. Commit.

### Task 3: Kalendarz
**Files:** Create `backend/app/models/calendar.py`, `backend/app/services/calendar_gen.py`, `backend/app/routers/calendar.py`, `backend/app/tools/calendar.py`, `backend/tests/test_calendar.py`.
**Interfaces:** `CalendarEvent(id, family_id, kind: deadline|application|child|warning, title, summary, due_date|None, effect_until|None, done=False, source_ref, child_id|None, actor_user_id|None, status|None)`; `def generate_events(family_view, benefits_with_match, applications, risks, today) -> list[CalendarEvent]` (ID deterministyczne: `hash(kind+source_ref+child_id)`; `deadline` z `Benefit.deadline` względem narodzin/porodu; wnioski → wpis z „kto złożył”; ryzyka → `warning`); `GET /api/calendar?from&to`, `PATCH /api/calendar/{id} {done}`, `GET /api/notifications`, `POST /api/notifications/{id}/read`; narzędzie MCP `kalendarz`. Regeneracja przy odczycie zachowuje `done`.
- [ ] Testy: `test_due_date_generates_prebirth_deadlines`, `test_birth_unlocks_800plus_deadline_3_months`, `test_done_preserved_on_regeneration`, `test_overdue_marked`, `test_application_event_shows_who_submitted`, `test_warning_from_risk`, `test_ids_stable_no_duplicates_after_due_date_change`. Commit.

### Task 4: Router poczty i zadanie w tle
**Files:** Create `backend/app/routers/mail.py`, `backend/tests/test_mail_api.py`; Modify `backend/app/main.py` (jedna zmiana: uruchom `asyncio.create_task(poll_loop)` w lifespan gdy `MAIL_POLL_S>0`; w testach 0).
**Interfaces:** `GET /api/mail/status -> {connected: true, provider: "gmail-sim", address, scope_note}`; `GET /api/mail/threads` (tylko wątki powiązane z wnioskami, z klasyfikacją/statusem); `POST /api/mail/sync`; `POST /api/mail/simulate-replies` (demo: dostarcza oczekujące odpowiedzi natychmiast, potem sync). Sim dostarcza odpowiedź po `submit` zgodnie z regułami z Global Constraints.
- [ ] Testy: `test_status_connected_by_default`, `test_threads_only_application_related`, `test_submit_then_simulate_replies_changes_application_status`, `test_family_isolation`, `test_poll_loop_disabled_in_tests`. Commit.

### Task 5: Frontend — kalendarz, poczta, powiadomienia
**Files:** Create `frontend/src/features/calendar/{routes.tsx,nav.ts,CalendarPage.tsx,EventCard.tsx,widget.tsx}`, `features/mail/{routes.tsx,nav.ts,MailPage.tsx,MailSettings.tsx}`, `features/notifications/{NotificationBell.tsx}` (osadzany w AppShell przez jedną minimalną zmianę slotu w `AppShell`: komponent `HeaderSlot` z registry; jeśli slotu brak, dodaj go), testy.
**Interfaces:** `/kalendarz` — lista chronologiczna + oś (bez zewnętrznych bibliotek), odklikanie, filtr „zagrożone”, każdy wpis z podsumowaniem i „kto/gdzie/do kogo”; widget dashboardu (`order: 10`) „Najbliższe terminy” + ostrzeżenia; `/poczta` — „Poczta ZUS / urzędy”: wątki wniosków, status, przycisk „Sprawdź pocztę”, w trybie demo „Symuluj odpowiedzi”; ustawienia: „Gmail podłączony”, opis zakresu, wzmianka „Wkrótce: przypomnienia mailem i SMS-em”; dzwonek z licznikiem nieprzeczytanych.
- [ ] Testy: odklikanie wpisu wywołuje PATCH; wątki pokazują status; dzwonek pokazuje licznik; ustawienia pokazują zakres czytania. Commit.

### Task 6: Weryfikacja
- [ ] Test integracyjny `tests/test_flow_mail_calendar_e2e.py`: Anna składa wniosek → odpowiedzi testowe → status zmienia się → wpis w kalendarzu i powiadomienie. Pełne testy/build zielone; `docs/dev.md`. Commit.
