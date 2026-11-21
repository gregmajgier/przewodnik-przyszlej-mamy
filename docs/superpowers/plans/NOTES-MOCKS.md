# NOTES-MOCKS — tymczasowe interfejsy planów 03 i 08 (gałąź Michała: plany 04, 07, 09)

Plany 07 i 09 zależą od planów 03 (świadczenia) i 08 (wnioski), które robi kto inny i których nie ma
na gałęzi `assignment/michal-plans-04-07-09`. Żeby nie czekać, w `backend/app/mocks/` są **minimalne
mocki** tych interfejsów, odtworzone z opisów w `03-benefits.md` i `08-applications.md`.
**Po scaleniu prawdziwych planów 03/08 trzeba je podmienić i usunąć pakiet `app/mocks/`.**

| Mock (`backend/app/mocks/…`) | Zastępuje (prawdziwy moduł) | Kto używa | Uwagi do dopasowania |
|---|---|---|---|
| `benefit.py`: `Criteria`, `Condition`, `Deadline`, `Benefit` | `app/models/benefit.py` (plan 03) | plan 07 (cały), plan 09 (kalendarz) | **Rozszerzenia wymagane przez plan 07:** `Benefit.status` ma też `awaiting_approval`; dodatkowe pola `deadline_text`, `apply_url`. Trzeba je dopisać do prawdziwego modelu. |
| `units.py`: `covers`, `units_for` | `app/services/units.py` (plan 03) | plan 07, `benefit_catalog.py` | Prawdziwa wersja dla gminy sprawdza też powiat. |
| `benefit_catalog.py`: `visible_benefits`, `naive_match`, `SAMPLE_NATIONAL` | `GET /api/benefits` + `match_benefit` + seed krajowy (plan 03) | plan 07 (testy widoczności), plan 09 (kalendarz) | `naive_match` patrzy tylko na wiek dziecka/ciążę. Po scaleniu: kalendarz bierze `{benefit, match}` z `benefit_service` planu 03, a `SAMPLE_NATIONAL` (3 świadczenia z prefiksem `mock-`) znika. |
| `application.py`: `Application`, `list_family_applications`, `mock_submit` | `app/models/application.py` + `POST /api/applications/{id}/submit` (plan 08) | plan 09 | `mock_submit` robi tylko część wysyłki potrzebną planowi 09: mail w `sent`, `thread_id`, `recipient_*`, `sent_at`, status `sent`. Prawdziwy `submit` musi po wysyłce wywołać `app.mail.sim_inbox.schedule_reply(store, app)` (hak planu 09). |
| `mail_provider.py`: `MailProvider`, `SentMessage`, `SimMailProvider`, `get_mail` | `app/mail/provider.py` + `app/mail/__init__.get_mail` (plan 08) | plan 09 | Skrzynka odbiorcza (plan 09) jest w `app/mail/sim_inbox.py` i korzysta z tego samego `SimMailProvider`. |
| `app/routers/mock_applications.py` (`/api/mock/applications`) | kreator wniosków (plan 08) | demo planu 09 (frontend `/poczta`) | Endpoint tylko do demo: „złóż” przykładowy wniosek bez planu 08. Do usunięcia po scaleniu planu 08. |

## Inne zmiany w plikach spoza moich planów (do sprawdzenia przy scalaniu)
- `backend/app/mail/__init__.py` — utworzony przez plan 09 (pakiet `app/mail/`), a plan 08 też go tworzy, więc
  przy scalaniu będzie konflikt add/add. Docelowo `get_mail()` z planu 08 powinno zwracać `SimInbox`
  (`app/mail/sim_inbox.py`), bo rozszerza on `SimMailProvider` o skrzynkę odbiorczą.
- `backend/app/main.py` — jedna zmiana w `lifespan`: start `poll_loop` (plan 09 na to pozwala).
- `backend/tests/conftest.py` — `MAIL_POLL_S=0` dla testów.
- `frontend/src/features/registry.ts` + `components/AppShell.tsx` — slot nagłówka `features/<nazwa>/header-slot.tsx`
  (dzwonek powiadomień, plan 09).
- `backend/app/seed/__init__.py` — importy handlerów demo i seed świadczeń lokalnych.

## Jak podmienić po scaleniu
1. `grep -rn "app.mocks\|from \.\.mocks\|from \.mocks" backend/` — każdy import zamienić na prawdziwy moduł.
2. Dopisać do prawdziwego `Benefit` rozszerzenia z tabeli (status `awaiting_approval`, `deadline_text`, `apply_url`).
3. W prawdziwym `submit` (plan 08) wywołać `schedule_reply` z `app/mail/sim_inbox.py`.
4. Kalendarz (`services/calendar_gen.py`) przyjmuje `benefits_with_match` z polami `benefit` i `status`:
   przekazać wynik silnika planu 03 (`match.status`).
5. Usunąć `backend/app/mocks/`, `routers/mock_applications.py` oraz przycisk „Wyślij przykładowy wniosek (demo)”
   w `frontend/src/features/mail/MailPage.tsx`. Testy korzystające z mocków mają komentarz `# MOCK planu 0x`
   przy imporcie; `test_mail_api.py` i `test_flow_mail_calendar_e2e.py` wysyłają wnioski przez
   `/api/mock/applications` — przepiąć je na prawdziwe `POST /api/applications` + `/submit`.
6. Frontend `features/official/types.ts` ma lokalne typy `Benefit/Condition/Criteria` — przenieść do wspólnych.
