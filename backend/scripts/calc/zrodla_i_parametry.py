# -*- coding: utf-8 -*-
"""
zrodla_i_parametry.py
=====================
Wspólny moduł dla `sprawdzanie_swiadczen.py` i `kalkulator_zasilku.py`:

  1. ZRODLA      – rejestr źródeł: klucz -> (plik, strona, czego dotyczy). Każda reguła
                   w pozostałych plikach odwołuje się do tych kluczy, a komentarze w kodzie
                   podają plik i stronę wprost.
  2. PARAMETRY   – wszystkie liczby (procenty, wymiary urlopów, kwoty). Nazwy kluczy są
                   takie jak w sekcji "parametry_admin" pliku zmienne_uzytkownika.json
                   (wersja zaktualizowana), więc panel admina nadpisuje je 1:1.
  3. Narzędzia   – daty, kwoty, odczyt pól z danych użytkownika.

Strony podane jako „str.” to strony PDF. W Poradniku podaję numer wydrukowany na stronie
i w nawiasie numer strony PDF (wydrukowany = PDF − 1). Załącznik ZUS (.docx) nie ma
numeracji stron – odwołuję się do nazw jego sekcji.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# 1. PLIKI ŹRÓDŁOWE
# ═══════════════════════════════════════════════════════════════════════════
KP = "Kodeks_pracy_wyciąg_z_przepisów.pdf"
UZ = ("wyciąg_z_ustawy_o_świadczeniach_pieniężnych_z_ubezpieczeń_społecznych_"
      "w_razie_choroby_i_macierzyństwa_ustawa_zasiłkowa.pdf")
ZAL = "Załącznik__maksymalny_czas_trwania_zasiłków__wysokość__podstawa_wymiaru.docx"
ZAD = "ZUS_-_Pełna_treść_zadania_konkursowego.pdf"
POR = "Poradnik_dla_rodziców_ZUS_2026.pdf"
ROZ = ("rozporządzenie_w_spr__zakresu_informacji_o_okolicznościach_mających_"
       "wpływ_na_prawo_do_zasiłków___.pdf")
JSN = "zmienne_uzytkownika.json"
KAT = "katalog_wnioskow_pdf.json"

ZRODLA: dict[str, tuple[str, str, str]] = {
    # ── Kodeks pracy ────────────────────────────────────────────────────────
    "KP_92": (KP, "str. 1–2", "art. 92 – wynagrodzenie chorobowe: 33 dni w roku (14 po 50. r.ż.), w ciąży 100%"),
    "KP_180_1": (KP, "str. 3", "art. 180 § 1 – urlop macierzyński 20/31/33/35/37 tyg. wg liczby dzieci z jednego porodu"),
    "KP_180_2_3": (KP, "str. 3", "art. 180 § 2–3 – max 6 tyg. przed przewidywaną datą porodu, reszta po porodzie"),
    "KP_180_4_5": (KP, "str. 3", "art. 180 § 4–5 – rezygnacja matki po min. 14 tyg. po porodzie na rzecz ojca"),
    "KP_180_6_7": (KP, "str. 3", "art. 180 § 6–7 – matka z orzeczeniem o niezdolności do samodzielnej egzystencji: po 8 tyg."),
    "KP_180_10_11": (KP, "str. 4", "art. 180 § 10–11 – pobyt matki w szpitalu po 8 tyg.: ojciec za okres pobytu"),
    "KP_180_12_13": (KP, "str. 4", "art. 180 § 12–13 – zgon matki / porzucenie dziecka (porzucenie: nie wcześniej niż po 8 tyg.)"),
    "KP_180_14": (KP, "str. 4", "art. 180 § 14 – łączny wymiar przy podziale nie może przekroczyć § 1"),
    "KP_180_15_17": (KP, "str. 4–5", "art. 180 § 15–17 – matka nieubezpieczona: zgon, porzucenie, niezdolność, podjęcie pracy"),
    "KP_1801": (KP, "str. 5", "art. 180¹ – martwe urodzenie / zgon dziecka: 8 tyg., min. 7 dni od zgonu"),
    "KP_1802": (KP, "str. 5", "art. 180² § 1–4 – uzupełniający urlop macierzyński: 15/8/8 tyg., wiele dzieci, sumowanie, zaokrąglenie w górę, jednorazowo"),
    "KP_1821a": (KP, "str. 6", "art. 182¹a – rodzicielski 41/43 (Za życiem 65/67), łącznie dla obojga, 9 tyg. nieprzenoszalne, jednoczesne korzystanie"),
    "KP_1821c": (KP, "str. 6", "art. 182¹c – max 5 części, do końca roku kalendarzowego, w którym dziecko kończy 6 lat"),
    "KP_1821d": (KP, "str. 6", "art. 182¹d – wniosek 21 dni przed; liczba części = liczba wniosków"),
    "KP_1821e": (KP, "str. 7", "art. 182¹e – łączenie rodzicielskiego z pracą: max 1/2 etatu, u pracodawcy udzielającego urlopu, wniosek 21 dni"),
    "KP_1821f": (KP, "str. 7", "art. 182¹f – wydłużenie: iloczyn tygodni i wymiaru pracy (§ 2), w dniach bez niepełnego dnia (§ 4), dzielenie przez (1 − wymiar) (§ 7), limity 82/86 i 130/134 tyg."),
    "KP_1823": (KP, "str. 7–8", "art. 182³ – urlop ojcowski 2 tyg., max 2 części ≥ 1 tydz., do 12 mies. życia / 12 mies. od uprawomocnienia przysposobienia (≤ 14 lat)"),
    "KP_183_1": (KP, "str. 8", "art. 183 § 1 – rodzina zastępcza (bez zawodowej): 20–37 tyg., nie dłużej niż do 7 r.ż. (10 przy odroczeniu obowiązku szkolnego)"),
    "KP_183_11": (KP, "str. 8", "art. 183 § 1¹ – przysposobienie: 20–37 tyg., nie dłużej niż do 14 r.ż."),
    "KP_183_3": (KP, "str. 8", "art. 183 § 3 – prawo do 9 tyg. urlopu na warunkach urlopu macierzyńskiego"),
    "KP_183_31": (KP, "str. 8", "art. 183 § 3¹ – uzupełniający urlop, jeśli pobyt dziecka w szpitalu był po przyjęciu na wychowanie"),
    "KP_183_4": (KP, "str. 8–9", "art. 183 § 4–4⁵ – rodzicielski przy przyjęciu: 41/43, 38 w przypadku § 3; Za życiem 65/67/62; przy przysposobieniu do 14 r.ż."),
    "KP_183_5_6": (KP, "str. 9", "art. 183 § 5–6 – odesłanie do art. 182¹a–182¹g; wniosek w 7 dni, start najpóźniej 21 dni od przyjęcia"),
    "KP_183_7_8": (KP, "str. 9", "art. 183 § 7–8 – przysposobienie po rodzinie zastępczej: wymiar pomniejszony o wykorzystany urlop"),
    "KP_1831": (KP, "str. 9", "art. 183¹ – tydzień urlopu = 7 dni kalendarzowych; pierwszy dzień urlopu = dzień porodu"),
    "KP_184": (KP, "str. 10", "art. 184 – za okresy tych urlopów przysługuje zasiłek macierzyński na zasadach ustawy zasiłkowej"),
    # ── Ustawa zasiłkowa ────────────────────────────────────────────────────
    "UZ_2a": (UZ, "str. 1", "art. 2a – zadłużenie składkowe > 1% płacy minimalnej (m.in. JDG) wstrzymuje prawo do zasiłku; przedawnienie po 6 mies."),
    "UZ_3": (UZ, "str. 1–2", "art. 3 pkt 3–4 – wynagrodzenie/przychód po odliczeniu składek (13,71%)"),
    "UZ_4": (UZ, "str. 2", "art. 4 – okres wyczekiwania 30 dni (obowiązkowe) / 90 dni (dobrowolne); wliczanie okresów z przerwą ≤ 30 dni; wyjątki (np. 10 lat ubezpieczenia obowiązkowego)"),
    "UZ_6_7": (UZ, "str. 2–3", "art. 6–7 – zasiłek chorobowy w czasie ubezpieczenia; po ustaniu: niezdolność do 14 dni od ustania, trwająca ≥ 30 dni"),
    "UZ_8_9": (UZ, "str. 3", "art. 8–9 – okres zasiłkowy 270 dni w ciąży (bez limitu 91 dni po ustaniu); wliczanie poprzednich niezdolności"),
    "UZ_11": (UZ, "str. 3", "art. 11 ust. 2 pkt 1, ust. 4–5 – zasiłek chorobowy w ciąży 100%, za każdy dzień, miesiąc = 30 dni"),
    "UZ_12_13": (UZ, "str. 4", "art. 12–13 – brak zasiłku za okres zachowania wynagrodzenia; wyłączenia po ustaniu ubezpieczenia"),
    "UZ_18_19": (UZ, "str. 5–6", "art. 18–19 – świadczenie rehabilitacyjne: po wyczerpaniu zasiłku, max 12 mies., orzeka lekarz orzecznik ZUS, w ciąży 100%"),
    "UZ_29_1_2": (UZ, "str. 6–7", "art. 29 ust. 1–2 – prawo do zasiłku macierzyńskiego: poród; przyjęcie dziecka do 14 r.ż. + wniosek do sądu; rodzina zastępcza (bez zawodowej) do 7/10 r.ż."),
    "UZ_29_3_10": (UZ, "str. 7–8", "art. 29 ust. 3–10 – zasiłek dla ojca: rezygnacja matki po 14 tyg.; po 8 tyg. przy orzeczeniu, szpitalu, porzuceniu; zgon; matka nieubezpieczona"),
    "UZ_29a": (UZ, "str. 8", "art. 29a – okres zasiłku = okresy urlopów z KP; jednoczesne korzystanie z rodzicielskiego ≤ wymiar"),
    "UZ_30": (UZ, "str. 8", "art. 30 – zasiłek po ustaniu ubezpieczenia w ciąży (upadłość/likwidacja/śmierć pracodawcy, naruszenie przepisów + wyrok); ust. 3 – zasiłek w wysokości zasiłku macierzyńskiego do dnia porodu"),
    "UZ_30a": (UZ, "str. 8", "art. 30a – wniosek do 21 dni po porodzie / po przyjęciu dziecka o zasiłek za cały okres (bez 9 tyg. drugiego rodzica)"),
    "UZ_31_1_3": (UZ, "str. 9", "art. 31 ust. 1–3 – 100% (macierzyński, na warunkach macierzyńskiego, uzupełniający, ojcowski), 70% (rodzicielski), 81,5% (wniosek z art. 30a)"),
    "UZ_31_3a": (UZ, "str. 9", "art. 31 ust. 3a–3c – podwyższenie do kwoty świadczenia rodzicielskiego (proporcjonalnie za część miesiąca)"),
    "UZ_31_3f": (UZ, "str. 9", "art. 31 ust. 3f – 9 tyg. rodzicielskiego drugiego rodzica zawsze 70%"),
    "UZ_31_3g_4": (UZ, "str. 9", "art. 31 ust. 3g i 4 – brak dnia rodzicielskiego w 1. roku życia: rodzicielski 70% + wyrównanie macierzyńskiego do 100%"),
    "UZ_31_4a": (UZ, "str. 9", "art. 31 ust. 4a – zasiłek zmniejsza się proporcjonalnie do wymiaru pracy przy łączeniu z rodzicielskim"),
    "UZ_36": (UZ, "str. 9", "art. 36 – podstawa: średnia z 12 mies.; przy krótszym ubezpieczeniu – z pełnych miesięcy; 1/30 podstawy za dzień"),
    "UZ_37": (UZ, "str. 9–10", "art. 37 – prawo w 1. miesiącu ubezpieczenia: wynagrodzenie z umowy / uzupełnione"),
    "UZ_38": (UZ, "str. 10", "art. 38 – wyłączanie miesięcy z < połową czasu pracy, uzupełnianie miesięcy z ≥ połową"),
    "UZ_42": (UZ, "str. 10–11", "art. 42 – składniki kwartalne i roczne: 1/12 kwot z 4 kwartałów / roku"),
    "UZ_43": (UZ, "str. 11", "art. 43 – podstawy nie ustala się na nowo przy przerwie między zasiłkami < 1 miesiąca"),
    "UZ_45": (UZ, "str. 11", "art. 45 – minimalna podstawa (pełny etat) = płaca minimalna − 13,71%"),
    "UZ_47": (UZ, "str. 11", "art. 47 – art. 36–42 i 45 stosuje się do zasiłku macierzyńskiego i zasiłku w wysokości zasiłku macierzyńskiego"),
    "UZ_48": (UZ, "str. 11–12", "art. 48–48a – niepracownik: średni przychód z 12 mies.; zadeklarowana podstawa przy krótszym ubezpieczeniu"),
    "UZ_49": (UZ, "str. 12", "art. 49 – niepracownik, prawo w 1. miesiącu: najniższa podstawa / kwota z umowy zlecenia"),
    "UZ_50": (UZ, "str. 12–13", "art. 50 – niepracownik: wyłączanie miesięcy z działalnością < połowy miesiąca"),
    "UZ_52": (UZ, "str. 13", "art. 52 – odesłanie: zasady podstawy niepracownika do zasiłku macierzyńskiego"),
    "UZ_61": (UZ, "str. 19", "art. 61 – kto wypłaca: płatnik > 20 ubezpieczonych; w pozostałych przypadkach (JDG, po ustaniu ubezpieczenia) ZUS"),
    "UZ_61b_4a": (UZ, "str. 21", "art. 61b ust. 4a – do wniosku dołącza się oświadczenie o zaświadczeniu „Za życiem”"),
    # ── Załącznik ZUS ───────────────────────────────────────────────────────
    "ZAL_chor": (ZAL, "sekcja „Zasiłek chorobowy w okresie ciąży”", "tabela: wynagrodzenie chorobowe 33/14 dni, zasiłek chorobowy w ciąży do 270 dni, także po ustaniu ubezpieczenia"),
    "ZAL_mac": (ZAL, "sekcja „Zasiłek macierzyński za okres urlopu macierzyńskiego”", "tabela 20/31/33/35/37 tyg."),
    "ZAL_przyj": (ZAL, "sekcja „…urlopu na warunkach urlopu macierzyńskiego (przyjęcie dziecka na wychowanie)” + „Minimalny okres”", "tabela 20–37 tyg.; nie krócej niż 9 tyg."),
    "ZAL_uzup": (ZAL, "sekcja „…uzupełniającego urlopu macierzyńskiego”", "tabela przypadków 1–6, sumowanie, zaokrąglenie w górę"),
    "ZAL_rodz": (ZAL, "sekcja „Urlop rodzicielski – czas trwania”", "41/43/65/67 tyg., w tym 9 tyg. nieprzenoszalne"),
    "ZAL_ojc": (ZAL, "sekcja „…urlopu ojcowskiego”", "2 tyg., 1 lub 2 części ≥ 1 tydz., do 12 mies. / adopcja"),
    "ZAL_wys": (ZAL, "sekcja „Wysokość zasiłku macierzyńskiego”", "100% / 70% / 81,5% / 9 tyg. drugiego rodzica 70%"),
    "ZAL_podst_prac": (ZAL, "sekcja „Podstawa wymiaru zasiłków – Dla pracowników” (tabele 1–4)", "12 mies. − 13,71%, płaca minimalna 4 806 zł, składniki, uzupełnianie"),
    "ZAL_podst_nieprac": (ZAL, "sekcja „Dla nie pracowników”", "12 mies. przychodu − 13,71%; limit 23 550 zł → 20 321,30 zł"),
    # ── Treść zadania ───────────────────────────────────────────────────────
    "ZAD_s1": (ZAD, "str. 1 (przypis 1)", "zasiłki wypłaca płatnik > 20 ubezpieczonych albo ZUS"),
    "ZAD_s2_4": (ZAD, "str. 2–4", "zasiłek chorobowy dla kobiety w ciąży: e-ZLA z kodem B, 100%, okres zasiłkowy 270 dni"),
    "ZAD_s3": (ZAD, "str. 3", "ubezpieczenie obowiązkowe (umowa o pracę) – prawo po 30 dniach; dobrowolne (zlecenie, JDG) – po 90 dniach"),
    "ZAD_s4": (ZAD, "str. 4", "zasiłek w wysokości zasiłku macierzyńskiego po utracie pracy w ciąży (upadłość, likwidacja, śmierć pracodawcy, naruszenie przepisów + wyrok) – do dnia porodu, 100%"),
    "ZAD_s4_5": (ZAD, "str. 4–5", "zasiłek macierzyński: urlopy, za które przysługuje; te same zasady dla pracowników i niepracowników"),
    "ZAD_s5": (ZAD, "str. 5", "A) 6 tyg. przed porodem, 14 tyg. osobiście przez matkę"),
    "ZAD_s6": (ZAD, "str. 6", "5 części do końca roku 6 r.ż.; martwe urodzenie / zgon dziecka"),
    "ZAD_s7": (ZAD, "str. 7", "B) przejęcie przez ojca; 9 tyg. nieprzenoszalne; rodzicielski dla ojca, gdy matka nieubezpieczona"),
    "ZAD_s8": (ZAD, "str. 8", "ojcowski (także gdy ojciec zaczął pracę po narodzinach); C) uzupełniający; D) przyjęcie na wychowanie"),
    "ZAD_s9": (ZAD, "str. 9", "wiek dziecka przy przyjęciu; E) łączenie z pracą; F) wymiar; G) wysokość 100/70/81,5%"),
    "ZAD_s10": (ZAD, "str. 10", "H) ryzyko: brak ubezpieczenia chorobowego w dniu porodu"),
    # ── Poradnik ZUS 2026 ──────────────────────────────────────────────────
    "POR_15": (POR, "str. 15 (PDF 16)", "JDG: podstawa składek min. 60% prognozowanego przeciętnego wynagrodzenia"),
    "POR_19": (POR, "str. 19 (PDF 20)", "podwyższenie do świadczenia rodzicielskiego liczone od kwoty po zaliczce PIT; łączenie rodzicielskiego z pracą"),
    "POR_23": (POR, "str. 23 (PDF 24)", "wynagrodzenie chorobowe 33/14 dni tylko przy ubezpieczeniu obowiązkowym; kto wypłaca zasiłek chorobowy"),
    "POR_24": (POR, "str. 24 (PDF 25)", "zadłużenie > 1%; okres zasiłkowy 270 dni w ciąży; zasiłek 100% z kodem B; podstawa 12 mies. − 13,71%"),
    "POR_25": (POR, "str. 25 (PDF 26)", "minimalna podstawa przy pełnym etacie; brak nowej podstawy przy przerwie < 1 mies.; podstawa niepracownika"),
    "POR_27": (POR, "str. 27 (PDF 28)", "zasiłek za urlop macierzyński przed porodem – 100%"),
    "POR_29": (POR, "str. 29 (PDF 30)", "warunek: ubezpieczenie chorobowe w dniu powstania prawa do zasiłku macierzyńskiego"),
    "POR_30": (POR, "str. 30 (PDF 31)", "tabela 20–37 tyg.; 14 tyg. dla mamy; urlop na warunkach urlopu macierzyńskiego"),
    "POR_31": (POR, "str. 31 (PDF 32)", "uzupełniający 15/8/8 tyg.; rodzicielski 41/43"),
    "POR_32": (POR, "str. 32 (PDF 33)", "9 tyg. nieprzenoszalne; 5 części; Za życiem 65/67/62; z pracą 130/134; ojcowski"),
    "POR_33": (POR, "str. 33 (PDF 34)", "ojcowski 14 dni; martwe urodzenie; macierzyński przed porodem 100%"),
    "POR_34": (POR, "str. 34 (PDF 35)", "wariant 81,5% vs 100% + 70%; 9 tyg. drugiego rodzica zawsze 70%"),
    "POR_35": (POR, "str. 35 (PDF 36)", "osoby bez ubezpieczenia chorobowego (bezrobotni, studenci, umowa o dzieło) – świadczenie rodzicielskie"),
    # ── Rozporządzenie (dokumenty) ─────────────────────────────────────────
    "ROZ_15_16": (ROZ, "str. 4", "§ 15–16 – dokumenty: zasiłek po ustaniu ubezpieczenia; przyjęcie dziecka na wychowanie"),
    # ── Pliki zespołu ──────────────────────────────────────────────────────
    "JSN_param": (JSN, "sekcja parametry_admin", "kwoty spoza plików ZUS: świadczenie rodzicielskie 1000 zł, becikowe 1000 zł i kryterium 1922 zł, Za życiem 4000 zł"),
    "JSN_zmienne": (JSN, "opisy zmiennych", "opieka_medyczna_od_10_tyg – warunek becikowego i Za życiem; uznanie_ojcostwa – wymagane, gdy rodzice nie są małżeństwem"),
    "KAT_SR7": (KAT, "wniosek SR-7", "świadczenie rodzicielskie (gmina) – dla osób bez prawa do zasiłku macierzyńskiego; wniosek do 3 mies. od urodzenia = za cały okres"),
    "KAT_BECIKOWE": (KAT, "wniosek BECIKOWE", "dochód do 1922 zł/os., opieka medyczna od 10. tyg. ciąży; wniosek do 12 mies. od urodzenia"),
    "KAT_ZAZYCIEM": (KAT, "wniosek ZA-ZYCIEM", "jednorazowe 4000 zł dla dziecka z ciężkim i nieodwracalnym upośledzeniem lub nieuleczalną chorobą; wniosek do 12 mies."),
    "KAT_ZAS55": (KAT, "wniosek ZAS-55", "zasiłek w wysokości zasiłku macierzyńskiego – kobieta w ciąży po utracie pracy"),
    "KAT_ZNP7": (KAT, "wniosek ZNp-7", "świadczenie rehabilitacyjne – po wyczerpaniu zasiłku chorobowego"),
}


def opis_zrodla(klucz: str) -> str:
    """Zamienia klucz źródła na tekst „plik, strona: opis” (do raportów i JSON)."""
    plik, strona, opis = ZRODLA[klucz]
    return f"{plik}, {strona}: {opis}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. PARAMETRY (panel admina – ZUS_-_Pełna_treść_zadania_konkursowego.pdf, str. 14:
#    „możliwość wprowadzania zmian w jego parametrach np. stopy procentowej…”)
# ═══════════════════════════════════════════════════════════════════════════
PARAMETRY_DOMYSLNE: dict[str, Any] = {
    # Procent podstawy – ustawa zasiłkowa str. 9, art. 31 ust. 1–3 i 3f;
    # Załącznik, sekcja „Wysokość zasiłku macierzyńskiego”.
    "zasilek_macierzynski_procent": {
        "macierzynski": 100, "na_warunkach_macierzynskiego": 100, "uzupelniajacy": 100,
        "ojcowski": 100, "rodzicielski": 70, "jednolity_wniosek_21_dni": 81.5,
        "nieprzenoszalne_9_tyg_drugiego_rodzica": 70,
    },
    # Zasiłek chorobowy w ciąży 100% – ustawa zasiłkowa str. 3, art. 11 ust. 2 pkt 1.
    "zasilek_chorobowy_ciaza_procent": 100,
    # Świadczenie rehabilitacyjne w ciąży 100% – ustawa zasiłkowa str. 6, art. 19 ust. 1.
    "swiadczenie_rehabilitacyjne_ciaza_procent": 100,
    "swiadczenie_rehabilitacyjne_max_miesiecy": 12,           # ustawa zasiłkowa str. 5, art. 18 ust. 2
    # Składki 13,71% – ustawa zasiłkowa str. 1–2, art. 3 pkt 3–4.
    "skladki_pomniejszenie_podstawy_procent": 13.71,
    # Okres wyczekiwania – ustawa zasiłkowa str. 2, art. 4 ust. 1; treść zadania str. 3.
    "okres_wyczekiwania_dni": {"obowiazkowe": 30, "dobrowolne": 90},
    "okres_wyczekiwania_przerwa_max_dni": 30,                   # art. 4 ust. 2
    "okres_wyczekiwania_zwolnienie_lat_obowiazkowego": 10,      # art. 4 ust. 3 pkt 3
    # Wynagrodzenie chorobowe – Kodeks pracy str. 1–2, art. 92 § 1.
    "wynagrodzenie_chorobowe_dni": {"standard": 33, "po_50_roku_zycia": 14},
    # Okres zasiłkowy w ciąży – ustawa zasiłkowa str. 3, art. 8 ust. 1.
    "okres_zasilkowy_dni": 270,
    # Płaca minimalna 2026 – Załącznik, sekcja „Minimalna podstawa wymiaru zasiłku w 2026 roku”.
    "placa_minimalna_zl": 4806,
    # Świadczenie rodzicielskie 1000 zł – zmienne_uzytkownika.json, parametry_admin (kwoty nie ma w plikach ZUS).
    "swiadczenie_rodzicielskie_zl_mies": 1000,
    # Limit dobrowolnego chorobowego – Załącznik, sekcja „Dla nie pracowników”.
    "max_podstawa_skladki_chorobowej_dobrowolnej_zl": 23550,
    # 60% prognozowanego przeciętnego wynagrodzenia (Poradnik str. 15) – KWOTA SPOZA PLIKÓW, zweryfikować.
    "jdg_najnizsza_podstawa_zl": 5652.00,
    # Wymiary urlopów – Kodeks pracy str. 3 (art. 180), str. 6 (art. 182¹a), str. 7 (182¹f), str. 8–9 (183).
    "urlop_macierzynski_tyg": {"1": 20, "2": 31, "3": 33, "4": 35, "5+": 37},
    "urlop_macierzynski_min_matka_tyg": 14,                     # art. 180 § 4
    "urlop_macierzynski_min_szczegolne_tyg": 8,                 # art. 180 § 6, 10, 13
    "urlop_macierzynski_przed_porodem_max_tyg": 6,              # art. 180 § 2
    "martwe_urodzenie_tyg": 8,                                  # art. 180¹ § 1
    "martwe_urodzenie_min_dni_od_zgonu": 7,                     # art. 180¹ § 1–2
    "urlop_rodzicielski_tyg": {"1": 41, "mnogi": 43, "za_zyciem_1": 65, "za_zyciem_mnogi": 67},
    "urlop_rodzicielski_art183_par3_tyg": {"zwykly": 38, "za_zyciem": 62},
    "urlop_rodzicielski_nieprzenoszalny_tyg": 9,                # art. 182¹a § 4
    "urlop_rodzicielski_max_czesci": 5,                         # art. 182¹c
    "urlop_rodzicielski_do_konca_roku_wieku_lat": 6,            # art. 182¹c
    "urlop_rodzicielski_praca_max_wymiar": 0.5,                 # art. 182¹e
    "urlop_rodzicielski_z_praca_limit_tyg": {"1": 82, "mnogi": 86, "za_zyciem_1": 130, "za_zyciem_mnogi": 134},
    "urlop_ojcowski_dni": 14,                                   # art. 182³ § 1
    "urlop_ojcowski_min_czesc_dni": 7,                          # art. 182³ § 1¹
    "urlop_ojcowski_max_czesci": 2,
    "urlop_ojcowski_do_miesiaca_zycia": 12,
    "urlop_uzupelniajacy_max_tyg": {                            # art. 180² § 1
        "ponizej_28_tyg_lub_do_1000g": 15,
        "od_28_do_37_tyg_powyzej_1000g_lub_hospitalizacja": 8,
    },
    "na_warunkach_macierzynskiego_min_tyg": 9,                  # art. 183 § 3; Załącznik „Minimalny okres”
    "wiek_limit_lat": {"rodzina_zastepcza": 7, "rodzina_zastepcza_odroczony_obowiazek": 10,
                       "przysposobienie": 14},
    "termin_wniosku_81_5_dni": 21,                              # ustawa zasiłkowa str. 8, art. 30a
    "termin_rozpoczecia_na_warunkach_dni": 21,                  # Kodeks pracy str. 9, art. 183 § 6
    "zadluzenie_prog_procent_placy_min": 1,                     # ustawa zasiłkowa str. 1, art. 2a
    "platnik_wyplaca_prog_ubezpieczonych": 20,                  # ustawa zasiłkowa str. 19, art. 61
    # Świadczenia gminne – zmienne_uzytkownika.json (parametry_admin) i katalog_wnioskow_pdf.json:
    "becikowe_zl": 1000,
    "becikowe_kryterium_zl": 1922,
    "za_zyciem_zl": 4000,
    "termin_wniosku_jednorazowego_miesiecy": 12,                # katalog: BECIKOWE, ZA-ZYCIEM „12 miesięcy od urodzenia”
}

# Tytuły ubezpieczenia (enum tytul_ubezpieczenia z zmienne_uzytkownika.json – wersja zaktualizowana).
TYTULY_PRACOWNIK = {"umowa_o_prace"}
TYTULY_JDG = {"jdg", "wspolpraca_jdg", "duchowny", "marynarz"}
# Bez ubezpieczenia chorobowego w ZUS → bez zasiłków; Poradnik str. 35 wymienia bezrobotnych,
# studentów i umowę o dzieło. „ulga_na_start” – brak obowiązku ubezpieczeń społecznych, więc też brak
# chorobowego (Poradnik str. 24 – mowa o osobach korzystających z ulgi; interpretacja).
TYTULY_BEZ_ZASILKU_ZUS = {"umowa_o_dzielo", "student", "bezrobocie_z_zasilkiem",
                          "bezrobocie_bez_zasilku", "brak", "ulga_na_start", "krus"}


def _scal(baza: dict, nadpis: dict) -> dict:
    wynik = dict(baza)
    for k, v in (nadpis or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(wynik.get(k), dict):
            wynik[k] = _scal(wynik[k], v)
        else:
            wynik[k] = v
    return wynik


def wczytaj_parametry(sciezka_json: str | None = None, nadpis: dict | None = None) -> dict:
    """Parametry domyślne + "parametry_admin" z zmienne_uzytkownika.json + ręczne nadpisanie."""
    P = dict(PARAMETRY_DOMYSLNE)
    if sciezka_json:
        with open(sciezka_json, encoding="utf-8") as f:
            P = _scal(P, json.load(f).get("parametry_admin", {}))
    return _scal(P, nadpis or {})


# ═══════════════════════════════════════════════════════════════════════════
# 3. NARZĘDZIA
# ═══════════════════════════════════════════════════════════════════════════
D = Decimal
BRAK = object()   # znacznik „pola nie ma w danych” (różny od None = „pole jest, wartość pusta”)


def zl(x: Any) -> Decimal:
    """Zaokrąglenie do grosza (połówki w górę)."""
    return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def data(x: Any) -> date | None:
    """'2026-11-21' → date; None/'' → None."""
    if x is None or x == "" or x is BRAK:
        return None
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def urodziny(data_ur: date, lat: int) -> date:
    """Dzień ukończenia `lat` lat (29 lutego → 1 marca)."""
    try:
        return data_ur.replace(year=data_ur.year + lat)
    except ValueError:
        return date(data_ur.year + lat, 3, 1)


def dodaj_miesiace(d: date, n: int) -> date:
    m = d.month - 1 + n
    r, m = d.year + m // 12, m % 12 + 1
    for dzien in (d.day, 30, 29, 28):
        try:
            return date(r, m, dzien)
        except ValueError:
            continue
    raise ValueError(d)


def pole(dane: dict, klucz: str) -> Any:
    """Odczyt pola po kluczu z kropkami ('urlop_macierzynski.tygodnie_przed_porodem').
    Zwraca BRAK, gdy pola nie ma."""
    v: Any = dane
    for czesc in klucz.split("."):
        if isinstance(v, dict) and czesc in v:
            v = v[czesc]
        else:
            return BRAK
    return v


def tydzien(dni: int) -> float:
    return round(dni / 7, 2)


def koniec(od: date, dni: int) -> date:
    """Ostatni dzień okresu `dni` dni zaczynającego się `od` (włącznie)."""
    return od + timedelta(days=dni - 1)


# Pola liczbowe schematu – przy danych z formularza mogą przyjść jako tekst ("1", "0,5").
POLA_LICZBOWE = {
    "liczba_dzieci_przy_porodzie", "okres_zasilkowy_wykorzystany_dni", "platnik_liczba_ubezpieczonych_chorobowo",
    "wymiar_etatu", "dochod_na_osobe", "tydzien_ciazy_przy_urodzeniu", "masa_urodzeniowa_g", "podstawa_wymiaru_skladek",
    "kwota", "dni_przepracowane", "dni_do_przepracowania", "wymiar_pracy_w_trakcie", "tygodnie_przed_porodem",
    "rok", "miesiac", "wymiar_tyg", "dochody_opodatkowane", "dochody_nieopodatkowane", "dochody_utracone",
    "dochody_uzyskane",
}


def normalizuj_dane(x: Any, klucz: str | None = None) -> Any:
    """Ujednolica dane z formularza, zanim trafią do reguł:
      "true"/"false" → True/False,  "" → None,  liczba w tekście w polu liczbowym → int/float ("0,5" → 0.5).
    PESEL, NIP itp. zostają tekstem (nie są w POLA_LICZBOWE). Funkcja nie zmienia oryginalnego słownika."""
    if isinstance(x, dict):
        return {k: normalizuj_dane(v, k) for k, v in x.items()}
    if isinstance(x, list):
        return [normalizuj_dane(v, klucz) for v in x]
    if isinstance(x, str):
        t = x.strip()
        if t == "":
            return None
        if t.lower() in ("true", "false"):
            return t.lower() == "true"
        if klucz in POLA_LICZBOWE:
            try:
                f = float(t.replace(",", "."))
                return int(f) if f.is_integer() and not any(c in t for c in ".,") else f
            except ValueError:
                return x
    return x
