# NOTES-03 — decyzje i odstępstwa (plan 03: świadczenia, dopasowanie, analiza, dashboard)

## Rozszerzenia kontraktów (nie łamią planu)
- `Criteria.allow_pregnancy` (nowe, opcjonalne): ciąża (dziecko w drodze lub aktywne e-ZLA „B”) spełnia też kryterium
  wieku dziecka — dla zasiłku macierzyńskiego, urlopów, „Za życiem”. Bez tego kryteria AND nie dałyby się wyrazić
  („w ciąży LUB dziecko do 11 mies.”).
- `Benefit.tags: list[str]` (plan 10 i tak go potrzebuje). Tag `per_child` = `annual_value_estimate` mnożone przez
  liczbę dzieci spełniających kryterium wieku (`MatchResult.eligible_children`, nowe pole).
- `build_context(family_view, profiles, today, units=None, viewer_id=None)` — dodatkowe argumenty: jednostki do
  wyliczenia `FamilyContext.unit_ids` (zasięg terytorialny) i rodzic, którego odpowiedzi mają pierwszeństwo.
  `FamilyContext.unit_ids` jest nowym polem (match nie ma dostępu do bazy).
- `next_deadline(benefit, ctx)` w `matching.py` — termin wyliczany z `Benefit.deadline` względem dzieci rodziny.
- Fakty dla warunków `auto` (`profile_key`): `family.pregnant`, `family.has_ezla_b`, `family.child_serious_illness`,
  `family.sickness_insurance`; inaczej bool z `ParentProfile.answers`.
- `GET /api/analysis` → `steps[{key,label,detail,status: done|warning}]` (klucze: `zus, contracts, catalog, results,
  deadlines`), `totals`, `estimated_annual_total`, `nearest_deadline {benefit_id,name,date,days_left}|null`.
  `GET /api/summary` → jak wyżej + `family_name`, `warnings[]`, `parameters_label` („Parametry ZUS {rok} – aktywne”).
  Zależność `get_today` (w `routers/benefits.py`) pozwala w testach ustawić „dziś”.
- Dochód: pytanie o dochód ma `condition_id = "income"` (odpowiedź tak/nie), albo globalny klucz
  `income_per_person` w `answers` (liczba jako tekst) porównywany z progiem.

## Decyzje
- Granice wieku: pełne ukończone miesiące, **obie granice włącznie**; „do 18 lat” = max 215 (w dniu 18. urodzin → `no`).
- Dziecko „w drodze” nie liczy się do wieku/liczby dzieci; komunikat „Dostępne po urodzeniu dziecka” (800+, KDR itd.).
  `min_children` liczy dzieci urodzone <18 lat oraz z niepełnosprawnością (KDR: do 25 lat przy nauce — nie modelujemy).
- Brak zaznaczonej niepełnosprawności/rodziny zastępczej w danych rodziny = `no` z podpowiedzią, gdzie to zmienić
  (nie `maybe` — inaczej każda rodzina widziałaby te świadczenia jako „może”).
- Dzieci z `situation == "loss"` są pomijane w dopasowaniu (plan 10 rozbuduje; nie koliduje).
- e-ZLA „B” liczy się jako ciąża tylko, gdy żadne dziecko nie urodziło się w ciągu ostatnich 270 dni.
- Świadczenia lokalne spoza obszaru rodziny nie trafiają na listę (`GET /api/benefits`), a silnik i tak zwraca `no`.
- Frontend: `features/dashboard/widgets.ts` czyta `features/*/widget.tsx` własnym `import.meta.glob`, nie z
  `registry.ts` (registry importuje trasy dashboardu → import cykliczny). Typy świadczeń są w
  `features/benefits/types.ts` (bez zmian w `lib/types.ts`).
- Pliki innych planów zmienione minimalnie: `OnboardingPage.tsx` (+test) kończy na `/analiza` zamiast `/`;
  `AppShell.tsx` — `end` dla linku „/” (inaczej „Start” byłby zawsze aktywny); `seed/__init__.py` (+1 import, +1 linia).
- Dashboard nie zawiera wyszukiwarki ani edycji stawek; stawki czyta z publicznego `GET /api/parametry`.
- Wygląd: tokeny z `theme.css`, pasy w kolorze akcentu z tekstem `--bg`, karty `1.5rem` z cieniem, pigułki,
  cele dotykowe ≥ 44 px, `prefers-reduced-motion` (analiza pokazuje wszystko od razu). Nagłówek aplikacji
  (AppShell, plan 01) nadal jest biały — to do planu 10 (polish).

## Do weryfikacji merytorycznej przez człowieka
Źródła pobrane 2026-11-21 ze stron ZUS, gov.pl (MRPiPS, MZ), podatki.gov.pl. Strony mają różne daty ostatniej
aktualizacji — sprawdź, czy kwoty są aktualne na dzień uruchomienia.
- `verify: true` w danych (9 rekordów): `nat-aktywny-rodzic-zlobek` (granica wieku: „do końca roku szkolnego, w
  którym dziecko kończy 3 lata” uproszczona do 47 mies.), `nat-urlop-rodzicielski` (granica 6 lat dziecka z Kodeksu
  pracy, nie z odczytanej strony), `nat-becikowe` (kryterium 1922 zł — „weryfikowane co 3 lata”),
  `nat-zasilek-rodzinny` (kwoty 95/124/135 zł i kryteria 674/764 zł ze strony gov.pl zmodyfikowanej 12.2023 —
  sprawdzić, czy okres 2026/2027 ich nie zmienił; tak samo dodatek 95 zł na III+ dziecko), `nat-leki-ciaza`
  (strona z 2020/2023), `nat-badania-prenatalne` (strona z 2017), `nat-swiadczenie-pielegnacyjne` (brak kwoty —
  celowo, nie znaleziono jej na stronie), `nat-zasilek-pielegnacyjny` (215,84 zł; strona z 01.2024),
  `nat-rodzina-zastepcza` (źródło: ISAP — adres niezweryfikowany przez przeglądarkę; brak kwot).
- Dobry Start: termin `2026-11-30` jest wpisany na stałe (rok szkolny 2026/2027) — trzeba aktualizować co rok.
- 800+: projekt automatycznego odnawiania (Rada Ministrów 20.10.2026) nie jest jeszcze prawem — opis mówi, że wniosek
  nadal się składa; sprawdzić przed publikacją.
- Aktywny rodzic „w pracy”: warunek aktywności zawodowej (≥100% minimalnego wynagrodzenia łącznie itd.) sprowadzony
  do pytania tak/nie; progi zależą od aktualnej płacy minimalnej.
- Wymiary urlopów (20/41 tyg., 2 tyg. ojcowski) i wysokości zasiłku (100/70/81,5%) — ze stron ZUS (data 2023–2026).
  Przy ciąży mnogiej tylko wzmianka; pełne wymiary w `zmienne_uzytkownika.json` (osobna uwaga o weryfikacji).
- Ulga prorodzinna: kwoty z podatki.gov.pl; limit dochodów przy jednym dziecku celowo bez liczb.
- Szacunki roczne (`annual_value_estimate`) są orientacyjne: zasiłek rodzinny 1140 zł/dziecko (konserwatywnie 95 zł ×
  12), ulga 1112 zł/dziecko (dla III dziecka byłoby 2000 zł). Aktywny rodzic i zasiłki zależne od podstawy nie
  mają szacunku (żeby nie sumować wykluczających się wariantów).

## Niezrealizowane / poza zakresem
- Świadczenia lokalne (Kraków/Małopolska) — plan 07 (Task 3). Test zasięgu używa rekordów tworzonych w testach.
- „Bon żłobkowy”: osobnej pozycji nie ma — dofinansowanie żłobka to „Aktywny rodzic — aktywnie w żłobku”
  (Aktywny Maluch to program dla podmiotów prowadzących żłobki, nie dla rodziców).
- Trasa `/wnioski/nowy?form=KOD` (przycisk „Złóż wniosek”) powstaje w planie 08.

## Niezweryfikowane
- UI nie był oglądany w przeglądarce (tylko testy jednostkowe, lint i build); układ i kontrast sprawdzić ręcznie.
- Wyszukiwarka sieciowa była niedostępna w trakcie pracy; źródła czytane bezpośrednio ze stron ZUS/gov.pl.
