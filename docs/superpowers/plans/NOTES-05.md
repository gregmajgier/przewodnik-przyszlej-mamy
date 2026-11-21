# NOTES-05 — /jaskolka (ścieżka publiczna)

## Decyzje i odstępstwa od planu
- **Trasa**: plan sugerował `lazy: () => import(...)` w `RouteObject`, ale `App` używa `<BrowserRouter>` + `useRoutes`,
  gdzie `lazy` nie działa (tylko data router). Użyto `React.lazy` + `Suspense` (`JaskolkaLazy.tsx`); build daje osobny chunk.
  Dwie trasy: `/jaskolka` (wybór) i `/jaskolka/:situationId` (checklista + fundacje), obie `handle: { public: true }`.
- **Brak tokenu**: `jaskolkaApi.ts` używa gołego `fetch` (`credentials: 'omit'`), nie `lib/api.ts`. Dodatkowo minimalna zmiana w
  `lib/session.tsx` (plan 01): `SessionProvider` nie odtwarza sesji (`/api/me`), gdy ścieżka zaczyna się od `/jaskolka`
  — inaczej zapisany token wyciekałby w nagłówku `Authorization`. Link „Wróć do mRodziny” to zwykłe `<a href="/">`
  (pełne przeładowanie → sesja wraca).
- **Motyw**: `data-theme="mono"` ustawiany na `<html>` w `useEffect`, po wyjściu przywracany poprzedni (lub usuwany).
- **Marka** (wg sekcji Branding): ten sam krój (Nunito 800 w nagłówkach, Sniglet tylko we wordmarku), pigułki 999px, karty 1.5rem
  z cieniem `0 6px 24px rgb(25 25 25 / 0.08)`, logo + „Rodzina” w pasie nagłówka (kolor główny motywu mono, tekst `--bg`).
  Wyłącznie tokeny z `theme.css`; test pilnuje braku kolorów hex w komponentach i `jaskolka.css`.
- **Koordynator** („Za życiem”): plan wspominał koordynatora; w źródłach oficjalnych (informator MZ, MRPiPS) nie znalazłem
  potwierdzenia takiej roli, więc w danych jest **asystent rodziny** i „koordynowana opieka” tylko tam, gdzie źródło tak mówi.
- Stały link na dole strony: telefon wsparcia **116 123** (całodobowo, bezpłatnie) + 112; źródło: strona MZ
  „Gdzie uzyskać pomoc psychologiczną i psychiatryczną”, która podaje także 800 70 2222 (Centrum Wsparcia, Fundacja ITAKA).
- Filtr regionu fundacji: organizacje bez regionu (ogólnopolskie) są zawsze widoczne.
- Landing: link w nowej stopce (`site-footer`/`support-link`), obrys-pigułka w tokenach landingu, bez wypełnienia akcentem.
- Dane: 5 sytuacji, 34 pozycje checklisty, 19 organizacji (`backend/app/data/jaskolka.json`). Dane są generowane ręcznie z
  oficjalnych stron (zus.pl, gov.pl, pacjent.gov.pl, bip.brpo.gov.pl, pip.gov.pl); każdy adres sprawdzony (HTTP 200) w dniu implementacji.

## Do weryfikacji przez człowieka (pozycje z `verify: true` i inne)
- **Kwota zasiłku pogrzebowego**: strona ZUS w dniu implementacji podaje **7000 zł** (plan i część serwisów: 4000 zł). Treść mówi
  „według strony ZUS”, ale kwota bywa zmieniana — sprawdzić aktualną.
- **Zasiłek pogrzebowy po dziecku**: czy rodzic ubezpieczony ma prawo (ZUS: „członek rodziny” osoby ubezpieczonej) — sformułowane ostrożnie.
- **Dwa dni zwolnienia okolicznościowego** (§ 15 pkt 1 rozporządzenia z 15.05.1996): źródłem jest strona PIP (otwiera się u mnie
  za weryfikacją „nie jestem robotem”, treść potwierdziły wyniki wyszukiwania); ISAP nie był dostępny automatycznie. Nie wiadomo
  pewnie, czy dotyczy dziecka urodzonego martwo (pozycja „Drugi rodzic” ma `verify: true`).
- **Prawo do pochówku** (karta zgonu, niezależnie od wieku i płci): opinia Biura Rady Ministrów/RPO z 2024 r.; sprawdzić aktualne
  przepisy o cmentarzach oraz procedurę wydania ciała w szpitalu.
- **Uzupełniający urlop macierzyński**: wymiary z ZUS; szczegóły wniosku (21 dni przed końcem urlopu dla pracowników) nie są w treści —
  tylko „przed zakończeniem urlopu macierzyńskiego”. Sprawdzić formularze (`URLOP-UZUP`, `ZAM`, `Z-3`).
- **Asystent rodziny po stracie ciąży/martwym urodzeniu**: informator MZ wymienia te kobiety wśród uprawnionych do wsparcia z ustawy
  „Za życiem”; zakres praktyczny zależy od gminy.
- **Opieka wytchnieniowa 120 h**: zapis z informatora MZ; NIK wskazywał braki we wdrożeniu — dostępność lokalna.
- **Opisy organizacji**: pisane na podstawie ich stron głównych; Fundacja Ernesta i Fundacja „Zdążyć z Pomocą” opisane ogólnie
  (strony nie podają jasnego opisu w pierwszym ekranie), Panda Team, hospicja — wg opisów na stronach. Hospicjum „Formuła Dobra”
  nie ma na stronie głównej wzmianki o grupie wsparcia po stracie (informacja z komunikatu miasta Wrocławia nie weszła do danych).
  Sprawdzić aktualną ofertę każdej organizacji i zgodę na umieszczenie w bazie.
- **Telefony**: 116 123, 800 70 2222, 116 111 — potwierdzone na stronach MZ/MC; godziny 116 123 różnią się w starszych źródłach (nowsze: całodobowo).
- **Nie dodano** (brak oficjalnego źródła w czasie pracy): zawiadamianie ZUS/gminy o zakończeniu świadczeń na dziecko po jego śmierci,
  urlop ojcowski/rodzicielski po stracie dziecka, rehabilitacja wcześniaków w NFZ, strona Koalicji dla Wcześniaka i Fundacji Medycyny
  Prenatalnej im. Ernesta Wójcickiego pod własnym adresem (strona `fundacjaernesta.pl` jest jej domeną wg komunikatów, nie potwierdzone wprost).
- `zazyciem.gov.pl` (wskazany w informatorze MZ) nie rozwiązuje się w DNS — pominięty.
- Fonty ładowane z Google Fonts (jak w całym froncie) — to jedyny zewnętrzny zasób strony; do rozważenia hostowanie lokalne, jeśli
  „bez śledzenia” ma obejmować i to.
