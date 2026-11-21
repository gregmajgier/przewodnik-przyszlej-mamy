# /jaskolka (ścieżka publiczna) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Monochromatyczna, spokojna ścieżka bez logowania: wybór sytuacji → checklista uprawnień i dokumentów → baza fundacji. Link z landingu.

**Architecture:** Publiczne endpointy `/api/jaskolka/*` czytające JSON z `backend/app/data/jaskolka.json`; osobna, leniwie ładowana trasa `/jaskolka` we frontendzie z motywem `mono` (bez AppShell i bez wymagania sesji).

**Spec:** §13.1, §13.3, §2 (anty-cele). Konwencje: `00-conventions.md`. Zależy od 01.

## Global Constraints
- Bez logowania, bez ciasteczek śledzących, bez analityki. Żadnych kolorów akcentu (`data-theme="mono"`), żadnych animacji poza subtelnym fade; żadnych wykrzykników ani „gratulacji”.
- Sytuacje: `martwe-urodzenie`, `poronienie`, `wczesniak`, `ciezka-choroba` („Za życiem”), `smierc-dziecka`.
- Treść wnosi wsparcie bez zbędnych kroków; ton: spokojny, konkretny, z jednym zdaniem współczucia na początku.
- Fakty prawne z oficjalnych źródeł (ZUS, gov.pl, ustawy) z `source_url`; niepewne → `verify: true`.

## Review Focus
- Dostęp bez tokenu działa; z nieznanym `situation` → 404 po polsku.
- Strona czytelna na telefonie 360 px, nawigacja klawiaturą, kontrast AA, `prefers-reduced-motion`.
- Brak jakiegokolwiek wywołania API wymagającego sesji na tej trasie (test: żadne żądanie nie dostaje nagłówka Authorization).
- Pusta/nieznana fundacja w filtrze → komunikat, nie biały ekran.

---

### Task 1: Dane i API
**Files:** Create `backend/app/data/jaskolka.json`, `backend/app/routers/jaskolka.py`, `backend/tests/test_jaskolka.py`.
**Interfaces:** `GET /api/jaskolka/situations -> [{id,label,intro}]`; `GET /api/jaskolka/situations/{id} -> {id,label,intro,checklist:[{id,title,body,kind:"right"|"document"|"step",deadline_text|None,form_codes:[str],source_url,verify}]}`; `GET /api/jaskolka/foundations?situation=ID -> [{id,name,description,url,situations:[id],region|None}]`.
- [ ] Przygotuj treść dla 5 sytuacji z oficjalnych źródeł. Minimum: martwe urodzenie/poronienie (urlop macierzyński, zasiłek macierzyński, karta zgonu/akt urodzenia martwego dziecka, zasiłek pogrzebowy, prawo do pochówku, opieka psychologiczna), wcześniak (urlop/zasiłek, szpital, rehabilitacja), „Za życiem” (4000 zł, koordynator, opieka wytchnieniowa), śmierć dziecka (urlop okolicznościowy, zasiłek pogrzebowy). ≥15 fundacji/organizacji (np. fundacje wsparcia po stracie, wcześniaków, hospicja dziecięce) z działającymi URL.
- [ ] Testy: `test_situations_public_no_token`, `test_each_situation_has_checklist_and_source`, `test_unknown_situation_404`, `test_foundations_filter`, `test_all_foundation_urls_https`. Commit.

### Task 2: Frontend `/jaskolka`
**Files:** Create `frontend/src/features/jaskolka/{routes.tsx,JaskolkaPage.tsx,SituationPicker.tsx,Checklist.tsx,Foundations.tsx,jaskolka.css}`, testy.
**Interfaces:** Trasa `/jaskolka` **poza** AppShell i bez `RequireAuth` (`routes.tsx` eksportuje trasę z `lazy: () => import('./JaskolkaPage')`; sprawdź, że registry planu 01 pozwala trasom publicznym omijać shell — jeśli nie, dodaj flagę `handle: { public: true }` w minimalnej zmianie registry). `JaskolkaPage` ustawia `document.documentElement.dataset.theme = "mono"` przy montowaniu i przywraca przy odmontowaniu.
- [ ] UI: krok 1 wybór sytuacji (duże, spokojne przyciski), krok 2 checklista z odhaczaniem (stan w `sessionStorage`, nie na serwerze), sekcja fundacji; link „Wróć” zawsze widoczny; stały dyskretny link „Potrzebujesz porozmawiać? Telefon zaufania…” z numerem ogólnopolskim potwierdzonym w oficjalnym źródle.
- [ ] Testy: render bez sesji nie wywołuje `/api/me`; wybór sytuacji ładuje checklistę; odhaczenie zapisuje w sessionStorage; motyw mono ustawiony i przywrócony. Commit.

### Task 3: Link z landingu
**Files:** Modify `landing/src/App.tsx` (+ `App.css` w razie potrzeby).
- [ ] Dodaj spokojny, nierzucający się link w stopce/CTA: „Potrzebujesz wsparcia po stracie dziecka lub w trudnej sytuacji? →” prowadzący do `${VITE_APP_URL ?? 'http://localhost:5173'}/jaskolka`. Test: `npm run build` w `landing/` zielony. Commit `feat(landing): link to /jaskolka`.

### Task 4: Weryfikacja
- [ ] Testy backend + frontend + build landing/frontend zielone; wpis w `docs/dev.md`. Commit.
