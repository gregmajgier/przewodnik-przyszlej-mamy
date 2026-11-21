# NOTES-10 — decyzje i odstępstwa (plan 10 tryb jaskółki i integracja)

## Stan względem zależności (03, 08, 09)
Plan 10 zależy od planów 03 (dopasowanie), 08 (wnioski) i 09 (kalendarz), których nie ma w tej gałęzi
(`assignment/kuba-plans-05-06-10`): część 03 jest na gałęzi Piotrka, 08 i 09 nie są jeszcze zaimplementowane.
Dlatego zrobiono **wszystko, co niezależne**, a miejsca styku zostawiono jako czyste funkcje i testy kontraktu:

| Wymóg planu | Stan |
|---|---|
| `services/situations.py` (set/undo/exit/mode/serious_illness, idempotencja, okno 7 dni) | gotowe, przetestowane |
| Anulowanie szkiców / `child_loss_note` | gotowe na kolekcji `applications` (statusy `draft|needs_input|ready` → `cancelled`); po scaleniu planu 08 można zastąpić własnym `cancel_drafts_for_child` — ten sam kontrakt |
| Brak powiadomień dla drugiego rodzica | gotowe (nic nie zapisujemy w `notifications`), test |
| API + `GET /api/me/mode` | gotowe |
| Filtr dopasowania (`matching.py`) i `loss_support` | **do podpięcia:** silnik z gałęzi Piotrka już pomija dzieci z `situation == "loss"` i zna `family.child_serious_illness`; brakuje tylko filtra `loss_support_applies(benefit.tags, children)` oraz wczytania `data/benefits_loss.json` do seedu świadczeń (`Benefit` z `tags`) |
| Wyciszanie terminów (`calendar_gen.py`) | **do podpięcia:** `event_policy(children)` zwraca `skip`/`mute` per dziecko |
| `profil_rodziny` z `situation` | gotowe (w planie 06) + test |
| Frontend: `SituationMenu`, `JaskolkaHome`, `useFamilyMode`, zmiany w `AppShell` i `FamilyPage` | gotowe; sekcje zależne od planów 03/09 (`/api/benefits`, `/api/calendar`) znikają same, gdy endpoint nie istnieje |
| Task 4 — test całości | **częściowy:** `tests/test_e2e_nowak.py` pokrywa logowanie, rodzinę, czat, tryb jaskółki; kroki 03/04/07/08/09 opisuje test oznaczony `skip` z listą do dopisania |
| Task 5 — README, weryfikacja końcowa | README gotowe; `docker build` niewykonany (Docker niedostępny w środowisku) |

## Decyzje
- Pole `Child.situation_exited_at` (nowe): „Wróć do zwykłego widoku” kończy **tryb**, ale dziecko zostaje w
  sytuacji `loss` — jego świadczenia i przypomnienia nadal są ukryte. `family_mode` = jest dziecko w `loss` bez `situation_exited_at`.
- `ChildPatch` nie zawiera już `situation*` (zwykłe PATCH nie omija serwisu). `serious_illness` zostało w PATCH (bez skutków ubocznych).
- Pierwsze zgłoszenie wygrywa: drugie (nawet z innym `kind`) zwraca stan pierwszego. Blokada per rodzina (`asyncio.Lock`
  w procesie) — przy kilku replikach wymaga atomowej operacji w bazie (jak budżet tokenów w NOTES-02).
- Okno cofnięcia: `now <= situation_at + UNDO_WINDOW_DAYS`; potem 409 „Czas na cofnięcie zgłoszenia minął…”.
  `GET /api/me/mode` zwraca `undo_until: null` po upływie okna (tryb zostaje).
- Anulowane szkice mają status `cancelled` (+ `cancelled_reason`, `cancelled_at`); plan 08 powinien dopisać `cancelled` do enuma statusów.
- Sesje czatu i inne ekrany nie są dotykane; `AppShell` dostał kontekst trybu (`FamilyModeContext`) i podmienia stronę „/”
  na `JaskolkaHome` tylko w trybie (dashboard planu 03 zostaje bez zmian).
- `benefits_loss.json`: 4 pozycje z oficjalnych źródeł (ZUS, gov.pl, PIP), te same co w `/jaskolka`; kwoty bez liczb
  (`verify: true`, „sprawdź aktualną na stronie ZUS”).

## Niezweryfikowane
- Zachowanie po scaleniu z planami 03/08/09 (kształt `Application`, `Benefit`, `/api/calendar`).
- Ścieżka „drugi rodzic widzi tryb przy następnym wejściu” sprawdzona przez API (nie przeglądarką).
