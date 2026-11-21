#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalkulator_zasilku.py
=====================
Kalkulator świadczeń – HackNation 2026, wyzwanie ZUS „Zasiłkowy Przewodnik Przyszłego Rodzica”.

DWA SPOSOBY UŻYCIA
  1) oblicz_wszystkie_swiadczenia(dane_uzytkownika)  ← główny punkt wejścia
     Bierze wszystkie dane użytkownika (płaski słownik z kluczami jak w zmienne_uzytkownika.json),
     dla KAŻDEGO świadczenia z katalogu uruchamia sprawdzenie z modułu sprawdzanie_swiadczen.py
     i zwraca jeden z komunikatów:
       • WARNING: {świadczenie} – brakuje danych: pole1, pole2…
       • Można uzyskać: {świadczenie}: {kwota} zł/miesiąc, okres: {od} – {do}             (wypłata co miesiąc)
       • Można uzyskać: {świadczenie}: {kwota} zł/jednorazowo, okres na wniosek: {od} – {do} (inny przedział)
       • Można uzyskać: {świadczenie} (urlop): {kwota} zł/mies. (podstawa × %) na okres {od} – {do}
       • Nie masz możliwości uzyskania: {świadczenie} – {powód}
  2) kalkulatory scenariuszowe b, c, d, e, f, j (podpunkty z treści zadania, str. 13) – szczegółowe
     symulacje dla obojga rodziców, łączenia z pracą, adopcji itd.

PLIKI ŹRÓDŁOWE (w komentarzach podaję nazwę pliku i stronę):
  Kodeks_pracy_wyciąg_z_przepisów.pdf
  wyciąg_z_ustawy_o_świadczeniach_pieniężnych_…_ustawa_zasiłkowa.pdf   (dalej: „ustawa zasiłkowa”)
  Załącznik__maksymalny_czas_trwania_zasiłków__wysokość__podstawa_wymiaru.docx  (dalej: „Załącznik”; bez stron – sekcje)
  ZUS_-_Pełna_treść_zadania_konkursowego.pdf                              (dalej: „treść zadania”)
  Poradnik_dla_rodziców_ZUS_2026.pdf  (numer wydrukowany na stronie; w nawiasie numer strony PDF)
  rozporządzenie_w_spr__zakresu_informacji_…pdf, zmienne_uzytkownika.json, katalog_wnioskow_pdf.json

KONWENCJE OBLICZEŃ
  • Kwoty BRUTTO (przed zaliczką PIT) – Poradnik str. 24 (PDF 25): zasiłek pomniejsza się jeszcze o PIT.
  • Zasiłek miesięczny = podstawa × procent (ustawa zasiłkowa str. 9, art. 31 ust. 1–3).
  • Stawka dzienna = zasiłek miesięczny / 30 (ustawa zasiłkowa str. 9, art. 36 ust. 3, stosowany do zasiłku
    macierzyńskiego przez art. 47 i 52, str. 11 i 13); kwota za okres = stawka dzienna × liczba dni.
  • Zaokrąglanie do grosza na każdym kroku – konwencja (przepisy w plikach jej nie określają).
  • Tydzień urlopu = 7 dni kalendarzowych; 1. dzień urlopu po porodzie = dzień porodu
    (Kodeks pracy str. 9, art. 183¹).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

# Import działa w obu trybach: jako pakiet (np. z backendu: from scripts.calc.kalkulator_zasilku import …)
# i z katalogu calc (skrypty i testy obok).
try:
    from .sprawdzanie_swiadczen import (Status, WynikSprawdzenia, granica_wieku_przyjecia,
                                   limit_z_praca_tyg, oblicz_uzupelniajacy, rola_wnioskodawcy,
                                   sprawdz_wszystkie, wymiar_macierzynskiego_tyg, wymiar_rodzicielskiego_tyg)
    from .zrodla_i_parametry import (BRAK, PARAMETRY_DOMYSLNE, TYTULY_BEZ_ZASILKU_ZUS, TYTULY_JDG, TYTULY_PRACOWNIK,
                                ZRODLA, D, data, dodaj_miesiace, normalizuj_dane, pole, urodziny, zl)
except ImportError:
    from sprawdzanie_swiadczen import (Status, WynikSprawdzenia, granica_wieku_przyjecia,
                                   limit_z_praca_tyg, oblicz_uzupelniajacy, rola_wnioskodawcy,
                                   sprawdz_wszystkie, wymiar_macierzynskiego_tyg, wymiar_rodzicielskiego_tyg)
    from zrodla_i_parametry import (BRAK, PARAMETRY_DOMYSLNE, TYTULY_BEZ_ZASILKU_ZUS, TYTULY_JDG, TYTULY_PRACOWNIK,
                                ZRODLA, D, data, dodaj_miesiace, normalizuj_dane, pole, urodziny, zl)


# ═══════════════════════════════════════════════════════════════════════════
# 1. STAWKA ZASIŁKU – wzór wspólny dla wszystkich świadczeń
# ═══════════════════════════════════════════════════════════════════════════
def _pct(P: dict, klucz: str) -> Decimal:
    """Procent podstawy z parametrów (zasilek_macierzynski_procent)."""
    return D(str(P["zasilek_macierzynski_procent"][klucz]))


def _wspolczynnik_netto(P: dict) -> Decimal:
    """1 − 13,71% = 0,8629 – część podstawy składek, która zostaje po odliczeniu składek
    emerytalnej, rentowej i chorobowej (ustawa zasiłkowa str. 1–2, art. 3 pkt 3–4)."""
    return 1 - D(str(P["skladki_pomniejszenie_podstawy_procent"])) / 100


def stawka_dzienna(podstawa: Decimal, procent: Decimal | float, P: dict,
                   wymiar_pracy: Fraction | float = 0,
                   minimum_swiadczenia_rodzicielskiego: bool = True) -> tuple[Decimal, Decimal, list[str]]:
    """Zwraca (stawka dzienna, kwota za pełny miesiąc, uwagi).

    KROK 1 – kwota miesięczna = podstawa × procent / 100
             (ustawa zasiłkowa str. 9, art. 31 ust. 1–3 – zasiłek macierzyński;
              str. 3, art. 11 ust. 2 – zasiłek chorobowy w ciąży 100%;
              str. 6, art. 19 ust. 1 – świadczenie rehabilitacyjne w ciąży 100%).
    KROK 2 – tylko zasiłek macierzyński: jeśli kwota < kwota świadczenia rodzicielskiego (1000 zł),
             podwyższa się ją do tej kwoty (ustawa zasiłkowa str. 9, art. 31 ust. 3a). Kwota 1000 zł
             pochodzi z zmienne_uzytkownika.json (parametry_admin) – w plikach ZUS jej nie ma.
             Poradnik str. 19 (PDF 20) porównuje kwotę PO zaliczce PIT; tu – od brutto (litera ustawy).
    KROK 3 – łączenie rodzicielskiego z pracą: kwota × (1 − wymiar pracy)
             (ustawa zasiłkowa str. 9, art. 31 ust. 4a). Podwyższenie z kroku 2 stosuję PRZED
             zmniejszeniem – kolejności przepisy nie rozstrzygają (interpretacja).
    KROK 4 – stawka dzienna = kwota miesięczna / 30, do grosza
             (ustawa zasiłkowa str. 9, art. 36 ust. 3; str. 3, art. 11 ust. 5 – miesiąc = 30 dni)."""
    uwagi: list[str] = []
    miesieczna = podstawa * D(str(procent)) / 100                          # KROK 1
    if minimum_swiadczenia_rodzicielskiego:                                 # KROK 2
        minimum = D(str(P["swiadczenie_rodzicielskie_zl_mies"]))
        if miesieczna < minimum:
            uwagi.append(f"Kwota {zl(miesieczna)} zł < świadczenie rodzicielskie – podwyższono do {zl(minimum)} zł "
                         "(ustawa zasiłkowa art. 31 ust. 3a).")
            miesieczna = minimum
    if wymiar_pracy:                                                        # KROK 3
        miesieczna = miesieczna * (1 - D(str(float(wymiar_pracy))))
    return zl(miesieczna / 30), zl(miesieczna), uwagi                      # KROK 4


# ═══════════════════════════════════════════════════════════════════════════
# 2. PODSTAWA WYMIARU ZASIŁKU (podpunkt f) – używana przez wszystkie świadczenia
# ═══════════════════════════════════════════════════════════════════════════
class BrakDanych(ValueError):
    """Brak danych potrzebnych do obliczenia – `pole` to nazwa pola ze schematu zmienne_uzytkownika.json."""

    def __init__(self, pole: str, opis: str = ""):
        super().__init__(opis or f"brak danych: {pole}")
        self.pole = pole


def oblicz_podstawe(osoba: dict, P: dict) -> dict:
    """Ustala podstawę wymiaru zasiłku. `osoba` to dane w formacie zmienne_uzytkownika.json:
      tytul_ubezpieczenia, ubezpieczenie_chorobowe, wymiar_etatu,
      podstawa_wymiaru_12_miesiecy: [{rok, miesiac, podstawa_wymiaru_skladek, dni_przepracowane,
                                      dni_do_przepracowania}],
      zadeklarowana_podstawa_jdg: [{rok, miesiac, kwota}].
    Pola dodatkowe spoza schematu (opcjonalne): podstawa (gotowa kwota), podstawa_poprzedniego_zasilku
    + przerwa_krotsza_niz_miesiac, premie_kwartalne_4_kwartaly, premie_roczne_rok_poprzedni,
    wynagrodzenie_umowne, data_powstania_prawa (miesiąc, od którego liczymy 12 wstecz),
    oraz w miesiącu: kwota_po_uzupelnieniu | skladniki_stale_umowne, skladniki_zmienne, skladniki_nieuzupelniane."""
    zr: list[str] = []
    ostrz: list[str] = []
    wn = _wspolczynnik_netto(P)

    # ŚCIEŻKA 0 – gotowa podstawa podana z zewnątrz (np. odczytana z decyzji ZUS).
    if osoba.get("podstawa") is not None:
        return {"podstawa": zl(osoba["podstawa"]), "metoda": "podana przez użytkownika",
                "miesiace": [], "zrodla": zr, "ostrzezenia": ostrz}

    # ŚCIEŻKA 1 – ta sama podstawa co poprzedni zasiłek, jeśli przerwa między zasiłkami < 1 miesiąca
    # (ustawa zasiłkowa str. 11, art. 43; Poradnik str. 25 (PDF 26)). Typowo: zasiłek chorobowy
    # w ciąży trwa do porodu → zasiłek macierzyński liczy się od tej samej podstawy.
    if osoba.get("podstawa_poprzedniego_zasilku") is not None and osoba.get("przerwa_krotsza_niz_miesiac"):
        zr += ["UZ_43", "POR_25"]
        ostrz.append("Przyjęto podstawę poprzedniego zasiłku, bo przerwa < 1 mies. (ustawa zasiłkowa art. 43). "
                     "Wyjątek: zmiana wymiaru czasu pracy między zasiłkami (Poradnik str. 25).")
        return {"podstawa": zl(osoba["podstawa_poprzedniego_zasilku"]),
                "metoda": "art. 43 – podstawa poprzedniego zasiłku", "miesiace": [], "zrodla": zr, "ostrzezenia": ostrz}

    tytul = osoba.get("tytul_ubezpieczenia", "umowa_o_prace")
    pracownik = tytul in TYTULY_PRACOWNIK
    granica = data(osoba.get("data_powstania_prawa"))

    # Wybór miesięcy: 12 miesięcy kalendarzowych POPRZEDZAJĄCYCH miesiąc powstania prawa
    # (ustawa zasiłkowa str. 9, art. 36 ust. 1 – pracownik; str. 11, art. 48 ust. 1 – niepracownik).
    def wybierz(lista: list[dict]) -> list[dict]:
        lista = sorted(lista or [], key=lambda m: (int(m["rok"]), int(m["miesiac"])))
        if granica:
            lista = [m for m in lista if (int(m["rok"]), int(m["miesiac"])) < (granica.year, granica.month)]
        lista = lista[-12:]
        # Dane kończą się wcześniej niż miesiąc przed powstaniem prawa (np. poród w przyszłości) → prognoza.
        if granica and lista:
            ost = (int(lista[-1]["rok"]), int(lista[-1]["miesiac"]))
            oczek = (granica.year, granica.month - 1) if granica.month > 1 else (granica.year - 1, 12)
            if ost < oczek:
                ostrz.append(f"Ostatni podany miesiąc to {ost[1]:02d}.{ost[0]}, a do podstawy wchodzi 12 mies. przed "
                             f"{granica.month:02d}.{granica.year} – policzono z dostępnych miesięcy (prognoza).")
        return lista

    miesiace_out: list[dict] = []

    # ── ŚCIEŻKA 2 – JDG / osoba z zadeklarowaną podstawą składek ──────────
    if not pracownik and osoba.get("zadeklarowana_podstawa_jdg"):
        zr += ["UZ_48", "UZ_52", "UZ_3", "ZAL_podst_nieprac", "POR_15"]
        mies = wybierz(osoba["zadeklarowana_podstawa_jdg"])
        najn_def = D(str(P["jdg_najnizsza_podstawa_zl"]))
        cap = D(str(P["max_podstawa_skladki_chorobowej_dobrowolnej_zl"]))
        if not mies:
            # Prawo w 1. miesiącu ubezpieczenia: najniższa podstawa − 13,71% (ustawa zasiłkowa str. 12, art. 49 ust. 1 pkt 1).
            zr.append("UZ_49")
            return {"podstawa": zl(najn_def * wn), "metoda": "art. 49 – najniższa podstawa", "miesiace": [],
                    "zrodla": zr, "ostrzezenia": ["Brak pełnego miesiąca ubezpieczenia – najniższa podstawa (art. 49)."]}
        for m in mies:
            # Limit podstawy dobrowolnego chorobowego 23 550 zł (Załącznik, sekcja „Dla nie pracowników”).
            kw = min(D(str(m["kwota"])), cap)
            najn = D(str(m.get("najnizsza_podstawa", najn_def)))
            miesiace_out.append({"rok": m["rok"], "miesiac": m["miesiac"], "zadeklarowana": kw, "najnizsza": najn,
                                 "netto": zl(kw * wn), "status": "uwzględniony"})
        n = len(miesiace_out)
        if n >= 12:
            # Wzór: podstawa = średnia z 12 mies. (zadeklarowana kwota × 0,8629) – art. 48 ust. 1, art. 3 pkt 4.
            podst = zl(sum(m["netto"] for m in miesiace_out) / n)
            metoda = "art. 48 – średni przychód z 12 miesięcy"
        else:
            # Wzór przy krótszym ubezpieczeniu (ustawa zasiłkowa str. 11, art. 48a ust. 1):
            #   podstawa = śr. najniższa podstawa × 0,8629
            #            + (1/12) × śr. nadwyżka (zadeklarowana − najniższa) × 0,8629 × liczba pełnych miesięcy
            sr_najn = sum(zl(m["najnizsza"] * wn) for m in miesiace_out) / n
            sr_nadw = sum(zl(max(D(0), m["zadeklarowana"] - m["najnizsza"]) * wn) for m in miesiace_out) / n
            podst = zl(sr_najn + sr_nadw * n / 12)
            metoda = f"art. 48a – {n} pełnych mies.: śr. najniższa podstawa + 1/12 śr. nadwyżki × {n}"
            ostrz.append("Najniższa podstawa JDG (5 652 zł = 60% prognozowanego przeciętnego wynagrodzenia – "
                         "Poradnik str. 15) nie jest podana kwotowo w plikach – zweryfikuj jdg_najnizsza_podstawa_zl.")
        if any(D(str(m["kwota"])) > cap for m in mies):
            ostrz.append(f"Część zadeklarowanych kwot przekraczała limit {cap} zł – przycięto.")
        return {"podstawa": podst, "metoda": metoda, "miesiace": miesiace_out, "zrodla": zr, "ostrzezenia": ostrz}

    # ── ŚCIEŻKA 3 – pracownik / zleceniobiorca: przychody z 12 miesięcy ─────
    mies = wybierz(osoba.get("podstawa_wymiaru_12_miesiecy", []))
    if pracownik:
        zr += ["UZ_36", "UZ_38", "UZ_47", "UZ_3", "ZAL_podst_prac", "POR_24"]
    else:
        zr += ["UZ_48", "UZ_50", "UZ_52", "UZ_3", "ZAL_podst_nieprac", "POR_25"]

    if not mies:
        # Prawo w 1. miesiącu ubezpieczenia: wynagrodzenie z umowy − 13,71%
        # (pracownik: ustawa zasiłkowa str. 9–10, art. 37; zleceniobiorca: str. 12, art. 49 ust. 1 pkt 2).
        if osoba.get("wynagrodzenie_umowne") is None:
            raise BrakDanych("podstawa_wymiaru_12_miesiecy",
                             "brak miesięcy w podstawa_wymiaru_12_miesiecy sprzed miesiąca powstania prawa")
        zr.append("UZ_37" if pracownik else "UZ_49")
        podst = zl(D(str(osoba["wynagrodzenie_umowne"])) * wn)
        return _minimum(podst, osoba, P, pracownik, zr,
                        ["Brak pełnego miesiąca ubezpieczenia – podstawa z wynagrodzenia z umowy (art. 37/49)."],
                        "art. 37/49 – wynagrodzenie z umowy", [])

    cap = D(str(P["max_podstawa_skladki_chorobowej_dobrowolnej_zl"]))
    dobrowolne = osoba.get("ubezpieczenie_chorobowe") == "dobrowolne"
    przyciete = False
    for m in mies:
        brutto = D(str(m["podstawa_wymiaru_skladek"]))
        if not pracownik and dobrowolne and brutto > cap:      # limit 23 550 zł (Załącznik „Dla nie pracowników”)
            brutto, przyciete = cap, True
        dp, dd = m.get("dni_przepracowane"), m.get("dni_do_przepracowania")
        status, kwota = "uwzględniony", brutto
        if dd and dp is not None and D(str(dp)) * 2 < D(str(dd)):
            # Miesiąc z < połową czasu pracy → WYŁĄCZONY (ustawa zasiłkowa str. 10, art. 38 ust. 2 pkt 1;
            # niepracownik – str. 12, art. 50 ust. 1 pkt 1; Załącznik tabela 4; Poradnik str. 24).
            status = "wyłączony (< połowy czasu pracy / działalności)"
        elif dd and dp is not None and D(str(dp)) < D(str(dd)) and pracownik:
            # Miesiąc z ≥ połową czasu pracy → UZUPEŁNIONY (art. 38 ust. 2 pkt 2 + art. 37 ust. 2, str. 10):
            #   składniki stałe – pełna kwota z umowy;
            #   składniki zmienne – kwota / dni przepracowane × dni do przepracowania (Załącznik tabela 4).
            if m.get("kwota_po_uzupelnieniu") is not None:
                kwota = D(str(m["kwota_po_uzupelnieniu"]))
            elif m.get("skladniki_stale_umowne") is not None:
                kwota = (D(str(m["skladniki_stale_umowne"]))
                         + D(str(m.get("skladniki_zmienne", 0))) / D(str(dp)) * D(str(dd))
                         + D(str(m.get("skladniki_nieuzupelniane", 0))))
            else:
                kwota = brutto / D(str(dp)) * D(str(dd))
            status = f"uzupełniony ({dp}/{dd} dni)"
            zr.append("UZ_37")
        # Każdy miesiąc po odliczeniu składek: kwota × (1 − 13,71%) (art. 3 pkt 3–4, str. 1–2).
        miesiace_out.append({"rok": m["rok"], "miesiac": m["miesiac"], "brutto": zl(brutto),
                             "kwota_do_podstawy": zl(kwota), "netto": zl(kwota * wn), "status": status})

    uwzgl = [m for m in miesiace_out if not m["status"].startswith("wyłączony")]
    if not uwzgl:
        # Wszystkie miesiące < połowy → bierzemy wszystkie (po uzupełnieniu): art. 38 ust. 3 / art. 50 ust. 2.
        ostrz.append("We wszystkich miesiącach < połowy czasu pracy – przyjęto wszystkie (art. 38 ust. 3 / art. 50 ust. 2).")
        for m, src in zip(miesiace_out, mies):
            dp, dd = src.get("dni_przepracowane") or 0, src.get("dni_do_przepracowania") or 0
            if pracownik and dp and dd:
                m["kwota_do_podstawy"] = zl(D(str(src["podstawa_wymiaru_skladek"])) / D(str(dp)) * D(str(dd)))
                m["netto"] = zl(m["kwota_do_podstawy"] * wn)
            m["status"] = "uwzględniony (art. 38 ust. 3)"
        uwzgl = miesiace_out
    # Wzór: podstawa = suma(netto uwzględnionych miesięcy) / liczba tych miesięcy
    # (ustawa zasiłkowa str. 10, art. 38 ust. 1; przy krótszym ubezpieczeniu – pełne miesiące, art. 36 ust. 2).
    srednia = sum(m["netto"] for m in uwzgl) / len(uwzgl)
    if len(mies) < 12:
        ostrz.append(f"Podano {len(mies)} mies. – średnia z pełnych miesięcy ubezpieczenia (art. 36 ust. 2).")
    if any(m["status"] != "uwzględniony" for m in miesiace_out):
        zr.append("UZ_43")
        ostrz.append("Są miesiące niepełne/wyłączone. Jeśli tuż przed świadczeniem był inny zasiłek (przerwa < 1 mies.), "
                     "podstawa jest taka jak tamtego zasiłku (ustawa zasiłkowa art. 43) – podaj podstawa_poprzedniego_zasilku.")
    # Premie kwartalne / roczne: + 1/12 kwot z 4 kwartałów / z roku (ustawa zasiłkowa str. 10–11, art. 42 ust. 2–3;
    # Załącznik tabela 3), po odliczeniu 13,71%.
    dodatki = D(0)
    for k in ("premie_kwartalne_4_kwartaly", "premie_roczne_rok_poprzedni"):
        if osoba.get(k):
            dodatki += D(str(osoba[k])) / 12 * wn
            zr.append("UZ_42")
    if przyciete:
        ostrz.append(f"Przycięto miesięczne podstawy do limitu {cap} zł (Załącznik „Dla nie pracowników”).")
    return _minimum(zl(srednia + dodatki), osoba, P, pracownik, zr, ostrz,
                    f"średnia z {len(uwzgl)} mies. (−13,71%)" + (" + 1/12 premii" if dodatki else ""), miesiace_out)


def _minimum(podst: Decimal, osoba: dict, P: dict, pracownik: bool, zr: list, ostrz: list,
             metoda: str, miesiace: list) -> dict:
    """Minimalna podstawa – tylko pracownik na PEŁNYM etacie:
    płaca minimalna × (1 − 13,71%) = 4 806 × 0,8629 = 4 147,10 zł
    (ustawa zasiłkowa str. 11, art. 45 ust. 1; Załącznik pkt 2; Poradnik str. 25 (PDF 26))."""
    if pracownik:
        minimum = zl(D(str(P["placa_minimalna_zl"])) * _wspolczynnik_netto(P))
        etat = float(osoba.get("wymiar_etatu") or 1.0)
        if etat >= 1.0 and podst < minimum:
            zr += ["UZ_45", "POR_25"]
            ostrz.append(f"Podstawa {podst} zł podniesiona do minimum {minimum} zł (ustawa zasiłkowa art. 45).")
            podst, metoda = minimum, metoda + " → minimum z art. 45"
        elif etat < 1.0:
            ostrz.append("Niepełny etat: art. 45 (minimalna podstawa) dotyczy tylko pełnego wymiaru – nie zastosowano.")
    return {"podstawa": podst, "metoda": metoda, "miesiace": miesiace,
            "zrodla": list(dict.fromkeys(zr)), "ostrzezenia": ostrz}


def kto_wyplaca(osoba: dict, P: dict) -> str:
    """Kto wypłaca zasiłek: płatnik, który zgłasza > 20 ubezpieczonych; w pozostałych przypadkach
    (≤ 20 ubezpieczonych, JDG, po ustaniu ubezpieczenia) – ZUS
    (ustawa zasiłkowa str. 19, art. 61; treść zadania str. 1, przypis 1; Poradnik str. 23 (PDF 24))."""
    tytul = osoba.get("tytul_ubezpieczenia", "umowa_o_prace")
    if tytul in TYTULY_JDG or osoba.get("ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia") is False:
        return "ZUS"
    if isinstance(osoba.get("platnik_wyplaca_zasilki"), bool):
        return "płatnik składek (pracodawca/zleceniodawca)" if osoba["platnik_wyplaca_zasilki"] else "ZUS"
    n = osoba.get("platnik_liczba_ubezpieczonych_chorobowo")
    if n is None:
        return "płatnik (> 20 ubezpieczonych) albo ZUS (≤ 20) – podaj platnik_liczba_ubezpieczonych_chorobowo"
    return "płatnik składek (pracodawca/zleceniodawca)" if n > P["platnik_wyplaca_prog_ubezpieczonych"] else "ZUS"


# ═══════════════════════════════════════════════════════════════════════════
# 3. REGUŁY OKRESÓW WSPÓLNE DLA KALKULATORÓW
# ═══════════════════════════════════════════════════════════════════════════
def macierzynski_po_porodzie(dzieci: list[dict], data_porodu: date, przed_dni: int, n: int,
                             P: dict) -> tuple[int, int, list[str], list[str]]:
    """Liczba dni urlopu macierzyńskiego PO porodzie → (dni, dzieci żyjące, uwagi, źródła).

    Standard: wymiar (20–37 tyg.) × 7 − dni wykorzystane przed porodem
      (Kodeks pracy str. 3, art. 180 § 1–3).
    Martwe urodzenie lub zgon dziecka (pola dziecko.urodzone_zywe, dziecko.data_zgonu):
      – zgon przed upływem 8 tyg. życia / martwe urodzenie → 8 tyg. po porodzie, nie krócej niż 7 dni od zgonu,
      – zgon po 8 tyg. → 7 dni od zgonu,
      – przy wieloraczkach → wymiar wg liczby dzieci żyjących, nie krócej niż 7 dni od zgonu
      (Kodeks pracy str. 5, art. 180¹; treść zadania str. 6; Poradnik str. 33 (PDF 34))."""
    standard_koniec = data_porodu + timedelta(days=wymiar_macierzynskiego_tyg(n, P) * 7 - przed_dni - 1)
    zgony = []
    for c in dzieci or []:
        if c.get("urodzone_zywe") is False:
            zgony.append(data_porodu)
        elif c.get("data_zgonu"):
            zgony.append(data(c["data_zgonu"]))
    if not zgony:
        return (standard_koniec - data_porodu).days + 1, n, [], []
    zr = ["KP_1801", "ZAD_s6", "POR_33"]
    n_zywe = n - len(zgony)
    ostatni = max(zgony)
    min_dni = int(P["martwe_urodzenie_min_dni_od_zgonu"])
    osiem = data_porodu + timedelta(days=int(P["martwe_urodzenie_tyg"]) * 7 - 1)
    if n_zywe <= 0:
        koniec = max(osiem, ostatni + timedelta(days=min_dni)) if ostatni <= osiem else ostatni + timedelta(days=min_dni)
        uw = ["Martwe urodzenie / zgon dziecka: 8 tyg. po porodzie, nie krócej niż 7 dni od zgonu; "
              "po 8. tyg. życia – 7 dni od zgonu (Kodeks pracy art. 180¹)."]
    else:
        koniec = max(data_porodu + timedelta(days=wymiar_macierzynskiego_tyg(n_zywe, P) * 7 - przed_dni - 1),
                     ostatni + timedelta(days=min_dni))
        uw = [f"Zgon {len(zgony)} z {n} dzieci: wymiar wg liczby dzieci żyjących ({n_zywe}), "
              "nie krócej niż 7 dni od zgonu (Kodeks pracy art. 180¹)."]
    koniec = min(koniec, standard_koniec)                       # nie dłużej niż standardowy wymiar
    return max(0, (koniec - data_porodu).days + 1), max(0, n_zywe), uw, zr


def wymiar_przyjecia(dziecko_ur: date, rodzaj: str, odroczony: bool, n: int, za_zyciem: bool,
                     start: date, P: dict) -> dict:
    """Wymiar urlopów przy przyjęciu dziecka na wychowanie.

    KROK 1 – wymiar urlopu na warunkach urlopu macierzyńskiego jak przy porodzie (20/31/33/35/37 tyg.)
             (Kodeks pracy str. 8, art. 183 § 1 i § 1¹; Załącznik, tabela „przyjęcie dziecka”).
    KROK 2 – nie dłużej niż do dnia przed ukończeniem przez dziecko 7 lat (10 przy odroczeniu
             obowiązku szkolnego) – rodzina zastępcza; 14 lat – przysposobienie (te same przepisy).
             „Ostatni dzień = dzień przed urodzinami” – interpretacja.
    KROK 3 – minimum 9 tygodni (Kodeks pracy str. 8, art. 183 § 3; Załącznik „Minimalny okres”).
             Gdy działa to minimum, przyjmuję „przypadek z § 3”, w którym rodzicielski wynosi
             38 tyg. (Za życiem 62) – art. 183 § 4 pkt 3, § 4², § 4³ pkt 3, § 4⁵ (str. 8–9) – interpretacja.
    KROK 4 – rodzicielski 41/43 (Za życiem 65/67); przy przysposobieniu nie dłużej niż do 14 r.ż.
             (Kodeks pracy str. 8–9, art. 183 § 4 i § 4¹; Poradnik str. 32)."""
    wiek = granica_wieku_przyjecia(rodzaj, odroczony, P)
    granica = urodziny(dziecko_ur, wiek)
    std = wymiar_macierzynskiego_tyg(n, P) * 7                                  # KROK 1
    wym = min(std, (granica - start).days)                                      # KROK 2
    par3 = False
    if wym < int(P["na_warunkach_macierzynskiego_min_tyg"]) * 7:               # KROK 3
        wym, par3 = int(P["na_warunkach_macierzynskiego_min_tyg"]) * 7, True
    t3 = P["urlop_rodzicielski_art183_par3_tyg"]
    R = int(t3["za_zyciem"] if za_zyciem else t3["zwykly"]) if par3 else wymiar_rodzicielskiego_tyg(n, za_zyciem, P)
    R_dni = R * 7                                                               # KROK 4
    if rodzaj == "przysposobienie" and not par3:
        R_dni = max(0, min(R_dni, (granica - (start + timedelta(days=wym))).days))
    return {"wiek_limit": wiek, "granica": granica, "na_warunkach_dni": wym, "skrocony": wym < std and not par3,
            "par3": par3, "R_tyg": R, "R_dni": R_dni}


# ═══════════════════════════════════════════════════════════════════════════
# 4. GŁÓWNY PUNKT WEJŚCIA – wszystkie świadczenia dla danych użytkownika
# ═══════════════════════════════════════════════════════════════════════════
class _KalkulatorOsoby:
    """Liczy kwotę i okres dla świadczeń, które przeszły sprawdzenie (Status.SPELNIA).
    Okresy urlopów układa po kolei: macierzyński → uzupełniający → rodzicielski
    (Kodeks pracy str. 5, art. 180² § 1 – uzupełniający bezpośrednio po macierzyńskim)."""

    def __init__(self, dane: dict, P: dict, dzis: date):
        self.dane, self.P, self.dzis = dane, P, dzis
        self.cache: dict = {}
        self.os: dict = {}            # oś czasu: końce wcześniejszych urlopów tego użytkownika

    # ── pomocnicze ─────────────────────────────────────────────────────────
    def pole(self, k: str) -> Any:
        return pole(self.dane, k)

    def podstawa(self, data_prawa: date) -> tuple[Decimal, dict]:
        """Podstawa z 12 miesięcy poprzedzających miesiąc powstania prawa (oblicz_podstawe)."""
        klucz = (data_prawa.year, data_prawa.month)
        if klucz not in self.cache:
            osoba = dict(self.dane)
            osoba["data_powstania_prawa"] = data_prawa
            self.cache[klucz] = oblicz_podstawe(osoba, self.P)
        r = self.cache[klucz]
        return r["podstawa"], r

    def _przed(self) -> int:
        """Tygodnie urlopu macierzyńskiego przed porodem (urlop_macierzynski.tygodnie_przed_porodem), max 6
        (Kodeks pracy str. 3, art. 180 § 2)."""
        v = self.pole("urlop_macierzynski.tygodnie_przed_porodem")
        return min(int(v or 0) if v is not BRAK else 0, int(self.P["urlop_macierzynski_przed_porodem_max_tyg"]))

    def _wynik(self, kwota: Decimal, jednostka: str, od: date, do: date, *, procent=None, podstawa=None,
               dzienna=None, wzor: str = "", zrodla: list | None = None, uwagi: list | None = None,
               podst_info: dict | None = None, kwota_laczna: Decimal | None = None,
               dni: int | None = None) -> dict:
        # dni = liczba dni płatnych; domyślnie cały okres od–do. Przy planie z przerwami między częściami
        # (czesci_urlopu_rodzicielskiego) dni płatnych jest mniej niż dni kalendarzowych od–do.
        dni = dni if dni is not None else (do - od).days + 1
        rec = {"kwota": kwota, "jednostka": jednostka, "okres_od": od, "okres_do": do, "dni": dni,
               "procent": float(procent) if procent is not None else None, "podstawa": podstawa,
               "stawka_dzienna": dzienna,
               "kwota_laczna": kwota_laczna if kwota_laczna is not None else (zl(dzienna * dni) if dzienna is not None else kwota),
               "wzor": wzor, "zrodla_obliczen": zrodla or [], "uwagi_obliczen": uwagi or []}
        if podst_info:
            rec["podstawa_metoda"] = podst_info["metoda"]
            rec["zrodla_obliczen"] = list(dict.fromkeys(rec["zrodla_obliczen"] + podst_info["zrodla"]))
            rec["uwagi_obliczen"] += podst_info["ostrzezenia"]
            rec["kto_wyplaca"] = kto_wyplaca(self.dane, self.P)
        return rec

    def _urlop(self, pct: Decimal, od: date, dni: int, data_prawa: date, wzor: str, zrodla: list,
               uwagi: list | None = None, wymiar_pracy: float = 0, do: date | None = None) -> dict:
        """Urlop płatny zasiłkiem macierzyńskim: kwota/mies. = podstawa × procent (× (1 − wymiar pracy)),
        łącznie = stawka dzienna × dni płatne (wzory – funkcja stawka_dzienna).
        `do` podaje się, gdy okres ma przerwy (koniec ≠ od + dni − 1)."""
        podst, info = self.podstawa(data_prawa)
        dz, mies, u = stawka_dzienna(podst, pct, self.P, wymiar_pracy)
        return self._wynik(mies, "miesiac", od, do or od + timedelta(days=dni - 1), procent=pct, podstawa=podst,
                           dzienna=dz, wzor=wzor, zrodla=zrodla, uwagi=(uwagi or []) + u, podst_info=info, dni=dni)

    # ── świadczenia w ciąży ────────────────────────────────────────────────
    def zasilek_chorobowy_ciaza(self, w: WynikSprawdzenia) -> dict:
        """Wzór: zasiłek/mies. = podstawa × 100% (ustawa zasiłkowa str. 3, art. 11 ust. 2 pkt 1;
        treść zadania str. 4; Poradnik str. 24 (PDF 25)), za każdy dzień niezdolności (art. 11 ust. 4),
        najdłużej do wyczerpania 270 dni (art. 8 ust. 1) – w kalkulatorze do dnia przed porodem.
        Podstawa: 12 mies. przed miesiącem powstania niezdolności (art. 36 ust. 1 / art. 48 ust. 1)."""
        f = w.fakty
        podst, info = self.podstawa(f["od"])
        pct = D(str(self.P["zasilek_chorobowy_ciaza_procent"]))
        dz, mies, _ = stawka_dzienna(podst, pct, self.P, minimum_swiadczenia_rodzicielskiego=False)
        uw = ["Wypłacany tylko za dni niezdolności do pracy potwierdzone e-ZLA z kodem B (treść zadania str. 3)."]
        if f.get("ubezpieczenie") == "obowiazkowe" and self.pole("tytul_ubezpieczenia") in TYTULY_PRACOWNIK:
            # Pracownik: pierwsze 33 dni w roku (14 po 50. r.ż.) – wynagrodzenie chorobowe od pracodawcy, w ciąży 100%
            # (Kodeks pracy str. 1–2, art. 92 § 1 pkt 2; Załącznik „Zasiłek chorobowy w okresie ciąży”; Poradnik str. 23).
            dni_wyn = self.P["wynagrodzenie_chorobowe_dni"]["po_50_roku_zycia" if (f.get("wiek") or 0) >= 50 else "standard"]
            uw.append(f"Pierwsze {dni_wyn} dni niezdolności w roku kalendarzowym płaci pracodawca jako wynagrodzenie "
                      "chorobowe (w ciąży 100%, liczone jak zasiłek – Kodeks pracy art. 92), dalej zasiłek.")
        elif f.get("ubezpieczenie") == "dobrowolne":
            uw.append("Ubezpieczenie dobrowolne – bez wynagrodzenia chorobowego, zasiłek od 1. dnia (Poradnik str. 23).")
        return self._wynik(mies, "miesiac", f["od"], f["do"], procent=pct, podstawa=podst, dzienna=dz,
                           wzor=f"podstawa {podst} zł × {pct}%", zrodla=["UZ_11", "UZ_8_9", "KP_92", "ZAL_chor", "POR_23", "POR_24"],
                           uwagi=uw, podst_info=info)

    def swiadczenie_rehabilitacyjne(self, w: WynikSprawdzenia) -> dict:
        """Wzór: świadczenie/mies. = podstawa zasiłku chorobowego × 100% w ciąży (ustawa zasiłkowa str. 6,
        art. 19 ust. 1), najdłużej 12 mies. (str. 5, art. 18 ust. 2). Waloryzacji podstawy z art. 19 ust. 2
        nie liczę (wskaźniki ogłasza Prezes ZUS – nie ma ich w plikach)."""
        f = w.fakty
        podst, info = self.podstawa(f["od"])
        pct = D(str(self.P["swiadczenie_rehabilitacyjne_ciaza_procent"]))
        dz, mies, _ = stawka_dzienna(podst, pct, self.P, minimum_swiadczenia_rodzicielskiego=False)
        return self._wynik(mies, "miesiac", f["od"], f["do"], procent=pct, podstawa=podst, dzienna=dz,
                           wzor=f"podstawa {podst} zł × {pct}%", zrodla=["UZ_18_19"],
                           uwagi=["Bez waloryzacji podstawy z art. 19 ust. 2 (brak wskaźników w plikach)."], podst_info=info)

    def zasilek_w_wysokosci_macierzynskiego(self, w: WynikSprawdzenia) -> dict:
        """Wzór: zasiłek/mies. = podstawa × 100% – „w wysokości zasiłku macierzyńskiego za urlop macierzyński”
        (ustawa zasiłkowa str. 8, art. 30 ust. 3; treść zadania str. 4), do dnia porodu.
        Podstawa wg zasad dla pracowników (ustawa zasiłkowa str. 11, art. 47)."""
        f = w.fakty
        podst, info = self.podstawa(f["od"])
        pct = _pct(self.P, "macierzynski")
        dz, mies, _ = stawka_dzienna(podst, pct, self.P, minimum_swiadczenia_rodzicielskiego=False)
        return self._wynik(mies, "miesiac", f["od"], f["do"], procent=pct, podstawa=podst, dzienna=dz,
                           wzor=f"podstawa {podst} zł × {pct}%", zrodla=["UZ_30", "UZ_47", "ZAD_s4"], podst_info=info)

    # ── urlopy przy porodzie ──────────────────────────────────────────────
    def urlop_macierzynski(self, w: WynikSprawdzenia) -> dict:
        """Wzór: zasiłek/mies. = podstawa × 100% (albo 81,5% przy jednolitym wniosku)
        (ustawa zasiłkowa str. 9, art. 31 ust. 1 i 3; Załącznik „Wysokość zasiłku”; Poradnik str. 34);
        okres: od (poród − tygodnie przed porodem) przez wymiar 20–37 tyg. (Kodeks pracy str. 3, art. 180 § 1–3),
        skrócony przy martwym urodzeniu / zgonie dziecka (art. 180¹, str. 5)."""
        f = w.fakty
        ev, n = f["zdarzenie"], f["liczba_dzieci"]
        przed = self._przed()
        dni_po, _, uw, zr = macierzynski_po_porodzie(ev["dzieci_zdarzenia"], ev["data"], przed * 7, n, self.P)
        pct = _pct(self.P, "jednolity_wniosek_21_dni") if f.get("wariant_81_5") else _pct(self.P, "macierzynski")
        if f.get("wariant_81_5") and przed:
            uw.append("Poradnik str. 27 i 33: zasiłek przed porodem 100%; ustawa (art. 31 ust. 3) – 81,5% za cały okres. "
                      "Przyjęto 81,5% – do potwierdzenia z ZUS.")
        od = ev["data"] - timedelta(days=przed * 7)
        self.os["koniec_macierzynskiego"] = ev["data"] + timedelta(days=dni_po - 1)
        return self._urlop(pct, od, przed * 7 + dni_po, ev["data"],
                           f"podstawa × {pct}%", ["KP_180_1", "KP_180_2_3", "UZ_31_1_3", "ZAL_wys"] + zr, uw)

    def urlop_macierzynski_przejecie(self, w: WynikSprawdzenia) -> dict:
        """Ojciec przejmuje część urlopu macierzyńskiego. Okres:
          rezygnacja matki – od dnia rezygnacji (najwcześniej po 14 tyg. po porodzie) do końca wymiaru
            (Kodeks pracy str. 3, art. 180 § 4–5);
          orzeczenie o niezdolności matki / porzucenie – najwcześniej po 8 tyg. (§ 6–7, § 13, str. 3–4);
          pobyt matki w szpitalu – za okres pobytu po 8 tyg. (§ 10–11, str. 4);
          zgon matki – od dnia po zgonie (§ 12, str. 4) – daty zgonu nie ma w schemacie, przyjmuję dziś.
        Łącznie nie więcej niż wymiar (§ 14). Wzór kwoty: podstawa ojca × 100% (ustawa zasiłkowa art. 31 ust. 1)."""
        f = w.fakty
        ev, n, powod = f["zdarzenie"], f["liczba_dzieci"], f["powod_przejecia"]
        W = wymiar_macierzynskiego_tyg(n, self.P)
        koniec_mac = ev["data"] + timedelta(days=W * 7 - self._przed() * 7 - 1)
        uw: list[str] = []
        if powod == "rezygnacja":
            rez = self.pole("rezygnacja_z_macierzynskiego_po_14_tyg")
            od = data(rez.get("data")) or ev["data"] + timedelta(days=14 * 7)
            od = max(od, ev["data"] + timedelta(days=int(self.P["urlop_macierzynski_min_matka_tyg"]) * 7))
        elif powod in ("orzeczenie_niezdolnosci", "porzucenie_dziecka"):
            od = ev["data"] + timedelta(days=int(self.P["urlop_macierzynski_min_szczegolne_tyg"]) * 7)
        elif powod == "szpital_matki":
            od8 = ev["data"] + timedelta(days=int(self.P["urlop_macierzynski_min_szczegolne_tyg"]) * 7)
            dni_sz = set()
            for h in self.pole("hospitalizacja_matki"):
                a, b = max(data(h["od"]), od8), min(data(h["do"]), koniec_mac)
                dni_sz.update(a + timedelta(days=i) for i in range((b - a).days + 1))
            if not dni_sz:
                od, dni = od8, 0
            else:
                od = min(dni_sz)
                uw.append(f"Za {len(dni_sz)} dni pobytu matki w szpitalu (po 8 tyg. od porodu); "
                          "zasiłek matki w tym czasie się przerywa (ustawa zasiłkowa art. 29 ust. 6).")
                self.os["koniec_macierzynskiego"] = koniec_mac
                return self._urlop(_pct(self.P, "macierzynski"), od, len(dni_sz), ev["data"], "podstawa × 100%",
                                   ["KP_180_10_11", "UZ_29_3_10", "UZ_31_1_3"], uw)
        else:  # zgon_matki
            od = max(ev["data"], self.dzis)
            uw.append("Data zgonu matki nie jest polem schematu – przyjęto dzień obliczenia jako początek.")
        self.os["koniec_macierzynskiego"] = koniec_mac
        dni = max(0, (koniec_mac - od).days + 1)
        return self._urlop(_pct(self.P, "macierzynski"), od, dni, ev["data"], "podstawa × 100%",
                           ["KP_180_14", "UZ_29_3_10", "UZ_31_1_3"], uw)

    def urlop_na_warunkach_macierzynskiego(self, w: WynikSprawdzenia) -> dict:
        """Przyjęcie dziecka: wymiar – funkcja wymiar_przyjecia(); kwota = podstawa × 100%
        (81,5% przy jednolitym wniosku do 21 dni od przyjęcia) – ustawa zasiłkowa str. 9, art. 31 ust. 1 i 3,
        str. 8, art. 30a ust. 2. Urlop zaczyna się najpóźniej 21 dni od przyjęcia (Kodeks pracy str. 9, art. 183 § 6) –
        w kalkulatorze od dnia powstania prawa."""
        f = w.fakty
        ev = f["zdarzenie"]
        dziecko = min(ev["dzieci_zdarzenia"] or [ev["dziecko"]], key=lambda c: -data(c["data_urodzenia"]).toordinal())
        wp = wymiar_przyjecia(data(dziecko["data_urodzenia"]), ev["przyjecie"]["rodzaj"],
                              bool(dziecko.get("odroczony_obowiazek_szkolny")), f["liczba_dzieci"],
                              bool(f.get("za_zyciem")), ev["data"], self.P)
        uw = []
        if wp["par3"]:
            uw.append("Wymiar wg minimum 9 tyg. (Kodeks pracy art. 183 § 3) – rodzicielski 38/62 tyg. (interpretacja).")
        elif wp["skrocony"]:
            uw.append(f"Skrócony do dnia przed ukończeniem przez dziecko {wp['wiek_limit']} lat (Kodeks pracy art. 183 § 1/§ 1¹).")
        self.os.update(koniec_macierzynskiego=ev["data"] + timedelta(days=wp["na_warunkach_dni"] - 1), przyjecie=wp)
        pct = _pct(self.P, "jednolity_wniosek_21_dni") if f.get("wariant_81_5") else _pct(self.P, "na_warunkach_macierzynskiego")
        return self._urlop(pct, ev["data"], wp["na_warunkach_dni"], ev["data"], f"podstawa × {pct}%",
                           ["KP_183_1", "KP_183_11", "KP_183_3", "UZ_31_1_3"], uw)

    def urlop_uzupelniajacy(self, w: WynikSprawdzenia) -> dict:
        """Wzór: podstawa × 100% (ustawa zasiłkowa str. 9, art. 31 ust. 1) przez U tygodni wyliczonych
        w oblicz_uzupelniajacy() (Kodeks pracy str. 5, art. 180²), bezpośrednio po macierzyńskim (§ 1)."""
        f = w.fakty
        ev, U = f["zdarzenie"], f["tygodnie"]
        if "koniec_macierzynskiego" in self.os:
            od = self.os["koniec_macierzynskiego"] + timedelta(days=1)
        else:   # ojciec: po macierzyńskim matki w pełnym wymiarze
            od = ev["data"] + timedelta(days=wymiar_macierzynskiego_tyg(f.get("liczba_dzieci") or 1, self.P) * 7 - self._przed() * 7)
        self.os["koniec_przed_rodzicielskim"] = od + timedelta(days=U * 7 - 1)
        return self._urlop(_pct(self.P, "uzupelniajacy"), od, U * 7, ev["data"], "podstawa × 100%",
                           ["KP_1802", "UZ_31_1_3"], [f["opis"]])

    def _plan_rodzicielski(self, w: WynikSprawdzenia) -> dict:
        """Ustala okres i procent rodzicielskiego dla użytkownika:
          • matka (poród): R − 9 tyg. (9 tyg. drugiego rodzica nieprzenoszalne – Kodeks pracy str. 6, art. 182¹a § 4),
            po macierzyńskim / uzupełniającym; 70% albo 81,5% przy jednolitym wniosku (ustawa zasiłkowa art. 31 ust. 2–3);
          • ojciec (poród): 9 tyg. nieprzenoszalnych, zawsze 70% (ustawa zasiłkowa str. 9, art. 31 ust. 3f;
            Poradnik str. 34) – termin przykładowy po części matki;
          • przyjęcie: R (38/41/43…) − 9 tyg. po urlopie na warunkach macierzyńskiego.
        Jeśli w danych jest plan (czesci_urlopu_rodzicielskiego z rodzic = rola) – liczę wg planu."""
        f = w.fakty
        ev, n, rola = f["zdarzenie"], f.get("liczba_dzieci") or 1, f.get("rola")
        nieprzen = int(self.P["urlop_rodzicielski_nieprzenoszalny_tyg"]) * 7
        uw: list[str] = []
        if ev["sciezka"] == "przyjecie":
            wp = self.os.get("przyjecie")
            if not wp:
                d0 = min(ev["dzieci_zdarzenia"] or [ev["dziecko"]], key=lambda c: -data(c["data_urodzenia"]).toordinal())
                wp = wymiar_przyjecia(data(d0["data_urodzenia"]), ev["przyjecie"]["rodzaj"],
                                      bool(d0.get("odroczony_obowiazek_szkolny")), n, bool(f.get("za_zyciem")), ev["data"], self.P)
            R_tyg = wp["R_tyg"]
            pula = max(0, wp["R_dni"] - nieprzen)
            start = ev["data"] + timedelta(days=wp["na_warunkach_dni"])
            pct = _pct(self.P, "jednolity_wniosek_21_dni") if f.get("wariant_81_5") else _pct(self.P, "rodzicielski")
            zr = ["KP_183_4"]
        else:
            R_tyg = wymiar_rodzicielskiego_tyg(n, bool(f.get("za_zyciem")), self.P)
            W = wymiar_macierzynskiego_tyg(n, self.P)
            koniec_mac_matki = ev["data"] + timedelta(days=W * 7 - self._przed() * 7 - 1)
            if rola == "ojciec":
                pula = nieprzen
                start = self.os.get("koniec_przed_rodzicielskim", koniec_mac_matki) + timedelta(days=(R_tyg * 7 - nieprzen) + 1)
                pct = _pct(self.P, "nieprzenoszalne_9_tyg_drugiego_rodzica")
                uw.append(f"Ojciec ma 9 tyg. nieprzenoszalne (zawsze 70%); może wziąć do {R_tyg - 9} tyg. z puli matki. "
                          "Termin przykładowy – po części matki.")
                zr = ["KP_1821a", "UZ_31_3f", "POR_34"]
            else:
                pula = R_tyg * 7 - nieprzen
                start = self.os.get("koniec_przed_rodzicielskim", self.os.get("koniec_macierzynskiego", koniec_mac_matki)) + timedelta(days=1)
                pct = _pct(self.P, "jednolity_wniosek_21_dni") if f.get("wariant_81_5") else _pct(self.P, "rodzicielski")
                zr = ["KP_1821a", "UZ_31_1_3"]
        # Części urlopu: (początek, dni z puli, wymiar pracy). Bez planu – jedna część od `start`.
        czesci_out = [(start, pula, 0.0)]
        czesci = self.pole("czesci_urlopu_rodzicielskiego")
        moje = sorted((c for c in (czesci if isinstance(czesci, list) else [])
                       if c.get("rodzic") == rola and c.get("od") and c.get("do")), key=lambda c: data(c["od"]))
        if moje:
            czesci_out = [(data(c["od"]), (data(c["do"]) - data(c["od"])).days + 1, float(c.get("wymiar_pracy_w_trakcie") or 0))
                          for c in moje]
            start, pula = czesci_out[0][0], sum(c[1] for c in czesci_out)
            uw.append(f"Wg planu: {len(moje)} część(i) urlopu rodzicielskiego, {pula} dni z puli.")
            if len(moje) > int(self.P["urlop_rodzicielski_max_czesci"]):
                uw.append("Więcej niż 5 części (Kodeks pracy art. 182¹c).")
        koniec_planu = max(od + timedelta(days=d - 1) for od, d, _ in czesci_out)
        return {"start": start, "pula": pula, "koniec": koniec_planu, "czesci": czesci_out, "pct": pct,
                "R_tyg": R_tyg, "n": n, "zr": zr, "uwagi": uw}

    def urlop_rodzicielski(self, w: WynikSprawdzenia) -> dict:
        """Wariant bez pracy: kwota/mies. = podstawa × 70% (81,5%) przez pulę dni z _plan_rodzicielski()."""
        p = self._plan_rodzicielski(w)
        return self._urlop(p["pct"], p["start"], p["pula"], w.fakty["zdarzenie"]["data"], f"podstawa × {p['pct']}%",
                           p["zr"] + ["ZAL_rodz"], p["uwagi"], do=p["koniec"])

    def urlop_rodzicielski_z_praca(self, w: WynikSprawdzenia) -> dict:
        """Wariant z pracą – liczony osobno dla KAŻDEJ części planu (czesci_urlopu_rodzicielskiego):
          KROK 1 – w części z pracą na `wp` etatu (≤ 1/2 – Kodeks pracy str. 7, art. 182¹e):
                   zasiłek/mies. = podstawa × procent × (1 − wp) (ustawa zasiłkowa str. 9, art. 31 ust. 4a);
          KROK 2 – ta część wydłuża się o dni × wp, z pominięciem niepełnego dnia (Kodeks pracy str. 7,
                   art. 182¹f § 2 i § 4); wydłużenie dokleja się do tej części (§ 5), zasiłek w nim pełny;
          KROK 3 – części bez pracy: pełny zasiłek;
          KROK 4 – łączny czas ≤ 82/86 tyg. (130/134 z Za życiem) – art. 182¹f § 1, § 1¹.
        Bez planu (albo gdy w planie nikt nie pracuje) liczę przykład: cała pula przy pracy na 1/2 etatu."""
        p = self._plan_rodzicielski(w)
        maxw = float(self.P["urlop_rodzicielski_praca_max_wymiar"])
        uw = list(p["uwagi"])
        czesci = p["czesci"]
        if not any(wp > 0 for _, _, wp in czesci):
            czesci = [(p["start"], p["pula"], maxw)]
            uw.append(f"Przykład dla pracy na {maxw:g} etatu przez całą pulę (w planie brak wymiar_pracy_w_trakcie > 0).")
        podst, info = self.podstawa(w.fakty["zdarzenie"]["data"])
        dz_pelna, mies_pelna, u0 = stawka_dzienna(podst, p["pct"], self.P)
        laczna, dni_razem, konce, mies_praca, dz_praca, wp_pokaz = D(0), 0, [], None, None, None
        for od, dni, wp in czesci:
            if wp > 0:                                                                   # KROK 1 + 2
                dz_w, mies_w, _ = stawka_dzienna(podst, p["pct"], self.P, wp)
                wydl = math.floor(dni * Fraction(str(wp)))
                laczna += dz_w * dni + dz_pelna * wydl
                konce.append(od + timedelta(days=dni + wydl - 1))
                dni_razem += dni + wydl
                uw.append(f"Część od {od}: {dni} dni pracy na {wp:g} etatu po {mies_w} zł/mies., "
                          f"potem wydłużenie {wydl} dni po {mies_pelna} zł/mies.")
                if mies_praca is None:
                    mies_praca, dz_praca, wp_pokaz = mies_w, dz_w, wp
            else:                                                                        # KROK 3
                laczna += dz_pelna * dni
                konce.append(od + timedelta(days=dni - 1))
                dni_razem += dni
                uw.append(f"Część od {od}: {dni} dni bez pracy po {mies_pelna} zł/mies.")
        limit = limit_z_praca_tyg(p["n"], bool(w.fakty.get("za_zyciem")), self.P) * 7     # KROK 4
        if dni_razem > limit:
            uw.append(f"Łączny czas przekracza limit {limit // 7} tyg. (Kodeks pracy art. 182¹f).")
        uw.append("Łączna kwota zasiłku ≈ jak bez pracy; do tego wynagrodzenie za pracę (nie liczone).")
        return self._wynik(mies_praca, "miesiac", czesci[0][0], max(konce), procent=p["pct"], podstawa=podst,
                           dzienna=dz_praca, wzor=f"podstawa × {p['pct']}% × (1 − {wp_pokaz:g})",
                           zrodla=["KP_1821e", "KP_1821f", "UZ_31_4a"], uwagi=uw + u0, podst_info=info,
                           kwota_laczna=zl(laczna), dni=dni_razem)

    def urlop_ojcowski(self, w: WynikSprawdzenia) -> dict:
        """Wzór: podstawa × 100% przez 14 dni (Kodeks pracy str. 7–8, art. 182³; ustawa zasiłkowa art. 31 ust. 1;
        Poradnik str. 33 (PDF 34)); od porodu / uprawomocnienia przysposobienia albo wg planu
        (czesci_urlopu_ojcowskiego – max 2 części ≥ 7 dni)."""
        f = w.fakty
        czesci = self.pole("czesci_urlopu_ojcowskiego")
        uw = [f"Wykorzystaj do {f['termin']} (Kodeks pracy art. 182³ § 1)."]
        if isinstance(czesci, list) and czesci:
            od = min(data(c["od"]) for c in czesci)
            dni = sum((data(c["do"]) - data(c["od"])).days + 1 for c in czesci)
            if dni > self.P["urlop_ojcowski_dni"] or len(czesci) > self.P["urlop_ojcowski_max_czesci"]:
                uw.append("Plan przekracza 14 dni lub 2 części (Kodeks pracy art. 182³ § 1¹).")
        else:
            od, dni = max(f["od_najwczesniej"], self.dzis), int(self.P["urlop_ojcowski_dni"])   # najwcześniej dziś
        return self._urlop(_pct(self.P, "ojcowski"), od, dni, f["zdarzenie"]["data"], "podstawa × 100%",
                           ["KP_1823", "UZ_31_1_3", "POR_33"], uw)

    # ── świadczenia gminne ────────────────────────────────────────────────
    def swiadczenie_rodzicielskie(self, w: WynikSprawdzenia) -> dict:
        """Kwota 1000 zł/mies. – zmienne_uzytkownika.json, parametry_admin.
        Długość: plików ZUS nie ma ustawy o świadczeniach rodzinnych, więc przyjmuję okres odpowiadający urlopowi
        macierzyńskiemu + rodzicielskiemu bez 9 tyg. drugiego rodzica (Kodeks pracy str. 3, art. 180 § 1 i str. 6,
        art. 182¹a) – np. 20 + 32 = 52 tyg. przy 1 dziecku. DO WERYFIKACJI."""
        f = w.fakty
        ev, n = f["zdarzenie"], f.get("liczba_dzieci") or 1
        if ev["sciezka"] == "przyjecie":
            d0 = min(ev["dzieci_zdarzenia"] or [ev["dziecko"]], key=lambda c: -data(c["data_urodzenia"]).toordinal())
            wp = wymiar_przyjecia(data(d0["data_urodzenia"]), ev["przyjecie"]["rodzaj"],
                                  bool(d0.get("odroczony_obowiazek_szkolny")), n, False, ev["data"], self.P)
            dni = wp["na_warunkach_dni"] + max(0, wp["R_dni"] - int(self.P["urlop_rodzicielski_nieprzenoszalny_tyg"]) * 7)
        else:
            dni = (wymiar_macierzynskiego_tyg(n, self.P)
                   + wymiar_rodzicielskiego_tyg(n, False, self.P) - int(self.P["urlop_rodzicielski_nieprzenoszalny_tyg"])) * 7
        kw = zl(self.P["swiadczenie_rodzicielskie_zl_mies"])
        return self._wynik(kw, "miesiac", ev["data"], ev["data"] + timedelta(days=dni - 1), wzor="kwota stała",
                           dzienna=zl(kw / 30), zrodla=["JSN_param", "POR_35", "KAT_SR7"],
                           uwagi=["Długość okresu przyjęta jak macierzyński + rodzicielski − 9 tyg. – do weryfikacji "
                                  "(brak ustawy o świadczeniach rodzinnych w plikach)."])

    def becikowe(self, w: WynikSprawdzenia) -> dict:
        """1000 zł jednorazowo (zmienne_uzytkownika.json, parametry_admin: becikowe_zl); wniosek do 12 mies.
        od urodzenia (katalog_wnioskow_pdf.json, BECIKOWE)."""
        f = w.fakty
        return self._wynik(zl(self.P["becikowe_zl"]), "jednorazowo", f["od"], f["do"], wzor="kwota stała",
                           zrodla=["JSN_param", "KAT_BECIKOWE"])

    def jednorazowe_za_zyciem(self, w: WynikSprawdzenia) -> dict:
        """4000 zł jednorazowo (zmienne_uzytkownika.json, parametry_admin: za_zyciem_zl); wniosek do 12 mies.
        (katalog_wnioskow_pdf.json, ZA-ZYCIEM)."""
        f = w.fakty
        return self._wynik(zl(self.P["za_zyciem_zl"]), "jednorazowo", f["od"], f["do"], wzor="kwota stała",
                           zrodla=["JSN_param", "KAT_ZAZYCIEM"])


def _komunikat(w: WynikSprawdzenia, k: dict | None) -> str:
    """Komunikaty w formacie ustalonym przez zespół:
      BRAK_DANYCH → 'WARNING: {nazwa} – brakuje danych: a, b'
      NIE_SPELNIA → 'Nie masz możliwości uzyskania: {nazwa} – {powód}'
      SPELNIA     → zależnie od trybu wypłaty (miesięcznie / jednorazowo / urlop)."""
    if w.status != Status.SPELNIA or k is None:
        return w.komunikat()
    od, do = k["okres_od"].isoformat(), k["okres_do"].isoformat()
    if w.tryb_wyplaty == "miesiecznie":
        return f"Można uzyskać: {w.nazwa}: {k['kwota']} zł/miesiąc, okres: {od} – {do}"
    if w.tryb_wyplaty == "jednorazowo":
        return f"Można uzyskać: {w.nazwa}: {k['kwota']} zł/jednorazowo, okres na złożenie wniosku: {od} – {do}"
    wzor = k["wzor"].replace("podstawa", f"podstawa {k['podstawa']} zł")   # bez zagnieżdżonych f-stringów (Python 3.10+)
    return (f"Można uzyskać: {w.nazwa} (urlop): {k['kwota']} zł/mies. ({wzor}) "
            f"na okres {od} – {do} ({round(k['dni'] / 7, 1):g} tyg.; łącznie ok. {k['kwota_laczna']} zł)")


# Każdy element listy z oblicz_wszystkie_swiadczenia ma ZAWSZE te same klucze (None, gdy nie dotyczy),
# żeby frontend / REST API mógł je czytać bez sprawdzania, czy klucz istnieje.
POLA_WYNIKU = ("kod", "nazwa", "tryb_wyplaty", "status", "komunikat",
               "kwota", "jednostka", "okres_od", "okres_do", "dni", "procent", "podstawa", "stawka_dzienna",
               "kwota_laczna", "wzor", "podstawa_metoda", "kto_wyplaca",
               "brakujace_dane", "powody", "uwagi", "zrodla")


def oblicz_wszystkie_swiadczenia(dane: dict, P: dict | None = None, data_ref: date | None = None) -> list[dict]:
    """GŁÓWNY PUNKT WEJŚCIA → lista słowników (po jednym na świadczenie z KATALOG_SWIADCZEN, w jego kolejności).
    KROK 0 – ujednolicenie danych z formularza (normalizuj_dane: "true" → True, "2" → 2, "" → None);
    KROK 1 – sprawdzenie wszystkich świadczeń (moduł sprawdzanie_swiadczen.py → 3 stany);
    KROK 2 – dla stanu SPELNIA: kwota i okres (klasa _KalkulatorOsoby);
    KROK 3 – komunikat wg trybu wypłaty (_komunikat).
    Błąd przy jednym świadczeniu (np. zły format pola) nie przerywa listy – to świadczenie dostaje BRAK_DANYCH.
    Klucze elementu: POLA_WYNIKU (daty jako 'RRRR-MM-DD', kwoty jako float)."""
    P = P or PARAMETRY_DOMYSLNE
    dzis = data_ref or date.today()
    dane = normalizuj_dane(dane)                                                  # KROK 0
    kal = _KalkulatorOsoby(dane, P, dzis)
    wynik = []
    for w in sprawdz_wszystkie(dane, P, dzis):                                    # KROK 1
        k = None
        if w.status == Status.SPELNIA:
            try:
                k = getattr(kal, w.kod.lower())(w)                                # KROK 2
            except BrakDanych as e:
                w = WynikSprawdzenia(w.kod, w.nazwa, w.tryb_wyplaty, Status.BRAK_DANYCH, [e.pole], [], w.zrodla,
                                     w.uwagi + [str(e)], w.fakty)
            except (ValueError, TypeError, KeyError, AttributeError, IndexError) as e:
                w = WynikSprawdzenia(w.kod, w.nazwa, w.tryb_wyplaty, Status.BRAK_DANYCH,
                                     [f"poprawny format danych ({type(e).__name__}: {e})"], [], w.zrodla,
                                     w.uwagi + ["Nie udało się policzyć kwoty – sprawdź format pól planu i dat."], w.fakty)
        rec = dict.fromkeys(POLA_WYNIKU)
        rec.update(w.jako_slownik())
        if k:
            rec.update({kk: vv for kk, vv in k.items() if kk in POLA_WYNIKU})
            rec["uwagi"] = rec["uwagi"] + k["uwagi_obliczen"]
            for z in k["zrodla_obliczen"]:
                if z not in [x["klucz"] for x in rec["zrodla"]]:
                    rec["zrodla"].append({"klucz": z, "plik": ZRODLA[z][0], "strona": ZRODLA[z][1], "opis": ZRODLA[z][2]})
        rec["komunikat"] = _komunikat(w, k)                                        # KROK 3
        wynik.append(_do_json(rec))
    return wynik


# ── Funkcje pomocnicze do dalszej pracy z listą ───────────────────────────
def komunikaty(lista: list[dict]) -> list[str]:
    """Same komunikaty (lista tekstów) – np. do wyświetlenia w UI."""
    return [r["komunikat"] for r in lista]


def wg_statusu(lista: list[dict]) -> dict[str, list[dict]]:
    """Grupowanie: {"SPELNIA": […], "BRAK_DANYCH": […], "NIE_SPELNIA": […]} (kolejność w grupach zachowana)."""
    grupy: dict[str, list[dict]] = {s.value: [] for s in Status}
    for r in lista:
        grupy[r["status"]].append(r)
    return grupy


def wszystkie_brakujace_dane(lista: list[dict]) -> list[str]:
    """Unikalne brakujące pola ze wszystkich WARNING-ów – lista pól, o które formularz powinien dopytać."""
    return list(dict.fromkeys(b for r in lista for b in r["brakujace_dane"]))


def _do_json(x: Any) -> Any:
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, Fraction):
        return float(x)
    if isinstance(x, dict):
        return {k: _do_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_do_json(v) for v in x]
    return x


# ═══════════════════════════════════════════════════════════════════════════
# 5. KALKULATORY SCENARIUSZOWE b–j (podpunkty z treści zadania, str. 13)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Wynik:
    """Wynik kalkulatora scenariuszowego: okresy (kto, rodzaj, dni, %, stawki, daty), podsumowanie,
    ostrzeżenia (interpretacje) i źródła."""
    podpunkt: str
    tytul: str
    okresy: list[dict] = field(default_factory=list)
    podsumowanie: dict = field(default_factory=dict)
    ostrzezenia: list[str] = field(default_factory=list)
    zrodla: list[str] = field(default_factory=list)
    pokazuj_daty: bool = True

    def zrodlo(self, *klucze: str) -> None:
        for k in klucze:
            if k not in ZRODLA:
                raise KeyError(f"Brak źródła {k}")
            if k not in self.zrodla:
                self.zrodla.append(k)

    def uwaga(self, tekst: str) -> None:
        if tekst not in self.ostrzezenia:
            self.ostrzezenia.append(tekst)

    def okres(self, kto: str, rodzaj: str, dni: int, procent: Decimal | float, podstawa: Decimal | None,
              P: dict, zrodla: list[str], od: date | None = None, wymiar_pracy: Fraction | float = 0,
              uwagi: list[str] | None = None) -> dict:
        """Dodaje okres i liczy kwoty wzorem z stawka_dzienna(): łącznie = stawka dzienna × dni."""
        if podstawa is not None and dni > 0:
            dz, mies, u = stawka_dzienna(podstawa, D(str(procent)), P, wymiar_pracy)
        else:
            dz, mies, u = None, None, []
        rec = {"kto": kto, "rodzaj": rodzaj, "dni": int(dni), "tygodnie": round(dni / 7, 2),
               "procent": float(procent), "wymiar_pracy": float(wymiar_pracy),
               "stawka_dzienna": dz, "kwota_miesieczna": mies,
               "kwota_laczna": zl(dz * dni) if dz is not None else None,
               "od": od, "do": (od + timedelta(days=dni - 1)) if (od and dni > 0) else None,
               "zrodla": list(zrodla), "uwagi": (uwagi or []) + u}
        self.okresy.append(rec)
        self.zrodlo(*zrodla)
        return rec

    def sumy(self) -> dict:
        s: dict[str, dict] = {}
        for o in self.okresy:
            p = s.setdefault(o["kto"], {"dni": 0, "kwota_laczna": D("0")})
            p["dni"] += o["dni"]
            if o["kwota_laczna"] is not None:
                p["kwota_laczna"] += o["kwota_laczna"]
        for p in s.values():
            p["tygodnie"] = round(p["dni"] / 7, 2)
        return s

    def jako_slownik(self) -> dict:
        out = _do_json({"podpunkt": self.podpunkt, "tytul": self.tytul, "okresy": self.okresy, "sumy": self.sumy(),
                        "podsumowanie": self.podsumowanie, "ostrzezenia": self.ostrzezenia,
                        "zrodla": [{"klucz": k, "plik": ZRODLA[k][0], "strona": ZRODLA[k][1], "opis": ZRODLA[k][2]}
                                   for k in self.zrodla]})
        if not self.pokazuj_daty:
            for o in out["okresy"]:
                o["od"] = o["do"] = None
        return out



def sprawdz_uprawnienie(osoba: dict, P: dict, wynik: Wynik, kto: str) -> bool:
    """Prawo osoby do zasiłku macierzyńskiego w kalkulatorach scenariuszowych:
    – tytuł bez ubezpieczenia chorobowego → brak (Poradnik str. 35 (PDF 36));
    – brak ubezpieczenia w dniu porodu (pole ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia = false) → brak,
      chyba że wyjątek z ustawy zasiłkowej str. 8, art. 30 (upadłość, likwidacja, śmierć pracodawcy, naruszenie
      przepisów + wyrok) – wtedy wypłaca ZUS (art. 61);
    – JDG z zadłużeniem > 1% płacy minimalnej – wypłata dopiero po spłacie (ustawa zasiłkowa str. 1, art. 2a)."""
    tytul = osoba.get("tytul_ubezpieczenia", "umowa_o_prace")
    if tytul in TYTULY_BEZ_ZASILKU_ZUS or osoba.get("ubezpieczenie_chorobowe") == "brak":
        wynik.zrodlo("POR_29", "POR_35")
        wynik.uwaga(f"{kto}: brak ubezpieczenia chorobowego ({tytul}) → brak zasiłku macierzyńskiego z ZUS; "
                    "możliwe świadczenie rodzicielskie (Poradnik str. 35).")
        return False
    if osoba.get("ubezpieczony") is False:
        wynik.zrodlo("POR_29")
        wynik.uwaga(f"{kto}: oznaczono jako nieubezpieczony – brak prawa do zasiłku.")
        return False
    if osoba.get("ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia", True) is False:
        przycz = osoba.get("przyczyna_rozwiazania_umowy")
        if przycz in ("upadlosc", "likwidacja", "smierc_pracodawcy") or \
           (przycz == "naruszenie_przepisow" and osoba.get("prawomocny_wyrok_naruszenie_przepisow")):
            wynik.zrodlo("UZ_30", "UZ_61")
            wynik.uwaga(f"{kto}: zasiłek po ustaniu ubezpieczenia (ustawa zasiłkowa art. 30) – wypłaca ZUS (art. 61).")
        else:
            wynik.zrodlo("POR_29", "ZAD_s10", "UZ_29_1_2")
            wynik.uwaga(f"{kto}: brak ubezpieczenia chorobowego w dniu porodu/przyjęcia → brak prawa (treść zadania str. 10).")
            return False
    if tytul in TYTULY_JDG:
        dl = (osoba.get("zadluzenie_skladkowe") or {}).get("kwota", 0) or 0
        prog = zl(D(str(P["placa_minimalna_zl"])) * D(str(P["zadluzenie_prog_procent_placy_min"])) / 100)
        if D(str(dl)) > prog:
            wynik.zrodlo("UZ_2a", "POR_24")
            wynik.uwaga(f"{kto}: zadłużenie {dl} zł > {prog} zł – zasiłek dopiero po spłacie; brak spłaty w 6 mies. "
                        "= przedawnienie (ustawa zasiłkowa art. 2a). Kwoty pokazują stan PO spłacie.")
    return True


def _podstawa_osoby(osoba: dict | None, P: dict, wynik: Wynik, kto: str) -> Decimal | None:
    """Sprawdza uprawnienie i liczy podstawę (oblicz_podstawe) jednej osoby w scenariuszu."""
    if not osoba or not sprawdz_uprawnienie(osoba, P, wynik, kto):
        return None
    try:
        r = oblicz_podstawe(osoba, P)
    except ValueError as e:
        wynik.uwaga(f"{kto}: {e}")
        return None
    wynik.zrodlo(*r["zrodla"])
    for u in r["ostrzezenia"]:
        wynik.uwaga(f"{kto}: {u}")
    wynik.podsumowanie.setdefault("podstawy", {})[kto] = f"{r['podstawa']} zł ({r['metoda']})"
    wynik.podsumowanie.setdefault("podstawa_szczegoly", {})[kto] = r
    wynik.podsumowanie.setdefault("kto_wyplaca", {})[kto] = kto_wyplaca(osoba, P)
    wynik.zrodlo("UZ_61")
    return r["podstawa"]


def _wariant_81_5(dane: dict, data_zdarzenia: date | None, P: dict, wynik: Wynik) -> bool:
    """Jednolity wniosek (pole jednolity_wniosek_81_5_procent {czy, data_zlozenia}): 81,5% za cały okres,
    jeśli złożony najpóźniej 21 dni po porodzie / przyjęciu (ustawa zasiłkowa str. 8, art. 30a; str. 9, art. 31 ust. 3)."""
    w = dane.get("jednolity_wniosek_81_5_procent") or {}
    if not w.get("czy"):
        return False
    wynik.zrodlo("UZ_30a", "UZ_31_1_3", "POR_34")
    dz = data(w.get("data_zlozenia"))
    if dz and data_zdarzenia and (dz - data_zdarzenia).days > int(P["termin_wniosku_81_5_dni"]):
        wynik.uwaga(f"Jednolity wniosek złożony {(dz - data_zdarzenia).days} dni po zdarzeniu (> 21 dni) – "
                    "przysługuje wariant 100% + 70% (ustawa zasiłkowa art. 30a).")
        return False
    return True


def _dzieci_i_dane_porodu(dane: dict) -> tuple[list[dict], int, bool]:
    """(dzieci, liczba dzieci z porodu – pole liczba_dzieci_przy_porodzie, czy Za życiem)."""
    dzieci = dane.get("dzieci") or []
    n = int(dane.get("liczba_dzieci_przy_porodzie") or max(1, len(dzieci)))
    za_zyciem = bool(dane.get("zaswiadczenie_za_zyciem") or any(c.get("zaswiadczenie_za_zyciem") for c in dzieci))
    return dzieci, n, za_zyciem


def _przed_porodem(dane: dict, P: dict, w: Wynik) -> int:
    """urlop_macierzynski.tygodnie_przed_porodem – max 6 (Kodeks pracy str. 3, art. 180 § 2)."""
    chciane = int((dane.get("urlop_macierzynski") or {}).get("tygodnie_przed_porodem") or 0)
    przed = min(chciane, int(P["urlop_macierzynski_przed_porodem_max_tyg"]))
    if chciane > przed:
        w.uwaga("Przed porodem można wykorzystać max 6 tyg. (Kodeks pracy art. 180 § 2) – przycięto.")
    return przed


# ── b) oboje rodzice ───────────────────────────────────────────────────────
def kalkulator_b(dane: dict, P: dict | None = None) -> Wynik:
    """b) Maksymalny wymiar i wysokość zasiłku macierzyńskiego dla matki i ojca przy urodzeniu dziecka
    (liczba dzieci, „Za życiem”, wcześniactwo, zgon dziecka).
    dane: data_porodu | przewidywana_data_porodu, liczba_dzieci_przy_porodzie, dzieci[…],
          urlop_macierzynski{tygodnie_przed_porodem}, jednolity_wniosek_81_5_procent{czy,data_zlozenia},
          matka{…}, ojciec{…} (pola osoby jak w zmienne_uzytkownika.json), uzupelniajacy_dla."""
    P = P or PARAMETRY_DOMYSLNE
    w = Wynik("b", "Zasiłek macierzyński dla obojga rodziców – okres i wysokość")
    w.zrodlo("ZAD_s4_5", "KP_184", "UZ_29a", "KP_1831")
    data_porodu = data(dane.get("data_porodu") or dane.get("przewidywana_data_porodu"))
    if not data_porodu:
        data_porodu, w.pokazuj_daty = date(2026, 1, 1), False
    dzieci, n, za_zyciem = _dzieci_i_dane_porodu(dane)

    # KROK 1 – prawo i podstawa każdego z rodziców (sprawdz_uprawnienie + oblicz_podstawe).
    pm = _podstawa_osoby(dane.get("matka"), P, w, "matka")
    po = _podstawa_osoby(dane.get("ojciec"), P, w, "ojciec")
    matka_ok, ojciec_ok = pm is not None, po is not None

    # KROK 2 – wymiary: macierzyński W (Kodeks pracy str. 3, art. 180 § 1), rodzicielski R
    # (str. 6, art. 182¹a § 1–2), 9 tyg. nieprzenoszalne (§ 4).
    W = wymiar_macierzynskiego_tyg(n, P)
    R = wymiar_rodzicielskiego_tyg(n, za_zyciem, P)
    nieprzen = int(P["urlop_rodzicielski_nieprzenoszalny_tyg"])
    przed = _przed_porodem(dane, P, w)
    w.zrodlo("KP_180_1", "ZAL_mac", "POR_30", "KP_1821a", "ZAL_rodz", "POR_31", "POR_32", "UZ_31_1_3", "ZAL_wys")
    if za_zyciem:
        w.zrodlo("UZ_61b_4a")

    # KROK 3 – procenty: 100% / 70%, albo 81,5% przy jednolitym wniosku (ustawa zasiłkowa str. 9, art. 31 ust. 1–3).
    wariant81 = _wariant_81_5(dane, data_porodu, P, w)
    pct_mac = _pct(P, "jednolity_wniosek_21_dni") if wariant81 else _pct(P, "macierzynski")
    pct_rodz_m = _pct(P, "jednolity_wniosek_21_dni") if wariant81 else _pct(P, "rodzicielski")

    # KROK 4 – dni po porodzie (z uwzględnieniem zgonu dziecka) i uzupełniający (Kodeks pracy art. 180¹, 180²).
    po_porodzie, n_zywe, uw, zr = macierzynski_po_porodzie(dzieci, data_porodu, przed * 7, n, P)
    for u in uw:
        w.uwaga(u + (" Rodzicielski, uzupełniający i ojcowski nie są liczone (cel: opieka nad dzieckiem – "
                     "Kodeks pracy art. 182¹a § 1; interpretacja)." if n_zywe == 0 else ""))
    w.zrodlo(*zr)
    dzieci_zyja = n_zywe > 0
    U, U_opis = 0, ""
    if dzieci_zyja and any(c.get("hospitalizacja") for c in dzieci):
        U, U_opis = oblicz_uzupelniajacy([c for c in dzieci if c.get("urodzone_zywe", True) is not False], data_porodu, P)
        w.zrodlo("KP_1802", "ZAL_uzup", "POR_31", "ZAD_s8")
    w.podsumowanie.update({
        "liczba_dzieci": n, "za_zyciem": za_zyciem,
        "wymiar_macierzynskiego_tyg": W, "wymiar_rodzicielskiego_tyg": R if dzieci_zyja else 0,
        "w_tym_nieprzenoszalne_tyg_na_rodzica": nieprzen,
        "wymiar_uzupelniajacego_tyg": U, "uzupelniajacy_wyliczenie": U_opis or "nie dotyczy",
        "urlop_ojcowski_dni": int(P["urlop_ojcowski_dni"]) if dzieci_zyja else 0,
        "wariant": "81,5% (wniosek do 21 dni po porodzie)" if wariant81 else "100% + 70%",
    })

    # KROK 5 – oś czasu matki: przed porodem → po porodzie → uzupełniający → rodzicielski (R − 9 tyg.).
    kursor = data_porodu - timedelta(days=przed * 7)
    if matka_ok:
        if przed:
            r = w.okres("matka", "macierzyński przed porodem", przed * 7, pct_mac, pm, P, ["KP_180_2_3", "ZAD_s5", "POR_27"], kursor)
            if wariant81:
                r["uwagi"].append("Poradnik str. 27/33: przed porodem 100%; ustawa (art. 31 ust. 3) – 81,5% za cały okres. "
                                  "Przyjęto 81,5% (do potwierdzenia).")
            kursor += timedelta(days=przed * 7)
        w.okres("matka", "macierzyński po porodzie", po_porodzie, pct_mac, pm, P, ["KP_180_1", "KP_180_2_3", "ZAL_mac"], kursor)
        kursor += timedelta(days=po_porodzie)
        if U and dane.get("uzupelniajacy_dla", "matka") == "matka":
            w.okres("matka", "uzupełniający macierzyński", U * 7, _pct(P, "uzupelniajacy"), pm, P,
                    ["KP_1802", "ZAL_uzup", "UZ_31_1_3"], kursor)
            kursor += timedelta(days=U * 7)
        if dzieci_zyja:
            dni_r = (R - nieprzen) * 7          # 9 tyg. drugiego rodzica nieprzenoszalne (Kodeks pracy art. 182¹a § 4)
            if not dane.get("ojciec"):
                w.uwaga("Nie podano danych ojca – matce policzono R − 9 tyg. Sytuacji rodzica samotnego pliki nie opisują.")
            w.okres("matka", "rodzicielski (część matki)", dni_r, pct_rodz_m, pm, P, ["KP_1821a", "ZAL_rodz", "UZ_31_1_3", "POR_34"], kursor)
            kursor += timedelta(days=dni_r)
    elif ojciec_ok:
        w.zrodlo("UZ_29_3_10", "ZAD_s7", "KP_180_15_17")
        w.uwaga("Matka bez prawa do zasiłku: ojciec ma zasiłek za rodzicielski (treść zadania str. 7, ustawa zasiłkowa "
                "art. 29 ust. 9–10). Macierzyński przejmuje tylko przy zgonie/porzuceniu/niezdolności matki lub gdy podejmie "
                "ona pracę ≥ 1/2 etatu (Kodeks pracy art. 180 § 15–17) – kalkulator d).")

    # KROK 6 – ojciec: ojcowski 14 dni 100% (Kodeks pracy art. 182³) + 9 tyg. rodzicielskiego 70% (ustawa art. 31 ust. 3f).
    if dzieci_zyja and ojciec_ok:
        w.okres("ojciec", "ojcowski", int(P["urlop_ojcowski_dni"]), _pct(P, "ojcowski"), po, P,
                ["KP_1823", "ZAL_ojc", "POR_33", "UZ_31_1_3"], data_porodu)
        if U and dane.get("uzupelniajacy_dla") == "ojciec" and matka_ok:
            w.okres("ojciec", "uzupełniający macierzyński", U * 7, _pct(P, "uzupelniajacy"), po, P,
                    ["KP_1802", "ZAL_uzup", "POR_31"], data_porodu + timedelta(days=po_porodzie))
        tyg_ojca = nieprzen if matka_ok else R - nieprzen
        w.okres("ojciec", "rodzicielski (9 tyg. ojca)" if matka_ok else "rodzicielski (matka nieubezpieczona)",
                tyg_ojca * 7, _pct(P, "nieprzenoszalne_9_tyg_drugiego_rodzica") if matka_ok else _pct(P, "rodzicielski"),
                po, P, ["KP_1821a", "UZ_31_3f", "POR_34"], kursor if matka_ok else data_porodu + timedelta(days=14))
        if not matka_ok:
            w.uwaga("Przyjęto, że 9 tyg. matki przepada (ojciec ma R − 9 tyg.) – pliki tego nie rozstrzygają wprost.")
    elif dzieci_zyja and matka_ok:
        w.uwaga("Ojciec bez prawa do zasiłku – jego 9 tyg. rodzicielskiego nie przechodzi na matkę (Kodeks pracy art. 182¹a § 4).")
    if wariant81 and dzieci_zyja:
        w.zrodlo("UZ_31_3g_4")
        w.uwaga("Wariant 81,5%: brak choćby dnia rodzicielskiego w 1. roku życia → rodzicielski 70% i wyrównanie "
                "macierzyńskiego do 100% (ustawa zasiłkowa art. 31 ust. 3g i 4).")
    if dzieci_zyja:
        w.zrodlo("KP_1821c", "ZAD_s6")
    return w


# ── c) łączenie urlopu rodzicielskiego z pracą ────────────────────────────
def _rodzicielski_z_praca(w: Wynik, kto: str, dni_puli: int, wymiar_pracy: float, procent: Decimal,
                          podstawa: Decimal | None, P: dict, od: date | None,
                          wymiar_pracy_wydl: float = 0, etykieta: str = "rodzicielski") -> int:
    """Okres łączony z pracą + wydłużenie. Zwraca łączną liczbę dni kalendarzowych.
    KROK 1 – część z pracą: zasiłek × (1 − wymiar pracy) (ustawa zasiłkowa str. 9, art. 31 ust. 4a);
    KROK 2 – wydłużenie = dni puli × wymiar pracy, niepełny dzień się pomija (Kodeks pracy str. 7, art. 182¹f § 2, § 4);
    KROK 3 – praca także w wydłużeniu: długość = wydłużenie / (1 − wymiar pracy w wydłużeniu) (art. 182¹f § 7);
    wydłużenie dokleja się do tej części urlopu (art. 182¹f § 5)."""
    wp = Fraction(str(wymiar_pracy))
    maxw = Fraction(str(P["urlop_rodzicielski_praca_max_wymiar"]))
    if wp > maxw:
        raise ValueError(f"Wymiar pracy {wymiar_pracy} > {float(maxw)} etatu (Kodeks pracy art. 182¹e § 1).")
    zr = ["KP_1821e", "KP_1821f", "UZ_31_4a", "ZAD_s9", "POR_19"] if wp else ["KP_1821a"]
    w.okres(kto, etykieta + (f" + praca {float(wp):g} etatu" if wp else ""), dni_puli, procent, podstawa, P, zr, od, wymiar_pracy=wp)
    razem = dni_puli
    if wp:
        wydl = math.floor(dni_puli * wp)                                  # KROK 2
        wp2 = Fraction(str(wymiar_pracy_wydl or 0))
        if wp2 > maxw:
            raise ValueError("Wymiar pracy w wydłużeniu > 1/2 etatu.")
        dl = math.floor(Fraction(wydl) / (1 - wp2)) if wp2 else wydl      # KROK 3
        od2 = od + timedelta(days=dni_puli) if od else None
        w.okres(kto, f"{etykieta} – wydłużenie (art. 182¹f)" + (f" + praca {float(wp2):g}" if wp2 else ""),
                dl, procent, podstawa, P, ["KP_1821f", "UZ_31_4a"], od2, wymiar_pracy=wp2)
        razem += dl
    return razem


def kalkulator_c(dane: dict, P: dict | None = None) -> Wynik:
    """c) Łączenie urlopu rodzicielskiego z pracą (jeden rodzic-pracownik).
    dane: osoba{…}, liczba_dzieci_przy_porodzie, zaswiadczenie_za_zyciem,
          czesci_urlopu_rodzicielskiego: [{od, do, wymiar_pracy_w_trakcie}] albo czesci: [{tygodnie, wymiar_pracy}],
          wymiar_pracy_w_wydluzeniu, wariant: '70' | '81.5' | '9_tyg', data_rozpoczecia."""
    P = P or PARAMETRY_DOMYSLNE
    w = Wynik("c", "Zasiłek macierzyński przy łączeniu pracy z urlopem rodzicielskim")
    osoba = dane.get("osoba") or {}
    if osoba.get("tytul_ubezpieczenia", "umowa_o_prace") not in TYTULY_PRACOWNIK:
        w.uwaga("Łączenie z pracą (z wydłużeniem urlopu) dotyczy pracownika u pracodawcy udzielającego urlopu "
                "(Kodeks pracy art. 182¹e; treść zadania str. 9) – dla innych tytułów wynik poglądowy.")
    podst = _podstawa_osoby(osoba, P, w, "rodzic")
    od = data(dane.get("data_rozpoczecia"))
    n = int(dane.get("liczba_dzieci_przy_porodzie") or 1)
    zz = bool(dane.get("zaswiadczenie_za_zyciem"))
    R = wymiar_rodzicielskiego_tyg(n, zz, P)
    limit = limit_z_praca_tyg(n, zz, P)
    pct = {"70": _pct(P, "rodzicielski"), "81.5": _pct(P, "jednolity_wniosek_21_dni"),
           "9_tyg": _pct(P, "nieprzenoszalne_9_tyg_drugiego_rodzica")}[str(dane.get("wariant", "70"))]
    # Części: w formacie schematu (czesci_urlopu_rodzicielskiego z datami) albo w tygodniach.
    if dane.get("czesci_urlopu_rodzicielskiego"):
        czesci = [{"tygodnie": ((data(c["do"]) - data(c["od"])).days + 1) / 7, "wymiar_pracy": c.get("wymiar_pracy_w_trakcie") or 0,
                   "od": data(c["od"])} for c in dane["czesci_urlopu_rodzicielskiego"]]
        od = od or czesci[0]["od"]
    else:
        czesci = dane.get("czesci") or [{"tygodnie": R - int(P["urlop_rodzicielski_nieprzenoszalny_tyg"]), "wymiar_pracy": 0.5}]
    if not od:
        od, w.pokazuj_daty = date(2026, 1, 1), False
    pula = sum(Fraction(str(c["tygodnie"])) for c in czesci)
    if pula > R:
        w.uwaga(f"Suma tygodni z puli ({float(pula):g}) > wymiar rodzicielskiego ({R} tyg.) – Kodeks pracy art. 182¹a.")
    if pula > R - int(P["urlop_rodzicielski_nieprzenoszalny_tyg"]):
        w.uwaga("Jeden rodzic może wykorzystać najwyżej R − 9 tyg. (9 tyg. drugiego rodzica nieprzenoszalne).")
    kursor, razem_dni = od, 0
    for i, c in enumerate(czesci, 1):
        start = c.get("od") or kursor
        dl = _rodzicielski_z_praca(w, "rodzic", int(round(float(c["tygodnie"]) * 7)), float(c.get("wymiar_pracy", 0)),
                                   pct, podst, P, start, float(dane.get("wymiar_pracy_w_wydluzeniu", 0)), f"rodzicielski cz. {i}")
        kursor = start + timedelta(days=dl)
        razem_dni += dl
    if razem_dni > limit * 7:
        w.uwaga(f"Łączny czas {razem_dni} dni > limit {limit} tyg. (Kodeks pracy art. 182¹f § 1/§ 1¹).")
    if len(czesci) > int(P["urlop_rodzicielski_max_czesci"]):
        w.uwaga("Więcej niż 5 części urlopu rodzicielskiego (Kodeks pracy art. 182¹c).")
    bez_pracy = None
    if podst is not None:
        dz, _, _ = stawka_dzienna(podst, pct, P)
        bez_pracy = zl(dz * sum(int(round(float(c["tygodnie"]) * 7)) for c in czesci))
    w.podsumowanie.update({
        "wymiar_rodzicielskiego_tyg": R, "limit_przy_laczeniu_z_praca_tyg": limit,
        "pula_wykorzystana_tyg": float(pula), "czas_kalendarzowy_dni": razem_dni,
        "czas_kalendarzowy_tyg": round(razem_dni / 7, 2), "procent_zasilku": float(pct),
        "zasilek_bez_laczenia_z_praca_zl": bez_pracy,
        "uwaga": "Łączna kwota zasiłku ≈ jak bez pracy; do tego wynagrodzenie za pracę (nie liczone).",
    })
    w.zrodlo("KP_1821d")
    w.uwaga("Wniosek o łączenie z pracą: min. 21 dni przed; pracodawca może odmówić z powodu organizacji/rodzaju pracy "
            "(Kodeks pracy art. 182¹e § 2).")
    return w


# ── d) oboje rodzice dzielą się urlopami ──────────────────────────────────
PRZEJECIE_MIN_TYG = {"rezygnacja": "urlop_macierzynski_min_matka_tyg",
                     "orzeczenie_niezdolnosci": "urlop_macierzynski_min_szczegolne_tyg",
                     "szpital_matki": "urlop_macierzynski_min_szczegolne_tyg",
                     "porzucenie_dziecka": "urlop_macierzynski_min_szczegolne_tyg",
                     "zgon_matki": None}
PRZEJECIE_ZRODLA = {"rezygnacja": ["KP_180_4_5", "UZ_29_3_10", "ZAD_s7"],
                    "orzeczenie_niezdolnosci": ["KP_180_6_7", "UZ_29_3_10", "ZAD_s7"],
                    "szpital_matki": ["KP_180_10_11", "UZ_29_3_10", "ZAD_s7"],
                    "porzucenie_dziecka": ["KP_180_12_13", "UZ_29_3_10"],
                    "zgon_matki": ["KP_180_12_13", "UZ_29_3_10", "ZAD_s7"]}


def kalkulator_d(dane: dict, P: dict | None = None) -> Wynik:
    """d) Plan podziału urlopów między rodziców.
    dane: jak w b) + plan: [{rodzic, rodzaj: 'macierzynski'|'uzupelniajacy'|'rodzicielski'|'ojcowski',
          tygodnie|dni, od (opc.), wymiar_pracy (opc.)}]; powód przejęcia macierzyńskiego przez ojca –
          z pola zgon_matki_lub_porzucenie_dziecka (zgon_matki / porzucenie_dziecka) albo
          powod_przejecia_macierzynskiego: 'rezygnacja' | 'orzeczenie_niezdolnosci' | 'szpital_matki'."""
    P = P or PARAMETRY_DOMYSLNE
    w = Wynik("d", "Symulacja: z uprawnień korzystają oboje rodzice")
    w.zrodlo("ZAD_s7", "UZ_29a", "KP_1821a", "KP_180_14", "KP_1831")
    data_porodu = data(dane.get("data_porodu") or dane.get("przewidywana_data_porodu"))
    if not data_porodu:
        data_porodu, w.pokazuj_daty = date(2026, 1, 1), False
    dzieci, n, zz = _dzieci_i_dane_porodu(dane)
    pod = {"matka": _podstawa_osoby(dane.get("matka"), P, w, "matka"),
           "ojciec": _podstawa_osoby(dane.get("ojciec"), P, w, "ojciec")}
    W, R = wymiar_macierzynskiego_tyg(n, P), wymiar_rodzicielskiego_tyg(n, zz, P)
    nieprzen = int(P["urlop_rodzicielski_nieprzenoszalny_tyg"])
    wariant81 = _wariant_81_5(dane, data_porodu, P, w)
    przed = _przed_porodem(dane, P, w)
    U = 0
    if any(c.get("hospitalizacja") for c in dzieci):
        U, opis = oblicz_uzupelniajacy(dzieci, data_porodu, P)
        w.podsumowanie["uzupelniajacy_wyliczenie"] = opis
    plan = dane.get("plan") or []
    zg = dane.get("zgon_matki_lub_porzucenie_dziecka")
    powod = zg if zg in ("zgon_matki", "porzucenie_dziecka") else dane.get("powod_przejecia_macierzynskiego", "rezygnacja")

    kursor = data_porodu - timedelta(days=przed * 7)
    mac_m_po_porodzie = mac_razem = uzup_razem = ojc_razem = 0
    ojc_czesci, rodz_czesci = [], 0
    rodz_tyg = {"matka": Fraction(0), "ojciec": Fraction(0)}
    rodz_w_1_roku = False
    pierwsze_urodziny = urodziny(data_porodu, 1)
    koniec_6 = date(data_porodu.year + int(P["urlop_rodzicielski_do_konca_roku_wieku_lat"]), 12, 31)
    mac_ojca = []

    for seg in plan:
        kto, rodzaj = seg["rodzic"], seg["rodzaj"]
        dni = int(seg["dni"]) if "dni" in seg else int(round(float(seg["tygodnie"]) * 7))
        od = data(seg.get("od"))
        pod_k = pod.get(kto)
        if pod_k is None:
            w.uwaga(f"{kto}: brak prawa do zasiłku – segment „{rodzaj}” bez kwoty.")
        if rodzaj == "ojcowski":
            # Wyłączne prawo ojca, 14 dni, max 2 części ≥ 7 dni, do 12 mies. życia (Kodeks pracy art. 182³).
            if kto != "ojciec":
                w.uwaga("Urlop ojcowski to wyłączne prawo ojca (treść zadania str. 8).")
            od = od or data_porodu
            if od + timedelta(days=dni - 1) >= pierwsze_urodziny:
                w.uwaga("Urlop ojcowski musi się zakończyć przed ukończeniem przez dziecko 12 mies. (Kodeks pracy art. 182³ § 1).")
            if dni < int(P["urlop_ojcowski_min_czesc_dni"]):
                w.uwaga("Część urlopu ojcowskiego krótsza niż tydzień (Kodeks pracy art. 182³ § 1¹).")
            ojc_razem += dni
            ojc_czesci.append(dni)
            w.okres(kto, "ojcowski", dni, _pct(P, "ojcowski"), pod_k, P, ["KP_1823", "ZAL_ojc", "UZ_31_1_3"], od)
            continue
        start = od or kursor
        if rodzaj == "macierzynski":
            # Matka: 100% (81,5% przy jednolitym wniosku); ojciec przejmuje wg powodu (Kodeks pracy art. 180 § 4–13).
            mac_razem += dni
            pct = _pct(P, "jednolity_wniosek_21_dni") if wariant81 else _pct(P, "macierzynski")
            if kto == "matka":
                mac_m_po_porodzie += max(0, (start + timedelta(days=dni) - max(start, data_porodu)).days)
                w.okres(kto, "macierzyński", dni, pct, pod_k, P, ["KP_180_1", "KP_180_2_3", "ZAL_mac"], start)
            else:
                mac_ojca.append(dni)
                w.okres(kto, f"macierzyński (przejęcie: {powod})", dni, pct, pod_k, P, PRZEJECIE_ZRODLA[powod], start)
                if wariant81:
                    w.uwaga("Ojciec przejmujący macierzyński przy wniosku matki o 81,5% – przyjęto 81,5% (art. 31 ust. 3 "
                            "„za cały okres”); do potwierdzenia z ZUS.")
        elif rodzaj == "uzupelniajacy":
            uzup_razem += dni
            w.okres(kto, "uzupełniający macierzyński", dni, _pct(P, "uzupelniajacy"), pod_k, P, ["KP_1802", "ZAL_uzup", "UZ_31_1_3"], start)
        elif rodzaj == "rodzicielski":
            rodz_czesci += 1
            if start < pierwsze_urodziny:
                rodz_w_1_roku = True
            wp = float(seg.get("wymiar_pracy", 0))
            # Stawki: ojciec – pierwsze 9 tyg. 70% (ustawa zasiłkowa art. 31 ust. 3f), dalej z puli matki 81,5% / 70%.
            kawalki = []
            if kto == "ojciec" and wariant81:
                w_9 = max(0, min(dni, nieprzen * 7 - int(rodz_tyg[kto] * 7)))
                if w_9:
                    kawalki.append((w_9, _pct(P, "nieprzenoszalne_9_tyg_drugiego_rodzica"), "rodzicielski (9 tyg. ojca)"))
                if dni - w_9:
                    kawalki.append((dni - w_9, _pct(P, "jednolity_wniosek_21_dni"), "rodzicielski (z puli matki)"))
            elif kto == "matka" and wariant81:
                kawalki.append((dni, _pct(P, "jednolity_wniosek_21_dni"), "rodzicielski"))
            else:
                kawalki.append((dni, _pct(P, "rodzicielski"), "rodzicielski"))
            rodz_tyg[kto] += Fraction(dni, 7)
            s = start
            for dk, pct, et in kawalki:
                s += timedelta(days=_rodzicielski_z_praca(w, kto, dk, wp, pct, pod_k, P, s,
                                                          float(seg.get("wymiar_pracy_w_wydluzeniu", 0)), et))
            if s - timedelta(days=1) > koniec_6:
                w.uwaga("Rodzicielski musi się skończyć do końca roku, w którym dziecko kończy 6 lat (Kodeks pracy art. 182¹c).")
            w.zrodlo("UZ_31_3f", "POR_34")
            kursor = max(kursor, s)
            continue
        else:
            raise ValueError(f"Nieznany rodzaj: {rodzaj}")
        kursor = max(kursor, start + timedelta(days=dni))

    # Walidacja planu – każda reguła z przepisem:
    if mac_razem > W * 7:
        w.uwaga(f"Łączny macierzyński {mac_razem} dni > wymiar {W * 7} dni (Kodeks pracy art. 180 § 14).")
    if mac_ojca:
        klucz = PRZEJECIE_MIN_TYG.get(powod)
        if klucz and mac_m_po_porodzie < int(P[klucz]) * 7:
            w.uwaga(f"Matka wykorzystała po porodzie {mac_m_po_porodzie} dni – ojciec może przejąć macierzyński "
                    f"dopiero po {int(P[klucz])} tyg. (Kodeks pracy art. 180 § 4–13).")
    if U == 0 and uzup_razem:
        w.uwaga("Brak podstaw do uzupełniającego urlopu (brak danych o hospitalizacji/wcześniactwie) – Kodeks pracy art. 180².")
    elif uzup_razem > U * 7:
        w.uwaga(f"Uzupełniający {uzup_razem} dni > przysługujące {U * 7} dni (Kodeks pracy art. 180²).")
    if len({s['rodzic'] for s in plan if s['rodzaj'] == 'uzupelniajacy'}) > 1:
        w.uwaga("Uzupełniający urlop wykorzystuje tylko jeden z rodziców, jednorazowo (treść zadania str. 8).")
    if ojc_razem > int(P["urlop_ojcowski_dni"]) or len(ojc_czesci) > int(P["urlop_ojcowski_max_czesci"]):
        w.uwaga("Urlop ojcowski: max 14 dni w max 2 częściach (Kodeks pracy art. 182³).")
    suma_rodz = rodz_tyg["matka"] + rodz_tyg["ojciec"]
    if suma_rodz > R:
        w.uwaga(f"Łączny rodzicielski {float(suma_rodz):g} tyg. > {R} tyg., także przy jednoczesnym korzystaniu "
                "(Kodeks pracy art. 182¹a § 6, ustawa zasiłkowa art. 29a ust. 3).")
    for kto in ("matka", "ojciec"):
        if rodz_tyg[kto] > R - nieprzen:
            w.uwaga(f"{kto}: {float(rodz_tyg[kto]):g} tyg. rodzicielskiego > {R - nieprzen} tyg. "
                    "(9 tyg. drugiego rodzica nieprzenoszalne – Kodeks pracy art. 182¹a § 4).")
    if rodz_czesci > int(P["urlop_rodzicielski_max_czesci"]):
        w.uwaga(f"{rodz_czesci} części rodzicielskiego > 5 (Kodeks pracy art. 182¹c; treść zadania str. 7).")
    if wariant81 and not rodz_w_1_roku:
        # Brak rodzicielskiego w 1. roku życia → rodzicielski 70% + wyrównanie macierzyńskiego do 100%
        # (ustawa zasiłkowa str. 9, art. 31 ust. 3g i 4). Wyrównanie = (stawka 100% − stawka 81,5%) × dni macierzyńskiego.
        w.zrodlo("UZ_31_3g_4")
        w.uwaga("Wariant 81,5%, ale żaden dzień rodzicielskiego nie wypada w 1. roku życia: rodzicielski 70%, "
                "macierzyński do wyrównania do 100% na wniosek (ustawa zasiłkowa art. 31 ust. 3g i 4).")
        for o in w.okresy:
            if o["kto"] == "matka" and o["rodzaj"].startswith("rodzicielski") and pod["matka"] is not None:
                dz, mies, _ = stawka_dzienna(pod["matka"], _pct(P, "rodzicielski"), P, o["wymiar_pracy"])
                o.update(procent=float(_pct(P, "rodzicielski")), stawka_dzienna=dz, kwota_miesieczna=mies, kwota_laczna=zl(dz * o["dni"]))
                o["uwagi"].append("Przeliczono na 70% – ustawa zasiłkowa art. 31 ust. 3g.")
        if pod["matka"] is not None:
            dz100, _, _ = stawka_dzienna(pod["matka"], _pct(P, "macierzynski"), P)
            dz81, _, _ = stawka_dzienna(pod["matka"], _pct(P, "jednolity_wniosek_21_dni"), P)
            w.podsumowanie["jednorazowe_wyrownanie_macierzynskiego_zl"] = zl((dz100 - dz81) * mac_m_po_porodzie)
    if wariant81 and rodz_tyg["matka"] < R - nieprzen:
        w.uwaga("Jednolity wniosek dotyczy pełnego wymiaru – plan matki go nie wyczerpuje; ustawa nie przewiduje wprost "
                "korekty stawki (poza art. 31 ust. 3g) – sprawdź z ZUS.")
    w.podsumowanie.update({
        "wymiar_macierzynskiego_tyg": W, "wymiar_rodzicielskiego_tyg": R, "wymiar_uzupelniajacego_tyg": U,
        "rodzicielski_matka_tyg": float(rodz_tyg["matka"]), "rodzicielski_ojciec_tyg": float(rodz_tyg["ojciec"]),
        "wariant": "81,5%" if wariant81 else "100% + 70%",
    })
    return w


# ── e) / j) adopcja i rodzina zastępcza ───────────────────────────────────
def kalkulator_e(dane: dict, P: dict | None = None, podpunkt: str = "e") -> Wynik:
    """e) / j) Zasiłek przy przyjęciu dziecka na wychowanie.
    dane: dzieci: [{data_urodzenia, odroczony_obowiazek_szkolny, zaswiadczenie_za_zyciem, …,
                    przyjete_na_wychowanie: {rodzaj, data_przyjecia, data_wystapienia_do_sadu, data_uprawomocnienia}}]
          (format schematu) albo pola rodzaj / data_przyjecia / … na poziomie głównym;
          jednolity_wniosek_81_5_procent, wykorzystane_jako_rodzina_zastepcza{na_warunkach_tyg, rodzicielski_tyg},
          opiekun1{…}, opiekun2{…, ojciec: bool}."""
    P = P or PARAMETRY_DOMYSLNE
    tytul = ("Rodzice adopcyjni i rodzina zastępcza niezawodowa" if podpunkt == "e"
             else "Rodzice adopcyjni i rodzina zastępcza (w tym rozróżnienie zawodowa/niezawodowa)")
    w = Wynik(podpunkt, tytul + " – okres i wysokość")
    w.zrodlo("ZAD_s8", "ZAD_s9", "UZ_29_1_2", "ZAL_przyj", "POR_30", "KP_1831", "ROZ_15_16")
    dzieci = dane.get("dzieci") or []
    przyj_obj = next((c.get("przyjete_na_wychowanie") for c in dzieci if c.get("przyjete_na_wychowanie")), None) or {}
    rodzaj = przyj_obj.get("rodzaj") or dane.get("rodzaj", "przysposobienie")
    # KROK 0 – rodzina zastępcza zawodowa: brak prawa (Kodeks pracy str. 8, art. 183 § 1 i § 4; ustawa zasiłkowa art. 29 ust. 1 pkt 3).
    if rodzaj == "rodzina_zastepcza_zawodowa":
        w.zrodlo("KP_183_1")
        w.uwaga("Rodzina zastępcza ZAWODOWA nie ma prawa do urlopu na warunkach urlopu macierzyńskiego ani zasiłku "
                "macierzyńskiego (Kodeks pracy art. 183 § 1 i § 4; ustawa zasiłkowa art. 29 ust. 1 pkt 3).")
        w.podsumowanie["uprawnienie"] = "brak"
        return w
    adopcja = rodzaj == "przysposobienie"
    if not dzieci or not dzieci[0].get("data_urodzenia"):
        raise ValueError("Podaj dzieci[].data_urodzenia – wymiar zależy od wieku dziecka (Kodeks pracy art. 183).")
    przyj = data(przyj_obj.get("data_przyjecia") or dane.get("data_przyjecia"))
    wystap = data(przyj_obj.get("data_wystapienia_do_sadu") or dane.get("data_wystapienia_do_sadu"))
    upr = data(przyj_obj.get("data_uprawomocnienia") or dane.get("data_uprawomocnienia"))
    # Przy przysposobieniu prawo powstaje po przyjęciu I wystąpieniu do sądu (ustawa zasiłkowa art. 29 ust. 1 pkt 2).
    zdarzenie = max(przyj, wystap or przyj) if adopcja else przyj
    start = data(dane.get("data_rozpoczecia_urlopu")) or zdarzenie
    if (start - zdarzenie).days > int(P["termin_rozpoczecia_na_warunkach_dni"]):
        w.uwaga("Urlop na warunkach urlopu macierzyńskiego rozpoczyna się najpóźniej 21 dni od przyjęcia (Kodeks pracy art. 183 § 6).")
    w.zrodlo("KP_183_5_6")
    n = len(dzieci) if len(dzieci) > 1 else int(dane.get("liczba_dzieci") or 1)
    zz = any(c.get("zaswiadczenie_za_zyciem") for c in dzieci)
    najml = max(dzieci, key=lambda c: data(c["data_urodzenia"]))
    w.zrodlo("KP_183_11" if adopcja else "KP_183_1")
    wp = wymiar_przyjecia(data(najml["data_urodzenia"]), rodzaj, bool(najml.get("odroczony_obowiazek_szkolny")),
                          n, zz, start, P)
    # Warunek wieku w dniu przyjęcia (ustawa zasiłkowa str. 7, art. 29 ust. 1 pkt 2–3).
    if przyj >= wp["granica"]:
        w.uwaga(f"Dziecko miało w dniu przyjęcia ≥ {wp['wiek_limit']} lat → brak prawa (ustawa zasiłkowa art. 29 ust. 1).")
        w.podsumowanie["uprawnienie"] = "brak"
        return w
    if len(dzieci) > 1:
        w.uwaga("Kilkoro dzieci: limit wieku liczony dla najmłodszego dziecka – interpretacja.")
    o1, o2 = dane.get("opiekun1") or {}, dane.get("opiekun2")
    p1 = _podstawa_osoby(o1, P, w, "opiekun 1")
    p2 = _podstawa_osoby(o2, P, w, "opiekun 2") if o2 else None
    wariant81 = _wariant_81_5(dane, zdarzenie, P, w)
    wym, par3, R, R_dni = wp["na_warunkach_dni"], wp["par3"], wp["R_tyg"], wp["R_dni"]
    if par3:
        w.zrodlo("KP_183_3")
        w.uwaga("Wymiar ograniczony wiekiem byłby < 9 tyg. → 9 tyg. (Kodeks pracy art. 183 § 3; Załącznik „Minimalny okres”); "
                "przyjęto „przypadek z § 3”, w którym rodzicielski wynosi 38/62 tyg. (interpretacja).")
    elif wp["skrocony"]:
        w.uwaga(f"Wymiar skrócony do dnia przed ukończeniem przez dziecko {wp['wiek_limit']} lat (Kodeks pracy art. 183 § 1/§ 1¹).")
    # KROK 5 – przysposobienie po pieczy zastępczej: pomniejszenie o wykorzystany urlop (Kodeks pracy str. 9, art. 183 § 7–8).
    wyk = dane.get("wykorzystane_jako_rodzina_zastepcza") or {}
    if adopcja and wyk:
        w.zrodlo("KP_183_7_8")
        wym = max(0, wym - int(round(float(wyk.get("na_warunkach_tyg", 0)) * 7)))
        R_dni = max(0, R_dni - int(round(float(wyk.get("rodzicielski_tyg", 0)) * 7)))
        w.uwaga("Przysposobienie po pieczy zastępczej: wymiar pomniejszony o wykorzystany urlop (Kodeks pracy art. 183 § 7–8).")
    w.zrodlo("KP_183_4", "POR_32")
    if adopcja and not par3 and R_dni < R * 7:
        w.uwaga("Rodzicielski przy przysposobieniu nie dłużej niż do ukończenia przez dziecko 14 lat (Kodeks pracy art. 183 § 4¹).")
    if not adopcja:
        w.uwaga("Rodzina zastępcza: Kodeks pracy art. 183 § 4 nie podaje limitu wieku dla rodzicielskiego, a § 5 odsyła do "
                "art. 182¹c (do końca roku 6 r.ż.) – nie zastosowano; do potwierdzenia z ZUS.")
    nieprzen = int(P["urlop_rodzicielski_nieprzenoszalny_tyg"]) * 7
    # KROK 6 – kwoty: na warunkach 100% (81,5%), rodzicielski 70% (81,5%), 9 tyg. drugiego opiekuna 70%
    # (ustawa zasiłkowa str. 9, art. 31 ust. 1–3 i 3f; art. 30a ust. 2 – wniosek do 21 dni od przyjęcia).
    pct_mac = _pct(P, "jednolity_wniosek_21_dni") if wariant81 else _pct(P, "na_warunkach_macierzynskiego")
    pct_r1 = _pct(P, "jednolity_wniosek_21_dni") if wariant81 else _pct(P, "rodzicielski")
    kursor = start
    if p1 is not None or not o2:
        w.okres("opiekun 1", "na warunkach urlopu macierzyńskiego", wym, pct_mac, p1, P,
                ["KP_183_11" if adopcja else "KP_183_1", "ZAL_przyj", "UZ_31_1_3"], kursor)
        kursor += timedelta(days=wym)
        if any(c.get("hospitalizacja") for c in dzieci):
            # Uzupełniający, jeśli pobyt w szpitalu był po przyjęciu (Kodeks pracy str. 8, art. 183 § 3¹).
            U, opis = oblicz_uzupelniajacy(dzieci, data(najml["data_urodzenia"]), P, od_daty=przyj)
            w.podsumowanie["uzupelniajacy_wyliczenie"] = opis
            w.zrodlo("KP_183_31", "KP_1802")
            if U:
                w.okres("opiekun 1", "uzupełniający macierzyński", U * 7, _pct(P, "uzupelniajacy"), p1, P,
                        ["KP_183_31", "KP_1802", "UZ_31_1_3"], kursor)
                kursor += timedelta(days=U * 7)
        d1 = R_dni - nieprzen       # 9 tyg. drugiego opiekuna nieprzenoszalne (Kodeks pracy art. 182¹a § 4 przez art. 183 § 5)
        if o2 and p2 is None:
            w.uwaga("Drugi opiekun bez prawa do zasiłku – jego 9 tyg. nie przechodzi na opiekuna 1.")
        if not o2:
            w.uwaga("Jeden opiekun: policzono R − 9 tyg. Sytuacji osoby samotnie przysposabiającej pliki nie opisują.")
        w.okres("opiekun 1", "rodzicielski", max(0, d1), pct_r1, p1, P, ["KP_183_4", "UZ_31_1_3", "ZAL_rodz"], kursor)
        kursor += timedelta(days=max(0, d1))
    if o2 and p2 is not None:
        w.okres("opiekun 2", "rodzicielski (9 tyg. drugiego rodzica)", min(nieprzen, R_dni),
                _pct(P, "nieprzenoszalne_9_tyg_drugiego_rodzica"), p2, P, ["KP_183_4", "UZ_31_3f", "POR_34"], kursor)
        if adopcja and o2.get("ojciec"):
            # Ojcowski przy przysposobieniu: 12 mies. od uprawomocnienia, ≤ 14 r.ż. (Kodeks pracy art. 182³ § 1 pkt 2).
            od_o = upr or start
            if upr and od_o + timedelta(days=13) >= min(dodaj_miesiace(upr, 12), wp["granica"]):
                w.uwaga("Ojcowski: do 12 mies. od uprawomocnienia przysposobienia, nie dłużej niż do 14 r.ż.")
            if not upr:
                w.uwaga("Ojcowski przy przysposobieniu – podaj data_uprawomocnienia (Kodeks pracy art. 182³ § 1 pkt 2).")
            w.okres("opiekun 2", "ojcowski (przysposobienie)", int(P["urlop_ojcowski_dni"]), _pct(P, "ojcowski"), p2, P,
                    ["KP_1823", "ZAL_ojc", "UZ_31_1_3"], od_o)
    if not adopcja and o2 and o2.get("ojciec"):
        w.uwaga("Urlop ojcowski dotyczy ojca biologicznego i adopcyjnego (Kodeks pracy art. 182³, treść zadania str. 8) – "
                "dla rodziny zastępczej nie liczono.")
    w.podsumowanie.update({
        "rodzaj": rodzaj, "liczba_dzieci_przyjetych": n, "za_zyciem": zz,
        "limit_wieku_lat": wp["wiek_limit"], "dziecko_konczy_limit": wp["granica"].isoformat(),
        "wymiar_na_warunkach_macierzynskiego_dni": wym, "przypadek_art_183_par_3": par3,
        "wymiar_rodzicielskiego_tyg": R, "rodzicielski_po_ograniczeniach_dni": R_dni,
        "wariant": "81,5%" if wariant81 else "100% + 70%",
    })
    return w


def kalkulator_j(dane: dict, P: dict | None = None) -> Wynik:
    """j) – to samo co e), obejmuje też rodzinę zastępczą zawodową (wynik „brak prawa” z podstawą prawną)."""
    return kalkulator_e(dane, P, podpunkt="j")


# ── f) konkretna sprawa z indywidualną podstawą ──────────────────────────
def kalkulator_f(dane: dict, P: dict | None = None) -> Wynik:
    """f) Symulacja konkretnej sprawy (np. z zestawu ZUS) z indywidualną podstawą wymiaru.
    Wejście: dane użytkownika w formacie zmienne_uzytkownika.json (płaskie) – wnioskodawca na poziomie głównym,
    drugi rodzic w obiekcie drugi_rodzic (może zawierać podstawa_wymiaru_12_miesiecy – pole dodatkowe).
    Rola wnioskodawcy z PESEL (sprawdzanie_swiadczen.rola_wnioskodawcy). Uruchamia e) przy przyjęciu dziecka,
    d) gdy jest plan czesci_urlopu_rodzicielskiego, w pozostałych przypadkach b)."""
    P = P or PARAMETRY_DOMYSLNE
    rola = rola_wnioskodawcy(dane) or "matka"
    inna = "ojciec" if rola == "matka" else "matka"
    dzieci = dane.get("dzieci") or []
    data_porodu = dane.get("przewidywana_data_porodu") if dane.get("w_ciazy") else \
        (max((c.get("data_urodzenia") for c in dzieci if c.get("data_urodzenia")), default=None))
    wnioskodawca = {k: v for k, v in dane.items() if k not in ("dzieci", "drugi_rodzic")}
    drugi = dict(dane.get("drugi_rodzic") or {}) or None
    for o in (wnioskodawca, drugi):
        if o and not o.get("data_powstania_prawa"):
            o["data_powstania_prawa"] = data_porodu
    wsp = {"dzieci": dzieci, "jednolity_wniosek_81_5_procent": dane.get("jednolity_wniosek_81_5_procent"),
           "data_porodu": data_porodu, "liczba_dzieci_przy_porodzie": dane.get("liczba_dzieci_przy_porodzie"),
           "urlop_macierzynski": dane.get("urlop_macierzynski"), rola: wnioskodawca, inna: drugi,
           "uzupelniajacy_dla": (dane.get("urlop_uzupelniajacy") or {}).get("rodzic", "matka"),
           "zgon_matki_lub_porzucenie_dziecka": dane.get("zgon_matki_lub_porzucenie_dziecka")}
    if any(c.get("przyjete_na_wychowanie") for c in dzieci):
        w = kalkulator_e({"dzieci": dzieci, "jednolity_wniosek_81_5_procent": dane.get("jednolity_wniosek_81_5_procent"),
                          "opiekun1": wnioskodawca, "opiekun2": drugi}, P)
    elif dane.get("czesci_urlopu_rodzicielskiego"):
        _, n, _ = _dzieci_i_dane_porodu(wsp)
        segs = [{"rodzic": "matka", "rodzaj": "macierzynski", "tygodnie": wymiar_macierzynskiego_tyg(n, P)}]
        for c in dane["czesci_urlopu_rodzicielskiego"]:
            segs.append({"rodzic": c["rodzic"], "rodzaj": "rodzicielski", "od": c["od"],
                         "dni": (data(c["do"]) - data(c["od"])).days + 1, "wymiar_pracy": c.get("wymiar_pracy_w_trakcie") or 0})
        for c in dane.get("czesci_urlopu_ojcowskiego") or []:
            segs.append({"rodzic": "ojciec", "rodzaj": "ojcowski", "od": c["od"], "dni": (data(c["do"]) - data(c["od"])).days + 1})
        wsp["plan"] = segs
        w = kalkulator_d(wsp, P)
    else:
        w = kalkulator_b(wsp, P)
    w.podpunkt, w.tytul = "f", "Konkretna sprawa z indywidualną podstawą wymiaru → " + w.tytul
    return w


KALKULATORY = {"b": kalkulator_b, "c": kalkulator_c, "d": kalkulator_d,
               "e": kalkulator_e, "f": kalkulator_f, "j": kalkulator_j}


def oblicz(dane: dict, P: dict | None = None) -> dict:
    """Punkt wejścia dla kalkulatorów scenariuszowych: dane['podpunkt'] ∈ {b,c,d,e,f,j} → JSON."""
    return KALKULATORY[dane["podpunkt"]](dane, P or PARAMETRY_DOMYSLNE).jako_slownik()


# ═══════════════════════════════════════════════════════════════════════════
# 6. DANE PRZYKŁADOWE (używane w testach)
# ═══════════════════════════════════════════════════════════════════════════
def _m(rok: int, od: int, do: int, kwota: float, dp: int = 20, dd: int = 20) -> list[dict]:
    return [{"rok": rok, "miesiac": m, "podstawa_wymiaru_skladek": kwota, "dni_przepracowane": dp,
             "dni_do_przepracowania": dd} for m in range(od, do + 1)]


PRZYKLADOWY_UZYTKOWNIK: dict = {   # ciężarna pracownica, mąż na JDG – format zmienne_uzytkownika.json
    "imie": "Anna", "pesel": "92071512346", "stan_cywilny": "zonaty_zamezna",
    "tytul_ubezpieczenia": "umowa_o_prace", "ubezpieczenie_chorobowe": "obowiazkowe",
    "data_objecia_ubezpieczeniem_chorobowym": "2021-03-01", "data_ustania_ubezpieczenia": None,
    "platnik_liczba_ubezpieczonych_chorobowo": 120, "wymiar_etatu": 1.0,
    "podstawa_wymiaru_12_miesiecy": _m(2025, 11, 12, 7000) + _m(2026, 1, 10, 7200),
    "w_ciazy": True, "przewidywana_data_porodu": "2027-02-10", "liczba_dzieci_przy_porodzie": 1,
    "opieka_medyczna_od_10_tyg": True, "okres_zasilkowy_wykorzystany_dni": 0,
    "dzieci": [{"zaswiadczenie_za_zyciem": False}],          # oczekiwane dziecko (bez data_urodzenia)
    "drugi_rodzic": {"imie": "Piotr", "tytul_ubezpieczenia": "jdg"},
    "urlop_macierzynski": {"tygodnie_przed_porodem": 2},
    "jednolity_wniosek_81_5_procent": {"czy": True, "data_zlozenia": None},
    "dochod_na_osobe": 3100,
}

PRZYKLADY: dict[str, dict] = {
    "b": {"podpunkt": "b", "data_porodu": "2026-12-01", "liczba_dzieci_przy_porodzie": 2,
          "zaswiadczenie_za_zyciem": True, "urlop_macierzynski": {"tygodnie_przed_porodem": 2},
          "jednolity_wniosek_81_5_procent": {"czy": True, "data_zlozenia": "2026-12-10"},
          "dzieci": [{"tydzien_ciazy_przy_urodzeniu": 32, "masa_urodzeniowa_g": 1400,
                      "hospitalizacja": [{"od": "2026-12-01", "do": "2026-12-24"}]},
                     {"tydzien_ciazy_przy_urodzeniu": 32, "masa_urodzeniowa_g": 1550,
                      "hospitalizacja": [{"od": "2026-12-01", "do": "2026-12-18"}]}],
          "matka": {"tytul_ubezpieczenia": "umowa_o_prace", "podstawa": 6000, "platnik_liczba_ubezpieczonych_chorobowo": 120},
          "ojciec": {"tytul_ubezpieczenia": "jdg", "podstawa": 4500}},
    "c": {"podpunkt": "c", "liczba_dzieci_przy_porodzie": 1,
          "osoba": {"tytul_ubezpieczenia": "umowa_o_prace", "podstawa": 7000},
          "wariant": "70", "czesci_urlopu_rodzicielskiego": [
              {"rodzic": "matka", "od": "2027-05-01", "do": "2027-08-20", "wymiar_pracy_w_trakcie": 0.5},
              {"rodzic": "matka", "od": "2027-10-16", "do": "2028-02-04", "wymiar_pracy_w_trakcie": 0}]},
    "d": {"podpunkt": "d", "data_porodu": "2026-12-01", "liczba_dzieci_przy_porodzie": 1,
          "jednolity_wniosek_81_5_procent": {"czy": False}, "matka": {"podstawa": 8000}, "ojciec": {"podstawa": 10000},
          "powod_przejecia_macierzynskiego": "rezygnacja",
          "plan": [{"rodzic": "matka", "rodzaj": "macierzynski", "tygodnie": 14},
                   {"rodzic": "ojciec", "rodzaj": "macierzynski", "tygodnie": 6},
                   {"rodzic": "ojciec", "rodzaj": "ojcowski", "dni": 14, "od": "2026-12-01"},
                   {"rodzic": "matka", "rodzaj": "rodzicielski", "tygodnie": 20},
                   {"rodzic": "ojciec", "rodzaj": "rodzicielski", "tygodnie": 12, "wymiar_pracy": 0.25}]},
    "e": {"podpunkt": "e", "dzieci": [{"data_urodzenia": "2019-06-15", "przyjete_na_wychowanie": {
              "rodzaj": "przysposobienie", "data_przyjecia": "2026-11-02", "data_wystapienia_do_sadu": "2026-11-05",
              "data_uprawomocnienia": "2027-03-01"}}],
          "jednolity_wniosek_81_5_procent": {"czy": True, "data_zlozenia": "2026-11-20"},
          "opiekun1": {"podstawa": 5200}, "opiekun2": {"podstawa": 6100, "ojciec": True}},
    "j": {"podpunkt": "j", "dzieci": [{"data_urodzenia": "2019-12-20", "odroczony_obowiazek_szkolny": False,
                                       "przyjete_na_wychowanie": {"rodzaj": "rodzina_zastepcza_niezawodowa",
                                                                  "data_przyjecia": "2026-10-01"}}],
          "opiekun1": {"podstawa": 4800}},
    "f": dict(PRZYKLADOWY_UZYTKOWNIK, podpunkt="f",
              drugi_rodzic={"imie": "Piotr", "tytul_ubezpieczenia": "jdg",
                            "zadeklarowana_podstawa_jdg": [{"rok": 2026, "miesiac": m, "kwota": 6000} for m in range(1, 11)]}),
}


# ── Podgląd z konsoli ──────────────────────────────────────────────────────
#   python3 kalkulator_zasilku.py dane_uzytkownika.json [--data RRRR-MM-DD] [--szczegoly] [--json]
#                                                       [--param zmienne_uzytkownika.json]
#   --szczegoly – pod każdym świadczeniem uwagi i źródła (plik + strona);  --json – pełna lista jako JSON.
#   Plik ze scenariuszem ({"podpunkt": "b", …}) → wynik kalkulatora scenariuszowego jako JSON.
# Ten blok wykonuje się WYŁĄCZNIE przy uruchomieniu pliku z konsoli. Przy imporcie
# (from kalkulator_zasilku import …) nic się nie wypisuje – funkcje tylko zwracają listy.
if __name__ == "__main__":
    import json
    import sys
    try:
        from .zrodla_i_parametry import wczytaj_parametry
    except ImportError:
        from zrodla_i_parametry import wczytaj_parametry

    argumenty = sys.argv[1:]

    def _opcja(nazwa: str) -> str | None:
        if nazwa in argumenty:
            i = argumenty.index(nazwa)
            wartosc = argumenty[i + 1]
            del argumenty[i:i + 2]
            return wartosc
        return None

    parametry = wczytaj_parametry(_opcja("--param"))
    ref = _opcja("--data")
    ref = date.fromisoformat(ref) if ref else None
    szczegoly, jako_json = "--szczegoly" in argumenty, "--json" in argumenty
    argumenty = [a for a in argumenty if a not in ("--szczegoly", "--json")]
    if not argumenty:
        sys.exit("Użycie: python3 kalkulator_zasilku.py dane_uzytkownika.json "
                 "[--data RRRR-MM-DD] [--szczegoly] [--json] [--param zmienne_uzytkownika.json]")
    with open(argumenty[0], encoding="utf-8") as f:
        wczytane = json.load(f)
    for osoba in (wczytane if isinstance(wczytane, list) else [wczytane]):     # plik: jedna osoba albo lista osób
        if "podpunkt" in osoba:
            print(json.dumps(oblicz(osoba, parametry), ensure_ascii=False, indent=2))
            continue
        lista = oblicz_wszystkie_swiadczenia(osoba, parametry, ref)
        if jako_json:
            print(json.dumps(lista, ensure_ascii=False, indent=2))
            continue
        for r in lista:
            print(r["komunikat"])
            if szczegoly:
                for u in r["uwagi"]:
                    print(f"    ↳ {u}")
                for z in r["zrodla"]:
                    print(f"    [{z['klucz']}] {z['plik']}, {z['strona']}")
        print()
