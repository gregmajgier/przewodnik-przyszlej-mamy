"""Generuje app/data/formularz_ui.json (formularz dynamiczny dla frontendu) z zmienne_uzytkownika.json + teksty poniżej.

Każda zmienna wejściowa (bez `wyl.*`) dostaje pytanie; obiekty rozbijamy na pola (klucz = pełna ścieżka,
np. `plan.wniosek_81_5.czy` — taka jak w regułach JSONLogic), tablice to `array_builder` z definicją pól.
`swiadczenia` przy pytaniu = świadczenia/ryzyka, które używają zmiennej (z `uzywane_w_regulach`) — frontend
sortuje karty brakujących pytań wg `ranking_swiadczen`.

Użycie (z backend/):  .venv/bin/python scripts/kontrakt/generuj_formularz.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "app" / "data"
OUT = DATA / "formularz_ui.json"

ETAP_PO = {"in": [{"var": "wnioskodawca.etap"}, ["po_porodzie", "adopcja_zastepcza"]]}
W_CIAZY = {"or": [{"==": [{"var": "wnioskodawca.etap"}, "w_ciazy"]}, {"==": [{"var": "ciaza.w_ciazy"}, True]}]}
PRACOWNIK = {"==": [{"var": "ubezpieczenie.tytul"}, "umowa_o_prace"]}
JDG = {"in": [{"var": "ubezpieczenie.tytul"}, ["jdg", "wspolpraca_jdg", "ulga_na_start"]]}
MA_TYTUL_ZUS = {"in": [{"var": "ubezpieczenie.tytul"}, ["umowa_o_prace", "umowa_zlecenia", "jdg", "wspolpraca_jdg", "duchowny", "marynarz"]]}
OJCIEC = {"==": [{"var": "wnioskodawca.rola"}, "ojciec"]}
MATKA = {"==": [{"var": "wnioskodawca.rola"}, "matka"]}
STRATA = {"in": [{"var": "porod.stan_dziecka"}, ["martwe", "zgon_do_8_tyg", "zgon_po_8_tyg"]]}
CUDZOZIEMIEC = {"!=": [{"var": "wnioskodawca.obywatelstwo"}, "PL"]}

ETYKIETY_ENUM = {
    "wnioskodawca.etap": {"planuje": "Planuję dziecko", "w_ciazy": "Jestem w ciąży / spodziewamy się dziecka",
                          "po_porodzie": "Dziecko już jest na świecie", "adopcja_zastepcza": "Przyjmujemy dziecko (adopcja, rodzina zastępcza)"},
    "wnioskodawca.rola": {"matka": "Mama", "ojciec": "Tata", "przysposabiajacy": "Rodzic adopcyjny",
                          "rodzina_zastepcza_niezawodowa": "Rodzina zastępcza (niezawodowa)",
                          "rodzina_zastepcza_zawodowa": "Rodzina zastępcza zawodowa", "inna": "Inna osoba"},
    "wnioskodawca.stan_cywilny": {"panna_kawaler": "Panna / kawaler", "malzenstwo": "W małżeństwie", "rozwod": "Po rozwodzie",
                                  "separacja": "W separacji", "wdowa_wdowiec": "Wdowa / wdowiec"},
    "ubezpieczenie.tytul": {"umowa_o_prace": "Umowa o pracę", "umowa_zlecenia": "Umowa zlecenia", "jdg": "Własna działalność",
                            "wspolpraca_jdg": "Współpraca przy działalności", "ulga_na_start": "Działalność na uldze na start",
                            "umowa_o_dzielo": "Umowa o dzieło", "duchowny": "Osoba duchowna", "marynarz": "Marynarz",
                            "sluzba_mundurowa": "Służba mundurowa", "krus": "Rolnik (KRUS)",
                            "bezrobotna_z_zasilkiem": "Bezrobotna/y z zasiłkiem", "bezrobotna_bez_zasilku": "Bezrobotna/y bez zasiłku",
                            "student": "Studentka / student", "brak": "Nie pracuję i nie mam ubezpieczenia"},
    "ubezpieczenie.chorobowe": {"obowiazkowe": "Obowiązkowe (np. etat)", "dobrowolne": "Dobrowolne (zlecenie, działalność)",
                                "brak": "Nie mam ubezpieczenia chorobowego"},
    "ubezpieczenie.przyczyna_rozwiazania_umowy": {"upadlosc": "Upadłość pracodawcy", "likwidacja": "Likwidacja pracodawcy",
                                                  "smierc_pracodawcy": "Śmierć pracodawcy", "naruszenie_przepisow": "Rozwiązanie z naruszeniem przepisów",
                                                  "inna": "Inna przyczyna"},
    "ubezpieczenie.rodzaj_umowy_o_prace": {"czas_nieokreslony": "Na czas nieokreślony", "czas_okreslony": "Na czas określony",
                                           "okres_probny_powyzej_1_mies": "Na okres próbny dłuższy niż miesiąc",
                                           "okres_probny_do_1_mies": "Na okres próbny do miesiąca", "zastepstwo": "Na zastępstwo"},
    "porod.stan_dziecka": {"zywe": "Dziecko żyje", "martwe": "Dziecko urodziło się martwe",
                           "zgon_do_8_tyg": "Dziecko zmarło w ciągu 8 tygodni od urodzenia", "zgon_po_8_tyg": "Dziecko zmarło później"},
    "matka.stan": {"zyje": "Mama jest z nami", "zmarla": "Mama zmarła", "porzucila_dziecko": "Mama porzuciła dziecko"},
}
ETYKIETY_ENUM["drugi_rodzic.tytul_ubezpieczenia"] = ETYKIETY_ENUM["ubezpieczenie.tytul"]

# klucz: (krok, pytanie, podpowiedz, kontrolka, show_if, wsparcie_ai)
P: dict[str, tuple] = {
    # ── triage ──
    "wnioskodawca.etap": ("triage", "Na jakim etapie jesteście?", "Od tego zależy, które świadczenia pokażemy najpierw.", "radio_cards", None, False),
    "wnioskodawca.rola": ("triage", "Kim jesteś dla dziecka?", "Mama, tata i rodzina przyjmująca dziecko mają trochę inne uprawnienia.", "radio_cards", None, False),
    "ciaza.w_ciazy": ("triage", "Czy jesteś teraz w ciąży?", "Ciąża daje m.in. zasiłek chorobowy 100% i ochronę przed zwolnieniem.", "boolean_toggle", MATKA, False),
    "ubezpieczenie.tytul": ("triage", "Na jakiej podstawie teraz pracujesz?", "To najważniejsze pytanie: decyduje, czy zasiłek wypłaci ZUS, czy gmina (świadczenie rodzicielskie 1000 zł).", "radio_cards", None, True),
    # ── dane osobowe ──
    "wnioskodawca.imie": ("dane_osobowe", "Jak masz na imię?", "Wpisz tak, jak w dowodzie osobistym.", "text", None, False),
    "wnioskodawca.drugie_imie": ("dane_osobowe", "Drugie imię (jeśli masz)", "Wnioski ZUS proszą o wszystkie imiona.", "text", None, False),
    "wnioskodawca.nazwisko": ("dane_osobowe", "Nazwisko", "Tak jak w dokumencie tożsamości.", "text", None, False),
    "wnioskodawca.nazwisko_rodowe": ("dane_osobowe", "Nazwisko rodowe", "Potrzebne w części wniosków (np. Z-10).", "text", None, False),
    "wnioskodawca.pesel": ("dane_osobowe", "Twój PESEL", "Z PESEL-u odczytamy datę urodzenia — ma znaczenie m.in. przy limicie 33/14 dni wynagrodzenia chorobowego.", "pesel", None, False),
    "wnioskodawca.dokument_tozsamosci": ("dane_osobowe", "Dokument tożsamości", "Tylko jeśli nie masz numeru PESEL albo wniosek tego wymaga.", "text", None, True),
    "wnioskodawca.obywatelstwo": ("dane_osobowe", "Jakie masz obywatelstwo?", "Kod kraju, np. PL. Cudzoziemcy z legalnym pobytem też mogą dostać 800+ i świadczenia gminne.", "select", None, False),
    "wnioskodawca.legalny_pobyt_w_polsce": ("dane_osobowe", "Czy masz prawo legalnego pobytu w Polsce?", "Warunek 800+ i świadczeń gminnych dla osób spoza Polski.", "boolean_toggle", CUDZOZIEMIEC, False),
    "wnioskodawca.status_ukr": ("dane_osobowe", "Czy masz PESEL ze statusem UKR?", "Przy statusie UKR 800+ wymaga aktywności zawodowej.", "boolean_toggle", CUDZOZIEMIEC, False),
    "wnioskodawca.aktywnosc_zawodowa_ukr": ("dane_osobowe", "Czy pracujesz lub prowadzisz działalność w Polsce?", "Dla osób ze statusem UKR to warunek otrzymania 800+.", "boolean_toggle", {"==": [{"var": "wnioskodawca.status_ukr"}, True]}, False),
    "wnioskodawca.adres_zamieszkania": ("dane_osobowe", "Gdzie mieszkasz?", "Gmina decyduje, który urząd rozpatrzy becikowe i świadczenia rodzinne, oraz jakie programy lokalne Ci przysługują.", "text", None, False),
    "wnioskodawca.adres_korespondencyjny": ("dane_osobowe", "Adres do korespondencji (jeśli inny)", "Zostaw puste, jeśli taki sam jak zamieszkania.", "text", None, False),
    "wnioskodawca.telefon": ("dane_osobowe", "Numer telefonu", "Nieobowiązkowy, ale ułatwia kontakt z ZUS.", "text", None, False),
    "wnioskodawca.email": ("dane_osobowe", "Adres e-mail", "Na ten adres wyślemy przypomnienia o terminach.", "text", None, False),
    "wnioskodawca.adres_e_doreczen": ("dane_osobowe", "Adres do e-Doręczeń (jeśli masz)", "Pozwala wysyłać wnioski do gminy i ZUS bez papieru.", "text", None, False),
    "wnioskodawca.numer_rachunku": ("dane_osobowe", "Numer konta do wypłaty", "Bez numeru konta ZUS wyśle pieniądze przekazem pocztowym — dłużej i z opłatą.", "iban", None, False),
    "wnioskodawca.wlasciciel_rachunku": ("dane_osobowe", "Właściciel konta (jeśli to nie Ty)", "Np. wspólne konto prowadzone na partnera.", "text", None, False),
    "wnioskodawca.stan_cywilny": ("dane_osobowe", "Jaki masz stan cywilny?", "Wpływa na skład rodziny i dodatek dla samotnych rodziców.", "select", None, False),
    "drugi_rodzic.dane": ("dane_osobowe", "Dane drugiego rodzica", "Wnioski o urlopy i świadczenia rodzinne pytają o oboje rodziców.", "text", {"in": [{"var": "wnioskodawca.rola"}, ["matka", "ojciec"]]}, False),
    # ── zatrudnienie i finanse ──
    "ubezpieczenie.chorobowe": ("zatrudnienie_i_finanse", "Czy masz ubezpieczenie chorobowe?", "Bez niego nie ma zasiłku chorobowego ani macierzyńskiego. Na zleceniu i w działalności jest dobrowolne — warto je włączyć.", "radio_cards", MA_TYTUL_ZUS, True),
    "ubezpieczenie.data_objecia_chorobowym": ("zatrudnienie_i_finanse", "Od kiedy masz ubezpieczenie chorobowe?", "Zasiłek chorobowy przysługuje po 30 dniach (obowiązkowe) albo 90 dniach (dobrowolne).", "date", {"in": [{"var": "ubezpieczenie.chorobowe"}, ["obowiazkowe", "dobrowolne"]]}, True),
    "ubezpieczenie.okresy": ("zatrudnienie_i_finanse", "Historia ubezpieczenia", "Pobierzemy ją z ZUS. Przerwy do 30 dni nie przerywają ciągłości.", "array_builder", MA_TYTUL_ZUS, True),
    "ubezpieczenie.data_ustania": ("zatrudnienie_i_finanse", "Czy umowa lub działalność już się zakończyła? Kiedy?", "Jeśli ubezpieczenie skończy się przed porodem, zasiłek macierzyński może nie przysługiwać — sprawdzimy alternatywy.", "date", MA_TYTUL_ZUS, False),
    "ubezpieczenie.umowa_rozwiazana_w_ciazy": ("zatrudnienie_i_finanse", "Czy pracodawca rozwiązał z Tobą umowę w czasie ciąży?", "W pewnych sytuacjach przysługuje wtedy zasiłek w wysokości zasiłku macierzyńskiego aż do porodu.", "boolean_toggle", {"and": [PRACOWNIK, W_CIAZY]}, False),
    "ubezpieczenie.przyczyna_rozwiazania_umowy": ("zatrudnienie_i_finanse", "Co było przyczyną rozwiązania umowy?", "Upadłość, likwidacja lub śmierć pracodawcy dają prawo do zasiłku; naruszenie przepisów — tylko z prawomocnym wyrokiem.", "radio_cards", {"==": [{"var": "ubezpieczenie.umowa_rozwiazana_w_ciazy"}, True]}, True),
    "ubezpieczenie.prawomocny_wyrok_naruszenie_przepisow": ("zatrudnienie_i_finanse", "Czy sąd prawomocnie potwierdził naruszenie przepisów?", "Bez prawomocnego wyroku ZUS nie wypłaci zasiłku z tego tytułu.", "boolean_toggle", {"==": [{"var": "ubezpieczenie.przyczyna_rozwiazania_umowy"}, "naruszenie_przepisow"]}, False),
    "ubezpieczenie.zapewniono_inne_zatrudnienie": ("zatrudnienie_i_finanse", "Czy pracodawca zaproponował Ci inną pracę?", "Jeśli zapewniono inne zatrudnienie, zasiłek po rozwiązaniu umowy nie przysługuje.", "boolean_toggle", {"==": [{"var": "ubezpieczenie.umowa_rozwiazana_w_ciazy"}, True]}, False),
    "ubezpieczenie.platnik": ("zatrudnienie_i_finanse", "Kto jest Twoim pracodawcą lub zleceniodawcą?", "Jeśli zgłasza ponad 20 osób do ubezpieczenia chorobowego, zasiłek wypłaci on, a nie ZUS.", "text", {"in": [{"var": "ubezpieczenie.tytul"}, ["umowa_o_prace", "umowa_zlecenia"]]}, True),
    "ubezpieczenie.wymiar_etatu": ("zatrudnienie_i_finanse", "W jakim wymiarze etatu pracujesz?", "Np. 1 to pełny etat, 0,5 to pół. Przy pełnym etacie podstawa zasiłku nie spadnie poniżej płacy minimalnej.", "number", PRACOWNIK, True),
    "ubezpieczenie.rodzaj_umowy_o_prace": ("zatrudnienie_i_finanse", "Jaką masz umowę o pracę?", "Umowa terminowa lub próbna (ponad miesiąc), która kończy się po 3. miesiącu ciąży, sama przedłuża się do dnia porodu. Nie dotyczy umowy na zastępstwo.", "radio_cards", PRACOWNIK, True),
    "ubezpieczenie.data_konca_umowy": ("zatrudnienie_i_finanse", "Do kiedy jest zawarta Twoja umowa?", "Sprawdzimy, czy przedłuży się do porodu — od tego zależy zasiłek macierzyński.", "date", {"and": [PRACOWNIK, {"in": [{"var": "ubezpieczenie.rodzaj_umowy_o_prace"}, ["czas_okreslony", "okres_probny_powyzej_1_mies", "okres_probny_do_1_mies", "zastepstwo"]]}]}, True),
    "ubezpieczenie.dni_wynagrodzenia_chorobowego_w_roku": ("zatrudnienie_i_finanse", "Ile dni zwolnienia lekarskiego wykorzystałaś już w tym roku?", "Przez pierwsze 33 dni w roku (14 po 50. roku życia) płaci pracodawca, potem ZUS.", "number", PRACOWNIK, True),
    "ubezpieczenie.przychody_12_miesiecy": ("zatrudnienie_i_finanse", "Twoje zarobki z ostatnich 12 miesięcy", "Z nich liczymy podstawę zasiłku: średnia pomniejszona o 13,71% składek. Miesiące przepracowane w mniej niż połowie pomijamy.", "array_builder", {"in": [{"var": "ubezpieczenie.tytul"}, ["umowa_o_prace", "umowa_zlecenia"]]}, True),
    "ubezpieczenie.przerwa_od_poprzedniego_zasilku_dni": ("zatrudnienie_i_finanse", "Ile dni minęło od Twojego poprzedniego zasiłku (np. chorobowego)?", "Jeśli mniej niż miesiąc, ZUS przyjmie tę samą podstawę co poprzednio.", "number", MA_TYTUL_ZUS, True),
    "ubezpieczenie.podstawa_poprzedniego_zasilku": ("zatrudnienie_i_finanse", "Jaka była podstawa poprzedniego zasiłku?", "Znajdziesz ją w decyzji ZUS lub na zaświadczeniu Z-3.", "number", {"<": [{"var": "ubezpieczenie.przerwa_od_poprzedniego_zasilku_dni"}, 30]}, True),
    "ubezpieczenie.zadeklarowana_podstawa_jdg": ("zatrudnienie_i_finanse", "Od jakiej kwoty płacisz składki w działalności?", "Zasiłek liczy się od zadeklarowanej podstawy z 12 miesięcy (krócej — według specjalnego wzoru).", "array_builder", JDG, True),
    "ubezpieczenie.zmiana_podstawy_w_ciazy": ("zatrudnienie_i_finanse", "Czy w ciąży podniosłaś podstawę składek?", "To dozwolone, ale ZUS może to sprawdzić — przygotujemy pismo z wyjaśnieniem.", "boolean_toggle", {"and": [JDG, W_CIAZY]}, False),
    "ubezpieczenie.zmiana_warunkow_zatrudnienia_w_ciazy": ("zatrudnienie_i_finanse", "Czy w ciąży zmieniły się warunki Twojej pracy (pensja, etat)?", "Zmiana może obniżyć zasiłek — warto to sprawdzić wcześniej.", "boolean_toggle", {"and": [PRACOWNIK, W_CIAZY]}, False),
    "ubezpieczenie.zadluzenie_skladkowe": ("zatrudnienie_i_finanse", "Czy masz zaległości w składkach ZUS?", "Zadłużenie może wstrzymać zasiłek. Pomożemy przygotować wniosek o układ ratalny.", "number", JDG, True),
    "ubezpieczenie.pobiera_emeryture_rente": ("zatrudnienie_i_finanse", "Czy pobierasz emeryturę lub rentę?", "Pytanie z wniosków Z-10 i ZNp-7.", "boolean_toggle", None, False),
    "ubezpieczenie.zlozyla_wniosek_emerytura_renta": ("zatrudnienie_i_finanse", "Czy złożyłaś wniosek o emeryturę lub rentę?", "Pytanie z wniosku Z-10.", "boolean_toggle", {"!=": [{"var": "ubezpieczenie.pobiera_emeryture_rente"}, True]}, False),
    "zdrowie.ezla": ("zatrudnienie_i_finanse", "Zwolnienia lekarskie (e-ZLA)", "Pobierzemy je z ZUS. Kod B oznacza zwolnienie w ciąży — wtedy zasiłek wynosi 100%.", "array_builder", W_CIAZY, True),
    "zdrowie.okres_zasilkowy_wykorzystany_dni": ("zatrudnienie_i_finanse", "Ile dni zasiłku chorobowego wykorzystałaś w tej ciąży?", "W ciąży zasiłek przysługuje maksymalnie 270 dni.", "number", W_CIAZY, True),
    "zdrowie.nadal_niezdolna_do_pracy": ("zatrudnienie_i_finanse", "Czy po 270 dniach nadal nie możesz pracować?", "Wtedy można starać się o świadczenie rehabilitacyjne.", "boolean_toggle", {">=": [{"var": "zdrowie.okres_zasilkowy_wykorzystany_dni"}, 240]}, False),
    "zdrowie.rokowania_odzyskania_zdolnosci": ("zatrudnienie_i_finanse", "Czy lekarz ocenia, że wrócisz do pracy po dalszym leczeniu?", "To warunek świadczenia rehabilitacyjnego (decyduje lekarz orzecznik ZUS).", "boolean_toggle", {"==": [{"var": "zdrowie.nadal_niezdolna_do_pracy"}, True]}, False),
    "zdrowie.data_wyczerpania_zasilku": ("zatrudnienie_i_finanse", "Kiedy kończy się Twój zasiłek chorobowy?", "Od następnego dnia liczymy świadczenie rehabilitacyjne.", "date", {"==": [{"var": "zdrowie.nadal_niezdolna_do_pracy"}, True]}, False),
    "zdrowie.zasilek_opiekunczy_wykorzystany_dni": ("zatrudnienie_i_finanse", "Ile dni opieki nad chorym dzieckiem wykorzystałeś/aś w tym roku?", "Zasiłek opiekuńczy (80%) przysługuje do 60 dni w roku.", "number", ETAP_PO, False),
    "drugi_rodzic.tytul_ubezpieczenia": ("zatrudnienie_i_finanse", "Na jakiej podstawie pracuje drugi rodzic?", "Od tego zależy podział urlopu rodzicielskiego i np. świadczenie rodzicielskie dla nieubezpieczonej mamy.", "radio_cards", {"in": [{"var": "wnioskodawca.rola"}, ["matka", "ojciec"]]}, False),
    "drugi_rodzic.platnik": ("zatrudnienie_i_finanse", "Pracodawca drugiego rodzica", "Potrzebny do wniosków o urlop ojcowski i rodzicielski.", "text", {"==": [{"var": "drugi_rodzic.tytul_ubezpieczenia"}, "umowa_o_prace"]}, True),
    "drugi_rodzic.aktywny_zawodowo": ("zatrudnienie_i_finanse", "Czy drugi rodzic pracuje?", "Program „Aktywny rodzic” daje 1500 zł, gdy oboje rodzice pracują.", "boolean_toggle", None, False),
    "rodzina.sklad": ("zatrudnienie_i_finanse", "Kto wchodzi w skład Twojej rodziny?", "Dochód dzielimy na wszystkie te osoby — tak liczy gmina przy becikowym i zasiłku rodzinnym.", "array_builder", None, False),
    "rodzina.dochod_rok_bazowy": ("zatrudnienie_i_finanse", "Jaki był dochód Twojej rodziny w roku bazowym?", "Becikowe: do 1922 zł na osobę miesięcznie; zasiłek rodzinny: do 674 zł (764 zł przy niepełnosprawności dziecka).", "number", None, True),
    "rodzina.inne_pobierane_swiadczenia": ("zatrudnienie_i_finanse", "Czy pobierasz już jakieś świadczenia?", "Niektóre (np. zasiłek macierzyński, świadczenie pielęgnacyjne) wykluczają świadczenie rodzicielskie z gminy.", "array_builder", None, False),
    "rodzina.swiadczenie_za_granica": ("zatrudnienie_i_finanse", "Czy ktoś z rodziny dostaje świadczenie na to dziecko za granicą?", "Świadczenie z innego kraju wyłącza polskie świadczenia z tego samego tytułu.", "boolean_toggle", None, False),
    # ── ciąża i dzieci ──
    "ciaza.przewidywana_data_porodu": ("ciaza_i_dzieci", "Kiedy jest termin porodu?", "Wpisz datę z zaświadczenia lekarskiego — od niej liczymy terminy i urlopy.", "date", W_CIAZY, True),
    "ciaza.opieka_medyczna_od_10_tyg": ("ciaza_i_dzieci", "Czy byłaś pod opieką lekarza lub położnej od 10. tygodnia ciąży?", "To warunek becikowego i świadczenia „Za życiem”. Potwierdza to zaświadczenie lekarskie.", "boolean_toggle", None, True),
    "porod.data_porodu": ("ciaza_i_dzieci", "Kiedy urodziło się dziecko?", "Od tej daty biegną terminy, np. 21 dni na wniosek o 81,5% zasiłku.", "date", ETAP_PO, False),
    "porod.stan_dziecka": ("ciaza_i_dzieci", "Jak się czuje dziecko?", "Jeśli wydarzyło się coś trudnego, przeprowadzimy Cię spokojnie przez to, co Ci przysługuje.", "radio_cards", ETAP_PO, False),
    "porod.data_zgonu_dziecka": ("ciaza_i_dzieci", "Kiedy dziecko zmarło?", "Przykro nam. Ta data jest potrzebna do zasiłku macierzyńskiego i pogrzebowego.", "date", {"in": [{"var": "porod.stan_dziecka"}, ["zgon_do_8_tyg", "zgon_po_8_tyg"]]}, False),
    "porod.liczba_dzieci": ("ciaza_i_dzieci", "Ile dzieci urodziło się (lub urodzi) przy tym porodzie?", "Przy bliźniętach i większej liczbie dzieci urlopy są dłuższe.", "number", {"or": [ETAP_PO, W_CIAZY]}, False),
    "porod.tydzien_ciazy": ("ciaza_i_dzieci", "W którym tygodniu ciąży urodziło się dziecko?", "Przed 37. tygodniem przysługuje uzupełniający urlop macierzyński (do 8 lub 15 tygodni).", "number", ETAP_PO, True),
    "dzieci": ("ciaza_i_dzieci", "Twoje dzieci", "Dodaj wszystkie dzieci — także starsze. Liczą się do 800+, Karty Dużej Rodziny i zasiłku rodzinnego.", "array_builder", None, True),
    "matka.stan": ("ciaza_i_dzieci", "Sytuacja mamy dziecka", "W wyjątkowych sytuacjach tata może przejąć urlop macierzyński wcześniej.", "radio_cards", OJCIEC, False),
    "matka.ubezpieczona_w_dniu_porodu": ("ciaza_i_dzieci", "Czy mama dziecka miała ubezpieczenie chorobowe w dniu porodu?", "Jeśli nie, tata może skorzystać z urlopu rodzicielskiego, a mama — ze świadczenia rodzicielskiego 1000 zł z gminy.", "boolean_toggle", OJCIEC, False),
    "matka.wykorzystala_14_tyg": ("ciaza_i_dzieci", "Czy mama wykorzystała już 14 tygodni urlopu po porodzie?", "Po 14 tygodniach mama może oddać resztę urlopu macierzyńskiego tacie.", "boolean_toggle", OJCIEC, False),
    "matka.data_konca_urlopu_macierzynskiego": ("ciaza_i_dzieci", "Kiedy kończy się urlop macierzyński mamy?", "Tata zaczyna przejęty urlop następnego dnia.", "date", OJCIEC, False),
    "matka.pobiera_zasilek_8_tyg_po_porodzie": ("ciaza_i_dzieci", "Czy mama pobiera zasiłek przez 8 tygodni po porodzie?", "Potrzebne do oświadczenia ZAS-39.", "boolean_toggle", OJCIEC, False),
    "matka.hospitalizacja": ("ciaza_i_dzieci", "Czy mama przebywa (przebywała) w szpitalu po porodzie?", "Pobyt mamy w szpitalu po 8 tygodniach od porodu pozwala tacie przejąć urlop na ten czas.", "array_builder", OJCIEC, True),
    "matka.orzeczenie_niezdolnosci_do_samodzielnej_egzystencji": ("ciaza_i_dzieci", "Czy mama ma orzeczenie o niezdolności do samodzielnej egzystencji?", "Wtedy tata może przejąć urlop macierzyński już po 8 tygodniach.", "boolean_toggle", OJCIEC, False),
    "matka.podjela_prace_min_pol_etatu": ("ciaza_i_dzieci", "Czy mama (bez ubezpieczenia w dniu porodu) podjęła pracę na co najmniej pół etatu?", "Wtedy tata może przejąć urlop macierzyński — nie wcześniej niż po 14 tygodniach od porodu.", "boolean_toggle", {"and": [OJCIEC, {"==": [{"var": "matka.ubezpieczona_w_dniu_porodu"}, False]}]}, False),
    "rodzina.samotne_wychowywanie": ("ciaza_i_dzieci", "Czy samotnie wychowujesz dziecko?", "Daje dodatek do zasiłku rodzinnego i preferencyjne rozliczenie podatku.", "boolean_toggle", None, False),
    "rodzina.uznanie_ojcostwa": ("ciaza_i_dzieci", "Czy ojciec uznał dziecko?", "Potrzebne, gdy rodzice nie są małżeństwem — bez tego tata nie przejmie urlopu.", "boolean_toggle", {"!=": [{"var": "wnioskodawca.stan_cywilny"}, "malzenstwo"]}, False),
    "rodzina.wspolne_gospodarstwo_domowe": ("ciaza_i_dzieci", "Czy mieszkacie razem?", "Wpływa na skład rodziny i zasiłek opiekuńczy.", "boolean_toggle", None, False),
    "rodzina.opieka_naprzemienna": ("ciaza_i_dzieci", "Czy sprawujecie opiekę naprzemienną?", "Wtedy 800+ i „Aktywny rodzic” dzieli się po połowie.", "boolean_toggle", {"!=": [{"var": "rodzina.wspolne_gospodarstwo_domowe"}, True]}, False),
    "rodzina.poniesiono_koszty_pogrzebu": ("ciaza_i_dzieci", "Czy to Ty pokryłaś/eś koszty pogrzebu dziecka?", "Bardzo nam przykro. Osobie, która pokryła koszty, ZUS wypłaca zasiłek pogrzebowy 7000 zł.", "boolean_toggle", STRATA, False),
    # ── plan urlopów ──
    "plan.urlop_macierzynski": ("plan_urlopow", "Kiedy chcesz rozpocząć urlop macierzyński?", "Najwcześniej 6 tygodni przed terminem porodu; 14 tygodni po porodzie mama wykorzystuje osobiście.", "date", MATKA, False),
    "plan.wniosek_81_5": ("plan_urlopow", "Czy chcesz złożyć wniosek o 81,5% zasiłku za cały okres?", "Wniosek do 21 dni po porodzie: równa kwota co miesiąc. Bez niego: 100% za macierzyński i 70% za rodzicielski.", "boolean_toggle", MATKA, False),
    "plan.rezygnacja_z_macierzynskiego_po_14_tyg": ("plan_urlopow", "Czy po 14 tygodniach chcesz oddać resztę urlopu macierzyńskiego tacie?", "Tata przejmie urlop od dnia, w którym go oddasz.", "boolean_toggle", MATKA, False),
    "plan.czesci_urlopu_rodzicielskiego": ("plan_urlopow", "Jak podzielicie urlop rodzicielski?", "41 tygodni (przy bliźniętach 43) na oboje rodziców, w tym po 9 tygodni tylko dla każdego z Was. Do 5 części.", "array_builder", {"in": [{"var": "wnioskodawca.rola"}, ["matka", "ojciec", "przysposabiajacy", "rodzina_zastepcza_niezawodowa"]]}, False),
    "plan.urlop_uzupelniajacy": ("plan_urlopow", "Uzupełniający urlop macierzyński", "Tydzień urlopu za każdy tydzień pobytu dziecka w szpitalu — maksymalnie 8 lub 15 tygodni, zaraz po macierzyńskim.", "number", {"<": [{"var": "porod.tydzien_ciazy"}, 37]}, True),
    "plan.czesci_urlopu_ojcowskiego": ("plan_urlopow", "Kiedy tata weźmie urlop ojcowski?", "14 dni — naraz albo w dwóch częściach po co najmniej 7 dni, do ukończenia przez dziecko 12 miesięcy.", "array_builder", OJCIEC, False),
    "plan.data_zlozenia_wniosku_u_pracodawcy": ("plan_urlopow", "Kiedy złożysz wniosek o urlop u pracodawcy?", "Urlop rodzicielski: 21 dni przed, ojcowski: 7 dni przed rozpoczęciem.", "date", PRACOWNIK, False),
    "wnioski_zlozone": ("plan_urlopow", "Wnioski, które już złożyłeś/aś", "Odhaczymy je w kalendarzu i nie będziemy o nie przypominać.", "array_builder", None, False),
}

# podpola obiektów: klucz -> {pole: (pytanie, kontrolka)}; pytanie obiektu z P to nagłówek grupy
PODPOLA_NAZWY = {
    "ulica": "Ulica", "nr_domu": "Numer domu", "nr_lokalu": "Numer lokalu", "kod_pocztowy": "Kod pocztowy",
    "miejscowosc": "Miejscowość", "gmina": "Gmina", "teryt_gminy": "Kod TERYT gminy", "powiat": "Powiat",
    "wojewodztwo": "Województwo", "kraj": "Kraj (kod, np. PL)", "rodzaj": "Rodzaj", "seria": "Seria", "numer": "Numer",
    "nazwa": "Nazwa", "nip": "NIP", "regon": "REGON", "adres": "Adres", "liczba_ubezpieczonych_chorobowo": "Ile osób zgłasza do ubezpieczenia chorobowego?",
    "imie": "Imię", "nazwisko": "Nazwisko", "pesel": "PESEL", "obywatelstwo": "Obywatelstwo",
    "czy": "Tak / nie", "data": "Data", "kwota_przed": "Kwota przed zmianą", "kwota_po": "Kwota po zmianie", "opis": "Opis",
    "kwota": "Kwota (zł)", "na_dzien": "Na dzień", "rok": "Rok", "dochody_opodatkowane": "Dochody opodatkowane (zł)",
    "dochody_nieopodatkowane": "Dochody nieopodatkowane (zł)", "dochody_utracone": "Dochody utracone (zł)",
    "dochody_uzyskane": "Dochody uzyskane (zł)", "od": "Od", "do": "Do", "tygodnie_przed_porodem": "Ile tygodni przed porodem?",
    "data_zlozenia": "Data złożenia", "wymiar_tyg": "Wymiar (tyg.)", "rodzic": "Który rodzic?",
}
KONTROLKA_TYPU = {"date": "date", "date|null": "date", "boolean": "boolean_toggle", "integer": "number", "number": "number",
                  "number|null": "number", "string(11)": "pesel", "string(7)": "text"}


def kontrolka_pola(typ: str, nazwa: str) -> str:
    if nazwa == "pesel":
        return "pesel"
    return KONTROLKA_TYPU.get(typ, "text")


def opcje(klucz: str, z: dict) -> list[dict] | None:
    wartosci = z.get("enum")
    if not wartosci and klucz == "drugi_rodzic.tytul_ubezpieczenia":
        wartosci = list(ETYKIETY_ENUM[klucz])
    if not wartosci:
        return None
    et = ETYKIETY_ENUM.get(klucz, {})
    return [{"wartosc": w, "etykieta": et.get(w, w.replace("_", " ").capitalize())} for w in wartosci]


def generuj() -> dict:
    zmienne = json.loads((DATA / "zmienne_uzytkownika.json").read_text(encoding="utf-8"))
    reguly = json.loads((DATA / "reguly_uprawnien.json").read_text(encoding="utf-8"))
    pytania = []
    for z in zmienne["zmienne"]:
        klucz = z["klucz"]
        if klucz.startswith(("wyl.", "param.")):
            continue
        if klucz not in P:
            raise KeyError(f"Brak tekstu pytania dla {klucz} — dopisz do P w generuj_formularz.py")
        krok, pytanie, podp, kontrolka, show_if, ai = P[klucz]
        wpis = {"klucz": klucz, "krok": krok, "pytanie": pytanie, "podpowiedz": podp, "kontrolka": kontrolka,
                "opcje": opcje(klucz, z), "show_if": show_if, "wsparcie_ai": ai, "zrodlo": z.get("zrodlo", []),
                "wrazliwe": z.get("wrazliwe", False), "swiadczenia": z.get("uzywane_w_regulach", []),
                "wymagane_dla": z.get("wymagane_dla", [])}
        pola = z.get("pola")
        if pola and z["typ"].startswith("array"):
            wpis["kontrolka"] = "array_builder"
            wpis["pola"] = [{"nazwa": p["nazwa"], "etykieta": p.get("opis") or PODPOLA_NAZWY.get(p["nazwa"], p["nazwa"]),
                             "kontrolka": kontrolka_pola(p["typ"], p["nazwa"])} for p in pola]
        elif pola:
            # obiekt: grupa pytań, każde podpole ma pełną ścieżkę (jak w JSONLogic)
            wpis["kontrolka"] = "grupa"
            wpis["pola"] = [{"klucz": f"{klucz}.{p['nazwa']}", "etykieta": PODPOLA_NAZWY.get(p["nazwa"], p["nazwa"]),
                             "kontrolka": "boolean_toggle" if p["nazwa"] == "czy" else kontrolka_pola(p["typ"], p["nazwa"]),
                             **({"show_if": {"==": [{"var": f"{klucz}.czy"}, True]}} if p["nazwa"] != "czy" and any(x["nazwa"] == "czy" for x in pola) else {})}
                            for p in pola]
        pytania.append(wpis)

    p = reguly["parametry_drzewo"]
    ranking = [
        ("ZASILEK_MACIERZYNSKI_MATKA", p["urlop"]["macierzynski_tyg"]["1"], p["zasilek"]["procent"]["macierzynski"], 0, p["termin"]["wniosek_81_5_dni"]),
        ("ZASILEK_URLOP_RODZICIELSKI", p["urlop"]["rodzicielski_tyg"]["1"], p["zasilek"]["procent"]["rodzicielski"], 0, p["termin"]["urlop_rodzicielski_przed_dni"]),
        ("ZASILEK_ADOPCJA_ZASTEPCZA", p["urlop"]["macierzynski_tyg"]["1"], p["zasilek"]["procent"]["macierzynski"], 0, 7),
        ("ZASILEK_MACIERZYNSKI_OJCIEC_PRZEJECIE", p["urlop"]["macierzynski_tyg"]["1"] - p["urlop"]["macierzynski_min_matka_tyg"], p["zasilek"]["procent"]["macierzynski"], 0, 30),
        ("ZASILEK_URLOP_UZUPELNIAJACY", p["urlop"]["uzupelniajacy_max_tyg"]["wczesniak_ciezki"], p["zasilek"]["procent"]["uzupelniajacy"], 0, p["termin"]["urlop_uzup_przed_koncem_dni"]),
        ("ZASILEK_CHOROBOWY_CIAZA", round(p["zasilek"]["okres_zasilkowy_dni"] / 7), p["zasilek"]["chorobowy_ciaza_procent"], 0, 14),
        ("ZASILEK_W_WYSOKOSCI_MACIERZYNSKIEGO", 26, p["zasilek"]["procent"]["macierzynski"], 0, 30),
        ("SWIADCZENIE_REHABILITACYJNE", round(p["zasilek"]["rehabilitacyjny_max_dni"] / 7), p["zasilek"]["rehabilitacyjny_standard_90_dni_procent"], 0, 30),
        ("ZASILEK_MACIERZYNSKI_MARTWE_URODZENIE", p["urlop"]["martwe_urodzenie_tyg"], p["zasilek"]["procent"]["macierzynski"], 0, 21),
        ("ZASILEK_URLOP_OJCOWSKI", 2, p["zasilek"]["procent"]["ojcowski"], 0, 365),
        ("ZASILEK_OPIEKUNCZY", round(p["zasilek"]["opiekunczy_max_dni_w_roku"] / 7, 1), p["zasilek"]["opiekunczy_procent"], 0, 180),
        ("SWIADCZENIE_RODZICIELSKIE", p["swiadczenia"]["rodzicielskie_tyg"]["1"], 0, p["swiadczenia"]["rodzicielskie_zl_mies"] * 12, p["termin"]["sr7_mies"] * 30),
        ("ZASILEK_800PLUS", 52, 0, p["swiadczenia"]["800plus_zl_mies"] * 12, p["termin"]["800plus_mies"] * 30),
        ("AKTYWNY_RODZIC", 104, 0, p["swiadczenia"]["aktywny_rodzic_praca_zl"] * 24, 60),
        ("ZASILEK_POGRZEBOWY", 0, 0, p["zasilek"]["pogrzebowy_zl"], p["termin"]["pogrzebowy_mies"] * 30),
        ("ZA_ZYCIEM_4000", 0, 0, p["swiadczenia"]["za_zyciem_zl"], p["termin"]["za_zyciem_mies"] * 30),
        ("BECIKOWE", 0, 0, p["swiadczenia"]["becikowe_zl"], p["termin"]["becikowe_mies"] * 30),
        ("ZASILEK_RODZINNY", 52, 0, p["swiadczenia"]["zasilek_rodzinny_kwoty_zl"]["do_5_lat"] * 12 + p["swiadczenia"]["dodatek_urodzenie_zl"], 365),
        ("KARTA_DUZEJ_RODZINY", 0, 0, 0, 365),
        ("OCHRONA_STOSUNKU_PRACY", 0, 0, 0, 30),
        ("FORMALNOSC_ZGLOSZENIE_URODZENIA", 0, 0, 0, p["termin"]["zgloszenie_urodzenia_dni"]),
        ("FORMALNOSC_ODPIS_AKTU", 0, 0, 0, 60),
    ]
    ids = {s["id"] for s in reguly["swiadczenia"]}
    assert {r[0] for r in ranking} == ids, ids ^ {r[0] for r in ranking}
    return {
        "meta": {
            "nazwa": "Formularz dynamiczny (frontend React)", "wersja": reguly["meta"]["wersja"],
            "generator": "backend/scripts/kontrakt/generuj_formularz.py — nie edytować ręcznie",
            "kroki": ["triage", "dane_osobowe", "zatrudnienie_i_finanse", "ciaza_i_dzieci", "plan_urlopow"],
            "kontrolki": ["radio_cards", "text", "pesel", "iban", "date", "number", "boolean_toggle", "select", "array_builder", "grupa"],
            "show_if": "JSONLogic na stanie formularza (te same ścieżki co w regułach); brak = pokaż zawsze. Zmienna jeszcze bez odpowiedzi (null) ukrywa pytanie zależne.",
            "sortowanie": "Wartość świadczenia = czas_tyg × stawka_procent / 100 × szacowana_podstawa / 4,33 + kwota_stala; "
                          "pilność = 1 / max(pilnosc_dni, 1). Kartę brakującego pytania sortuj malejąco po najwyższej "
                          "wartości ze świadczeń w polu `swiadczenia`, przy remisie — po pilności.",
        },
        "pytania": pytania,
        "ranking_swiadczen": [{"id": i, "czas_tyg": c, "stawka_procent": s, "kwota_stala": k, "pilnosc_dni": d} for i, c, s, k, d in ranking],
    }


def main() -> int:
    tekst = json.dumps(generuj(), ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        return 0 if OUT.exists() and OUT.read_text(encoding="utf-8") == tekst else 1
    OUT.write_text(tekst, encoding="utf-8")
    print(f"Zapisano {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
