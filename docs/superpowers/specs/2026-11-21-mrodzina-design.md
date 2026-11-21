# mRodzina — specyfikacja produktu

Data: 2026-11-21 · Status: szkic do akceptacji
Źródła: `materialy/Przewodnik Mam.md` (features dump, diagramy, ekrany), `landing/docs/vision.md`, rozmowa z zespołem.

Oznaczenia zakresu: **[P]** — buduje się w prototypie, **[W]** — wizja produktu (opisane, nie budowane teraz, do pokazania w prezentacji).

---

## 1. Po co to jest

Rodzic w Polsce, który spodziewa się dziecka, staje przed rozproszonym systemem: ZUS, pracodawca, gmina, USC, województwo, programy krajowe i lokalne, każdy z własnymi formularzami, terminami i kanałami. Łatwo przegapić świadczenie albo termin (np. 21 dni na wniosek o urlop, 3 miesiące na 800+ z wyrównaniem) i stracić pieniądze.

**mRodzina** to jedno miejsce, które:
1. zna rodzinę (dane z ZUS/mObywatela, umowy, krótki formularz),
2. mówi, co rodzinie przysługuje i dlaczego — z pełną przejrzystością,
3. wypełnia i wysyła wnioski za rodzica,
4. pilnuje terminów i statusów przez lata — od ciąży do 18. roku życia dziecka.

Osobno, bez logowania: **`/jaskolka`** — spokojna ścieżka dla rodziców w sytuacji straty lub ciężkiej choroby dziecka.

## 2. Cele, nie-cele, anty-cele

**Cele**
- Rodzic po onboardingu widzi konkretne świadczenia dla swojej rodziny z wyjaśnieniem dopasowania.
- Rodzic nie wpisuje danych, które system już ma.
- Wnioski są wstępnie wypełnione; rodzic tylko uzupełnia braki i zatwierdza.
- Gminy i województwa same publikują lokalne świadczenia, które trafiają do dopasowania.
- Rodzina (dwoje rodziców, osobne konta) dzieli wspólny obraz sytuacji.

**Nie-cele (teraz)**
- Panel admina ZUS i strona `/demo` dla jurorów — pominięte świadomą decyzją zespołu (mimo że materiały cytują polecenie wymagające edycji parametrów). Parametry ZUS żyją w bazie jako dane seedowane (`parametry_admin`), bez UI edycji; struktura ma pozwolić dodać panel później.
- Kalkulator — **zaparkowany** (patrz §12), buduje go inna osoba.
- Powiadomienia e-mail/SMS — **[W]**.
- Integracja z prawdziwymi eZUS / Emp@tia / ePUAP / mObywatel — symulowane.
- Aplikacja mobilna natywna.

**Anty-cele (porażka, nawet jeśli technicznie działa)**
- Aplikacja po stracie dziecka przypomina o 800+, PESEL-u lub gratuluje.
- Rodzic jest pytany o to, co system już wie.
- Rekomendacja bez wyjaśnienia „dlaczego” albo ukrywanie świadczeń, które nie pasują.
- Czytanie poczty rodzica poza wątkami wniosków.
- Wymuszanie logowania na rodzicu w kryzysie.

## 3. Użytkownicy i konta

### 3.1 Rodzic [P]
- Logowanie: **symulowany mObywatel** (wybór persony). Każdy rodzic ma **osobne konto**.
- Pierwszy rodzic tworzy **rodzinę** i dodaje dzieci (w tym „dziecko w drodze”).
- **Rodzic samotnie wychowujący** to pełnoprawny przypadek, nie „niekompletna rodzina”.

### 3.2 Dołączanie drugiego rodzica [P]
1. Założyciel rodziny generuje **kod zaproszenia** w ustawieniach rodziny.
2. Drugi rodzic (po własnym logowaniu) wybiera „Dołącz do rodziny” i wpisuje kod.
3. Założyciel dostaje prośbę i ją **akceptuje** (lub odrzuca). Dopiero po akceptacji drugi rodzic jest członkiem.
- Po dołączeniu **oboje widzą wszystko**: dane obojga, dzieci, umowy, dochody — bo wiele wniosków liczy dochód na członka rodziny.
- Każdy rodzic może składać wnioski; **wnioskodawcą jest zalogowany rodzic**, dane drugiego rodzica i dzieci wypełniają się z profilu. W kalendarzu widać, kto co złożył.
- *Decyzja buildera:* ważność kodu, jednorazowość, limit członków (rozsądnie: 2 rodziców).

### 3.3 Urzędnik gminy / powiatu / województwa [P]
- Konto **nadawane przez nas** (brak samorejestracji), logowanie e-mail + hasło.
- Każde konto przypisane do **jednej jednostki** (gmina, powiat lub województwo).
- Świadczenie jednostki widzą rodzice z jej obszaru (województwo → wszystkie jego gminy).

## 4. Cykl życia rodziny

- Rodzic przychodzi **w ciąży**. Pierwsze dziecko może istnieć jako **„dziecko w drodze”** z przewidywaną datą porodu → kalendarz od razu liczy terminy przedporodowe.
- Po porodzie rodzic uzupełnia dane dziecka (PESEL, akt urodzenia) — wniosek o akt urodzenia też przechodzi przez aplikację.
- **Każde dziecko ma własną oś czasu do 18 lat**; świadczenia pojawiają się i wygasają z wiekiem (np. Aktywny rodzic, 800+, KDR przy 3+).
- Zmiana sytuacji rodziny (narodziny trzeciego dziecka) automatycznie odblokowuje nowe świadczenia (np. Karta Dużej Rodziny).

## 5. Dane rodzica — profil „Moje dane”

Jeden **szyfrowany profil** na rodzinę, zasilany z trzech źródeł:

### 5.1 Symulowany mObywatel / ZUS [P]
Pobierany przy logowaniu dla wybranej persony:
- tożsamość, adres (→ gmina, województwo),
- tytuł ubezpieczenia (umowa o pracę / zlecenie / JDG), płatnik, podstawa wymiaru składek,
- **e-ZLA** z kodem „B” (zwolnienie w ciąży) → trafia na oś czasu (zasiłek chorobowy 100%),
- **stan zadłużenia składkowego** (JDG) → ostrzeżenie o ryzyku utraty prawa do zasiłku,
- **PUE/eZUS**: podgląd konta w „Moich danych”.

Symulacja jest modułem backendu za jednym interfejsem, żeby dało się ją podmienić na prawdziwe źródło.

### 5.2 Skan umów o pracę (AI) [P]
- Rodzic może wgrać **kilka umów** (np. etat + zlecenie).
- Model na **Azure AI Foundry** wyciąga: rodzaj umowy, pracodawcę (dane do wniosku o urlop), wymiar etatu, wynagrodzenie, datę zatrudnienia, okres trwania (określony/nieokreślony), stanowisko.
- Rodzic **widzi i zatwierdza** wyciągnięte dane przed zapisem do profilu.
- Dwa cele: **uzupełnienie profilu** oraz **ostrzeżenia o ryzyku**, np.:
  - umowa na czas określony kończy się przed porodem (przedłużenie do dnia porodu — informacja),
  - zlecenie bez dobrowolnego chorobowego → brak zasiłku macierzyńskiego,
  - zadłużenie JDG.

### 5.3 Formularz [P]
- Pyta **tylko o brakujące dane**, które **zmieniają wynik dopasowania**: m.in. gmina (jeśli niepewna), liczba i wiek dzieci, rodzina zastępcza/adopcja, niepełnosprawność dziecka, dochody nieujęte w ZUS.
- Od ogólnych do szczegółowych. Resztę dopytujemy później, przy konkretnym wniosku.
- Odpowiedzi na pytania tak/nie z dopasowywania świadczeń (§7.3) też zapisują się w profilu.

### 5.4 Persona prototypu [P]
**Rodzina Nowaków, Kraków (Małopolska)**
- **Mama**: umowa o pracę na czas nieokreślony, pełny etat, w ciąży z trzecim dzieckiem, e-ZLA z kodem B.
- **Tata**: umowa o pracę u innego pracodawcy; dołącza do rodziny kodem.
- **Dzieci**: 7 lat (szkoła), 3 lata (przedszkole), dziecko w drodze — termin ok. 2 miesiące od „dziś”.

Pokazuje: ścieżkę ciążową, wnioski do pracodawcy, 800+, odblokowanie KDR po porodzie, świadczenia zależne od wieku, lokalne świadczenia Krakowa/Małopolski.
*Decyzja buildera:* konkretne kwoty, nazwy pracodawców, daty względne do dnia uruchomienia.

Decyzja zespołu: **jedyna persona to rodzina Nowaków**, dane wymyślone przez nas (bez zewnętrznych zestawów spraw). Moja decyzja: logika wszystkich gałęzi (zlecenie/JDG → od razu ZAM, ostrzeżenia o zadłużeniu i braku chorobowego, rodzic samotnie wychowujący) jest **budowana zgodnie ze specem**, ale w prototypie **seedujemy tylko Nowaków**. Moduł symulacji przyjmuje persony jako dane, więc kolejne dodaje się bez zmian w kodzie.

## 6. Onboarding i „analiza” [P]

1. Logowanie (persona mObywatel) → pobranie danych ZUS.
2. Skan umów (opcjonalny) i/lub krótki formularz z brakującymi danymi.
3. **Ekran analizy** — animowany „loading”, który pokazuje **prawdziwą pracę** dopasowywania, krok po kroku:

```
  Poznajemy waszą rodzinę...
  ✓ Dane z ZUS: umowa o pracę, podstawa 7 850 zł
  ✓ Umowy: 1
  ⟳ Przeglądamy świadczenia: 38 krajowych, 11 z Krakowa i Małopolski
  ✓ Pasuje do was: 7 · może przysługiwać: 3
  ⚠ 1 termin w ciągu 30 dni
```

   Liczby pochodzą z faktycznego wyniku silnika (bez zmyślonych wartości); opóźnienie jest tylko prezentacyjne.
4. Dashboard z podsumowaniem: ile świadczeń, orientacyjnie ile zł rocznie, najbliższy termin.

## 7. Świadczenia i dopasowanie

### 7.1 Katalog [P]
Jeden katalog: **krajowe** (lista świadczeń z kryteriami strukturalnymi **przygotowana przez nas** z oficjalnych źródeł — ZUS, gov.pl, MRPiPS, ustawy — z linkiem do źródła przy każdym świadczeniu i powiązaniem z formularzami z `backend/app/data/katalog_wnioskow_pdf.json`; do weryfikacji merytorycznej przez zespół) + **lokalne** (z panelu jednostek) + **benefity spoza świadczeń** (np. Karta Dużej Rodziny, zniżki lokalne).

Na dashboardzie stawki pokazywane z bazy z oznaczeniem *„Parametry ZUS 2026 – aktywne”*.

### 7.2 Panel jednostki samorządu [P]
Urzędnik dodaje świadczenie / program / wsparcie:
- **Kryteria strukturalne** (sprawdzane kodem): wiek dziecka od–do, maks. dochód na osobę, min. liczba dzieci, zamieszkanie na obszarze jednostki, niepełnosprawność, rodzina zastępcza, itp.
- **Opis, kwota, termin, sposób złożenia** (kanał, link, PDF).
- **Pole „Dodatkowe wymogi”** (tekst wolny). Przy zapisie LLM zamienia je na listę **konkretnych warunków** (np. „zameldowanie w gminie ≥ 12 mies.”). Urzędnik **zatwierdza listę** przed publikacją.
- Wspomaganie [P/W — decyzja buildera]: wklejenie tekstu uchwały → AI wstępnie wypełnia kryteria strukturalne do zatwierdzenia.

### 7.3 Dopasowanie u rodzica [P]
- Kryteria strukturalne → kod (deterministycznie, z wyjaśnieniem: „pasuje, bo dziecko ma 3 lata i mieszkasz w Krakowie”).
- Warunki z „dodatkowych wymogów”: te, które da się sprawdzić na profilu, sprawdzane automatycznie; pozostałe → status **„może ci przysługiwać”** + pytanie tak/nie. Odpowiedź zapisuje się w profilu.
- LLM pracuje **raz, przy publikacji świadczenia**, nie przy każdym rodzicu.
- Statusy: **pasuje** / **może przysługiwać** / **nie pasuje (z powodem)**. Niepasujące są widoczne (przejrzystość), ale nie zaśmiecają widoku głównego.
- Dopasowanie przelicza się przy zmianie profilu (nowe dziecko, wiek, umowa).

## 8. Wnioski

### 8.1 Kanały (zgodnie z katalogiem)
| Odbiorca | Przykłady | Kanał w mRodzinie |
|---|---|---|
| Pracodawca | URLOP-MAC-ROD, URLOP-ROD, URLOP-OJC, URLOP-UZUP | PDF generowany przez aplikację → **e-mail ze skrzynki rodzica** (w prototypie symulowanej, §9) [P] |
| ZUS | ZAM, ZAS-53, ZAS-55, ZAS-26, ZAS-33 | **Agent w makiecie eZUS** [P]; PDF do pobrania jako alternatywa |
| ZUS (tylko online) | 800+, Aktywny rodzic | Agent w makiecie eZUS/Emp@tii [P] |
| Gmina | KDR, „Za życiem” | Agent w makiecie Emp@tii [P] lub PDF z instrukcją |
| USC | odpis / zgłoszenie urodzenia | symulacja [P] |

Podpis przez gov (Profil Zaufany) — **symulowany krok** w flow PDF [P]; prawdziwy podpis [W].

### 8.2 Flow wniosku [P]
1. Wybór wniosku (z rekomendacji świadczenia lub z listy).
2. Rozgałęzienie wg formy zatrudnienia (z diagramu 3): pracownik → najpierw wniosek o urlop do pracodawcy; zlecenie/JDG → od razu ZAM.
3. **Brakujące dane**: AI dopytuje tylko o to, czego nie ma w profilu; odpowiedzi zapisują się w profilu.
4. Wypełnienie:
   - **PDF**: AcroForm (wersje „wypełnij i wydrukuj”) lub PDF generowany dla wniosków do pracodawcy (wzór wg rozporządzenia MRPiPS, Dz.U. 2025 poz. 322).
   - **Online**: agent (§8.3).
5. Podgląd i **zatwierdzenie przez rodzica** przed wysyłką — zawsze.
6. Wysyłka → wpis w kalendarzu i śledzenie statusu (§9).

### 8.3 Agent w iframe [P]
- Makiety formularzy eZUS / Emp@tii serwowane **z naszej domeny**, osadzone w iframe.
- LLM w backendzie przygotowuje **plan wypełnienia** (pole → wartość, z profilu).
- Frontend wykonuje plan na oczach rodzica: widoczny kursor/podświetlenie, pole po polu; **zatrzymuje się** przy brakujących danych (pyta rodzica) i **przed wysłaniem** (zatwierdzenie).
- Rodzic może w każdej chwili przejąć i edytować pole ręcznie.
- **[W]**: agent na prawdziwym Playwright w kontenerze, docelowo na prawdziwych systemach.

## 9. Poczta i statusy wniosków [P]

- Prototyp: **połączenie z pocztą jest symulowane i domyślnie aktywne** — rodzina Nowaków ma od początku podłączoną symulowaną skrzynkę z predefiniowanymi danymi (bez ekranu zgody, bez prawdziwego OAuth i prawdziwych maili). W ustawieniach widać „Gmail podłączony” z informacją, co czytamy.
- Wysyłka wniosku do pracodawcy „z poczty rodzica” trafia do folderu „Wysłane” symulowanej skrzynki; odpowiedzi (pracodawca, ZUS, gmina) są predefiniowanymi wiadomościami, które pojawiają się po wysyłce (np. z opóźnieniem lub przyciskiem symulacji).
- Skrzynka jest modułem za jednym interfejsem (`MailProvider`), żeby można było podpiąć prawdziwy Gmail/Outlook bez zmian w reszcie.
- **[W]**: prawdziwe Gmail (OAuth, weryfikacja aplikacji Google) i Outlook (Microsoft Graph), podłączanie dowolnej skrzynki rodzica.
- Ustawienia poczty jasno mówią: czytamy **tylko** maile w sprawie wysłanych wniosków, i tylko po dacie wysyłki.
- Każdy wysłany wniosek zapisuje **adres odbiorcy i identyfikator wątku**.
- Filtr (moja decyzja, bo sama domena przy gmail.com/onet.pl czytałaby prywatną pocztę): odpowiedzi w **wątku wniosku** + maile z **dokładnego adresu odbiorcy**; filtr po **całej domenie tylko dla domen instytucjonalnych** (zus.pl, gov.pl, domeny urzędów z katalogu), nigdy dla publicznych dostawców poczty. Symulowana skrzynka zawiera też maile niezwiązane, żeby było widać, że filtr je pomija.
- Backend **cyklicznie** sprawdza skrzynkę (logika jak dla prawdziwej poczty).
- **LLM naprawdę klasyfikuje** znaleziony mail → proponowany status: *otrzymano*, *wezwanie do uzupełnienia*, *decyzja pozytywna*, *odmowa*, *inne*.
  - wysoka pewność → status zmienia się automatycznie + powiadomienie w aplikacji,
  - niska pewność → „Nowa wiadomość w sprawie wniosku X — sprawdź”.
- Widok **„Poczta ZUS / urzędy”** w aplikacji: tylko te wątki.
- *Decyzja buildera:* próg pewności, częstotliwość, treść predefiniowanych maili.

## 10. Kalendarz i ostrzeżenia [P]

- Wpisy: terminy (do kiedy złożyć, jak długo trwa efekt), złożone wnioski (kto, kiedy, gdzie, status), zdarzenia z osi dziecka.
- Wpis można **odkliknąć** (zrobione); każdy ma krótkie, przyjazne podsumowanie.
- **Ostrzeżenia**: zagrożenie utraty świadczenia (zbliżający się termin), zmiana stawek lub wymiaru, ryzyka z umów/ZUS (§5.2).
- Prototyp: ostrzeżenia **tylko w aplikacji** (dashboard + kalendarz).
- **[W]**: powiadomienia **e-mail + SMS** do rodzica przed terminem.

## 11. Dashboard (hub rodzica) [P]

Moduły: czat „Zapytaj mRodzinę” (§11a), świadczenia (rekomendacje + „może przysługiwać” + pozostałe), wnioski, kalendarz, poczta, moje dane, wsparcie (link do `/jaskolka`), kalkulator (miejsce zarezerwowane, §12).
Na górze: podsumowanie (liczba świadczeń, szac. kwota roczna, najbliższy termin, ostrzeżenia).

## 11a. Czat „Zapytaj mRodzinę” [P — działający]

Rodzic rozmawia z asystentem, który zna **przepisy**, **dane rodziny** i **aktualne informacje lokalne**. Przykładowe pytania: „Jak działa urlop macierzyński?”, „Jak zapisać dziecko do szkoły podstawowej / przedszkola / żłobka?”, „Co mi przysługuje, gdy wrócę do pracy?”.

**Architektura (podejście A — wybrane):** rozmowę prowadzi nasz backend (FastAPI) z modelem z **Azure AI Foundry**; narzędzia model dostaje przez **nasz serwer MCP** działający w backendzie (backend jest klientem MCP). Dane rodzica nie opuszczają backendu.
- Odrzucone: **B. Agent w Foundry Agent Service** wołający nasz publiczny serwer MCP — wymaga bezpiecznego przekazywania tożsamości rodzica do publicznego endpointu z danymi rodziny i rozdziela limity na dwa miejsca.

**Narzędzia MCP**
- `profil_rodziny` — dane rodziny, dzieci i ich wiek, zatrudnienie (zalogowanego rodzica i rodziny).
- `swiadczenia` — katalog + wynik dopasowania dla tej rodziny (§7).
- `kalendarz` — terminy i statusy wniosków (§10).
- `szukaj_w_przepisach` — wyszukiwanie w indeksie wybranych aktów prawnych (Azure AI Search), zwraca artykuły z linkiem.
- `szukaj_w_sieci` — web search dla informacji lokalnych i bieżących (np. terminy rekrutacji do przedszkoli w Krakowie, oferta powiatowego urzędu pracy: bon żłobkowy, staże, wsparcie powrotu do pracy). Wyniki **preferują domeny urzędowe** (gov.pl, bip, strony gmin, PUP, zus.pl). Dzięki temu gmina nie musi publikować tych informacji w panelu.

**Baza przepisów** (wybrane akty, pobierane z oficjalnego API Sejmu — ELI, dzielone na artykuły): Kodeks pracy (dział VIII — uprawnienia związane z rodzicielstwem), ustawa zasiłkowa, ustawa o świadczeniach rodzinnych, ustawa o pomocy państwa w wychowywaniu dzieci (800+), Prawo oświatowe (rekrutacja), ustawa o opiece nad dziećmi do lat 3, ustawa „Za życiem”, ustawa o Karcie Dużej Rodziny. *Decyzja buildera:* dokładna lista, sposób dzielenia i odświeżania.

**Zasady odpowiedzi**
- Każda odpowiedź oparta na przepisach **cytuje artykuł i podaje link** do źródła; informacje z sieci — link do strony.
- Brak podstawy → „nie wiem” + wskazanie, gdzie zapytać (urząd, ZUS, PUP). Bez zgadywania kwot i terminów.
- Odpowiedzi personalizowane danymi rodziny („Twoja córka ma 3 lata, więc…”), ale czat **nie składa wniosków sam** — może podlinkować flow wniosku (§8).
- W trybie jaskółki czat zna sytuację rodziny i nie proponuje świadczeń związanych z utraconym dzieckiem.
- Historia rozmów zapisywana per rodzic (szyfrowana).

*Decyzja buildera:* dostawca web search (uwaga: klasyczne Bing Search API zostało wycofane — rozważyć Grounding with Bing w Foundry lub zewnętrzne API wyszukiwania), model, streaming odpowiedzi.

## 12. Kalkulator — ZAPARKOWANY

Buduje inna osoba z zespołu. Otwarte pytanie: **wspólny planer urlopu rodziny** (podział rodzicielskiego między rodziców, warianty 81,5% vs 100/70, łączenie z pracą → z planu powstają wnioski obojga i terminy) czy **osobny kalkulator każdego rodzica**.
Kontrakt na teraz: kalkulator korzysta z profilu (podstawy wymiaru obojga, dzieci) i parametrów ZUS z bazy (`parametry_admin`); wynik ma się dać „zapisać jako wariant”, z którego flow wniosków (§8.2) startuje. Szczegóły po rozmowie z autorem kalkulatora.

## 13. `/jaskolka` i tryb jaskółki

### 13.1 `/jaskolka` bez logowania [P]
- Jeden klik z landingu, link także z dashboardu. **Monochromatyczna, neutralna**, bez zbędnych kroków.
- Wybór sytuacji: martwe urodzenie, poronienie, wcześniak i hospitalizacja, ciężka choroba („Za życiem”), śmierć dziecka.
- Checklista: uprawnienia i dokumenty (urlop macierzyński po stracie, zasiłek macierzyński, zasiłek pogrzebowy, akt urodzenia martwego dziecka, urlop okolicznościowy drugiego rodzica, …).
- Baza **fundacji** i organizacji wsparcia.

### 13.2 Tryb jaskółki w koncie [P]
- **Każde z rodziców** może zgłosić stratę: spokojna, niewyróżniona opcja „Zmiana sytuacji” na karcie dziecka; wybór z tej samej listy. Bez pól, bez uzasadnień, bez „czy na pewno?”. **Cofnięcie możliwe przez kilka dni** (pomyłka).
- Od razu, u obojga:
  - znikają przypomnienia, świadczenia i teksty dotyczące tego dziecka (800+, PESEL, „gratulacje”, plan urlopu),
  - szkice wniosków dla tego dziecka anulowane po cichu; wnioski już wysłane oznaczone (rodzic wie, co np. dostał pracodawca),
  - drugi rodzic **nie dostaje powiadomienia** — przy następnym wejściu widzi ten sam tryb.
- Aplikacja przechodzi w **monochromatyczny tryb** z jedną listą dla tej sytuacji; wnioski **wstępnie wypełnione z profilu**.
- Nie usuwamy dziecka bez decyzji rodzica (imię zostaje). Nie wychodzimy z trybu automatycznie — rodzic wychodzi sam, jedną spokojną opcją.
- Inne dzieci nie znikają; ich krytyczne terminy wyświetlane wyciszone, w tym samym stylu.

### 13.3 Ciężka choroba („Za życiem”) [P]
Oznaczenie na karcie dziecka, które dodaje właściwe świadczenia (4000 zł, wsparcie) — **bez** przełączania w tryb jaskółki.

## 14. Wymagania niefunkcjonalne

- **Szyfrowanie** (moja propozycja): szyfrowanie at-rest Cosmos DB i magazynu plików + dodatkowe szyfrowanie pól najwrażliwszych (PESEL, zarobki, skany umów, tokeny dostępu do poczty [W]).
- **Limity zapytań (strona publiczna, płatne modele)** — trzy poziomy dla wszystkich funkcji AI (czat, skan umów, plan agenta, klasyfikacja poczty, ekstrakcja „dodatkowych wymogów”):
  1. limit na użytkownika i na adres IP (okno minutowe i dzienne),
  2. **dzienny budżet tokenów** na całą aplikację — po przekroczeniu funkcje AI odpowiadają łagodnym komunikatem („spróbuj jutro”), reszta aplikacji działa,
  3. twardy limit przepustowości (TPM) ustawiony na wdrożeniu modelu w Foundry jako ostatnia bariera.
  Dodatkowo: limit długości wiadomości i historii w czacie, limit rozmiaru i liczby skanów. *Decyzja buildera:* konkretne wartości.
- **AI**: Azure AI Foundry, tanie modele OpenAI w prototypie. **[W]**: model on-premise do ekstrakcji i wypełniania.
- **Przejrzystość**: każda rekomendacja i każdy automatyczny status ma widoczne „dlaczego”.
- **Źródła**: kalkulator i świadczenia powołują się na oficjalne źródła (linki z katalogu).
- **Wygląd**: kolor główny `#EF4363`, tło `#f8fbef`, tekst `#191919`, Nunito (treść), Sniglet (tylko wordmark). `/jaskolka` i tryb jaskółki — monochromatyczne. Elementy AI/symulacji oznaczone osobnym kolorem (z legendy w materiałach).
- Język interfejsu: polski.

## 15. Architektura (podejście A — wybrane)

**Rozważone podejścia**
- **A. Jedna aplikacja, symulacje w backendzie, agent w przeglądarce** — *wybrane*. Najmniej ruchomych części, płynny efekt agenta; agent nie steruje prawdziwą przeglądarką (przebudowa przy realnym eZUS).
- **B. Jak A + prawdziwy Playwright w kontenerze** ze streamingiem obrazu — odrzucone na teraz: ciężki kontener, wolniej i bardziej zawodnie, a wypełniamy własną makietę. Zostaje jako [W].
- **C. Osobne aplikacje** (rodzic / gmina / jaskółka) — odrzucone: trzy wdrożenia i duplikacja; podział zespołowy da się zrobić katalogami w jednej aplikacji.

**Kształt**
- `frontend/` — jedna aplikacja React (Vite, TS) z obszarami: aplikacja rodzica, panel jednostki samorządu, `/jaskolka` (ładowana osobno, bez logowania, własny motyw), makiety eZUS/Emp@tii (dla iframe).
- `backend/` — FastAPI: auth (persona mObywatel, konta urzędników), rodzina i zaproszenia, profil, ekstrakcja umów, katalog i silnik dopasowania, wnioski (PDF + plan agenta), poczta (symulowana skrzynka za interfejsem `MailProvider` + polling + klasyfikacja LLM), kalendarz, czat (klient MCP + serwer MCP z narzędziami §11a, indeks przepisów w Azure AI Search, web search), limity zapytań, moduł symulacji ZUS/mObywatel.
- **Cosmos DB** — dane; **AI Foundry** — modele; hosting jak obecnie (SWA dla frontu, Container App dla backendu).
- Landing (`landing/`) już istnieje i linkuje do frontendu; CTA do `/jaskolka` dodać.

## 16. Zostawione builderowi

- Model danych i podział na kontenery Cosmos, schemat API.
- Mechanizm sesji/auth (dla persony i urzędników).
- Magazyn plików (skany, wygenerowane PDF).
- Seed świadczeń krajowych i przykładowych lokalnych dla Krakowa/Małopolski.
- Treść checklist `/jaskolka` i lista fundacji (do weryfikacji merytorycznej).
- Dobór modeli i promptów; progi pewności.
- Dokładny wygląd ekranów w ramach brand tokens.

## 17. Otwarte kwestie

1. **Kalkulator** — wspólny planer urlopu rodziny vs osobny (§12); do ustalenia z autorem kalkulatora.
