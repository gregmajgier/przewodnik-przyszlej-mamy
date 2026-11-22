# NOTES-01 — decyzje i odstępstwa (plan 01 fundament)

## Git
- Worktree startował na commicie bez katalogu `docs/`; dokumenty planów zostały wciągnięte przez
  `git merge 8d075fc` (commit z planami z `dev`) do gałęzi roboczej. `main`/`dev` nietknięte.

## Rozszerzenia kontraktów (nie łamią 00-conventions)
- `app/errors.py`: `DomainError(status_code, detail)` — serwisy go rzucają, `create_app` zamienia na JSON
  `{"detail": ...}`. Kolejne plany mogą z tego korzystać.
- `current_principal` odświeża `family_id`/`unit_id` z bazy przy każdym żądaniu (token niesie tylko
  `user_id`/`role`), więc rodzina założona po zalogowaniu jest od razu widoczna. Użytkownik z `disabled: true`
  lub usunięty -> 401.
- `Settings`: `env` (`dev` domyślnie), `is_production` (= `env != dev` lub ustawiony `COSMOS_ENDPOINT`),
  `session_secret`, `session_ttl_hours`, `official_default_password`.
  Start poza dev odmawia słabego `SESSION_SECRET` (<32 znaki/domyślny); konta urzędników nie powstają bez
  własnego hasła (>=12 znaków); istniejące konta z hasłem `demo1234` są wyłączane (`disabled`).
- `Family` ma dodatkowe pole `invite_expires_at` (kod ważny 7 dni, nowy kod = `POST /api/families/me/invite-code`).
  Kod nie jest jednorazowy; limit to 2 rodziców (409 przy 3.). Kod jest normalizowany (trim, wielkie litery).
- Dodatkowy endpoint `GET /api/families/join-requests/mine` (status własnych próśb).
- `POST /api/families` zwraca `FamilyView` (201); `accept|reject` też zwracają `FamilyView`.
- `ParentProfile` w kolekcji `profiles` ma `id == user_id` (wymóg `Store.put`). `GET /api/profile` zwraca
  `{members: [ParentProfile + user_name]}`. Profil z ZUS powstaje tylko, jeśli nie istnieje (odpowiedzi
  `answers` nie są resetowane przy kolejnym logowaniu).
- `GET /api/profile/me/zus` zwraca testowy podgląd PUE (`simulated: true`, `verify: true` dla stawki 13,71%).
- Istniejący router `wnioski` (publiczny katalog wniosków) pozostał bez wymogu tokena — to dane niewrażliwe;
  reszta `/api/*` poza `auth` wymaga tokena.
- Frontend: oprócz `routes.tsx`/`nav.ts`/`widget.tsx` rejestr wykrywa `features/*/profile-section.tsx`
  (`{order, title, Component({userId,userName})}`) — sekcje w „Moje dane” (miejsce na plan 04; placeholder
  „Umowy o pracę” znika, gdy jakaś sekcja jest zarejestrowana). Trasy publiczne: `handle: { public: true }`.
- `SessionContext` jest eksportowany (do testów); `useSession()` dodatkowo zwraca `loading` i `loginOfficial`.
- Strona `/` do czasu dashboardu (plan 03) przekierowuje na `/rodzina` (lub `/start` bez rodziny); gdy któraś
  funkcja zdefiniuje trasę `/`, fallback znika.

## Niezweryfikowane
- `docker build backend` — Docker niedostępny w środowisku.
- Cosmos/Foundry: `CosmosStore` testowany wyłącznie atrapą bazy.
