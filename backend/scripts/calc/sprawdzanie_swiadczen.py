# -*- coding: utf-8 -*-
"""
sprawdzanie_swiadczen.py
========================
Osobny moduł: sprawdza, czy dane użytkownika spełniają wymagania KAŻDEGO świadczenia
z katalogu i zwraca jeden z trzech stanów:

    Status.SPELNIA      – dane spełniają wymagania,
    Status.BRAK_DANYCH  – brakuje danych, żeby to rozstrzygnąć (lista brakujących pól),
    Status.NIE_SPELNIA  – dane nie spełniają wymagań (z powodem i źródłem).

Moduł NIE liczy kwot – to robi kalkulator_zasilku.py. Można go używać samodzielnie:

    from sprawdzanie_swiadczen import sprawdz_wszystkie_jako_slowniki
    lista = sprawdz_wszystkie_jako_slowniki(dane_uzytkownika)   # → list[dict], nic nie wypisuje

Dane użytkownika to płaski słownik z kluczami takimi jak w zmienne_uzytkownika.json
(wersja zaktualizowana): "pesel", "w_ciazy", "tytul_ubezpieczenia", "dzieci": [{…}],
"urlop_macierzynski": {…}, "jednolity_wniosek_81_5_procent": {…} itd. Pola dziecka
(„dziecko.X” w schemacie) są w elementach listy "dzieci". Brakujące pola są zgłaszane
dokładnie pod nazwami ze schematu.

Zasada kolejności w każdej funkcji sprawdzającej:
  1) najpierw warunki, które na podstawie dostępnych danych od razu WYKLUCZAJĄ świadczenie
     (wtedy NIE_SPELNIA – nie ma sensu prosić o resztę danych),
  2) potem zbieranie brakujących danych (wtedy BRAK_DANYCH),
  3) jeśli niczego nie brakuje – SPELNIA, a w `fakty` zostają ustalenia potrzebne kalkulatorowi.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

# Import działa w obu trybach: jako pakiet (np. z backendu: from scripts.calc.sprawdzanie_swiadczen import …)
# i z katalogu calc (skrypty i testy obok).
try:
    from .zrodla_i_parametry import (BRAK, PARAMETRY_DOMYSLNE, TYTULY_BEZ_ZASILKU_ZUS, TYTULY_JDG,
                                TYTULY_PRACOWNIK, ZRODLA, data, dodaj_miesiace, normalizuj_dane,
                                pole, urodziny)
except ImportError:
    from zrodla_i_parametry import (BRAK, PARAMETRY_DOMYSLNE, TYTULY_BEZ_ZASILKU_ZUS, TYTULY_JDG,
                                TYTULY_PRACOWNIK, ZRODLA, data, dodaj_miesiace, normalizuj_dane,
                                pole, urodziny)


# ═══════════════════════════════════════════════════════════════════════════
# 1. TYPY WYNIKU
# ═══════════════════════════════════════════════════════════════════════════
class Status(str, Enum):
    SPELNIA = "SPELNIA"
    BRAK_DANYCH = "BRAK_DANYCH"
    NIE_SPELNIA = "NIE_SPELNIA"


# Tryby wypłaty decydują o formacie komunikatu w kalkulatorze:
#   "miesiecznie" – kwota/miesiąc + okres działania,
#   "jednorazowo" – kwota/jednorazowo + okres na złożenie wniosku,
#   "urlop"       – urlop płatny: podstawa × procent na okres urlopu.
@dataclass
class WynikSprawdzenia:
    kod: str
    nazwa: str
    tryb_wyplaty: str
    status: Status
    brakujace_dane: list[str] = field(default_factory=list)
    powody: list[str] = field(default_factory=list)
    zrodla: list[str] = field(default_factory=list)
    uwagi: list[str] = field(default_factory=list)
    fakty: dict = field(default_factory=dict)

    def komunikat(self) -> str:
        """Komunikat w formacie ustalonym przez zespół (bez kwot – kwoty dokłada kalkulator)."""
        if self.status == Status.BRAK_DANYCH:
            return f"WARNING: {self.nazwa} – brakuje danych: {', '.join(self.brakujace_dane)}"
        if self.status == Status.NIE_SPELNIA:
            return f"Nie masz możliwości uzyskania: {self.nazwa} – {'; '.join(self.powody)}"
        return f"Możesz uzyskać: {self.nazwa} (spełniasz warunki)"

    def jako_slownik(self) -> dict:
        return {
            "kod": self.kod, "nazwa": self.nazwa, "tryb_wyplaty": self.tryb_wyplaty,
            "status": self.status.value, "komunikat": self.komunikat(),
            "brakujace_dane": self.brakujace_dane, "powody": self.powody, "uwagi": self.uwagi,
            "zrodla": [{"klucz": k, "plik": ZRODLA[k][0], "strona": ZRODLA[k][1], "opis": ZRODLA[k][2]}
                       for k in self.zrodla],
        }


class _Spr:
    """Pomocnik jednej funkcji sprawdzającej: zbiera braki, źródła, uwagi i fakty."""

    def __init__(self, kod: str, ctx: "Kontekst"):
        self.kod, self.ctx = kod, ctx
        self.braki: list[str] = []
        self.zr: list[str] = []
        self.uwagi: list[str] = []
        self.fakty: dict = {}
        self.powod: str | None = None   # ustawiany przez funkcje pomocnicze przy wykluczeniu

    def pole(self, klucz: str) -> Any:
        return pole(self.ctx.dane, klucz)

    def wymagaj(self, klucz: str, nazwa: str | None = None) -> Any:
        """Odczytuje pole; jeśli go nie ma (lub jest null), dopisuje je do listy braków."""
        v = self.pole(klucz)
        if v is BRAK or v is None:
            self.brak(nazwa or klucz)
            return BRAK
        return v

    def brak(self, nazwa: str) -> None:
        if nazwa not in self.braki:
            self.braki.append(nazwa)

    def zrodlo(self, *klucze: str) -> None:
        for k in klucze:
            if k not in ZRODLA:
                raise KeyError(k)
            if k not in self.zr:
                self.zr.append(k)

    def uwaga(self, tekst: str) -> None:
        if tekst not in self.uwagi:
            self.uwagi.append(tekst)

    def _wynik(self, status: Status, powody: list[str]) -> WynikSprawdzenia:
        meta = KATALOG_SWIADCZEN[self.kod]
        return WynikSprawdzenia(self.kod, meta["nazwa"], meta["tryb_wyplaty"], status,
                                list(self.braki) if status == Status.BRAK_DANYCH else [],
                                powody, list(self.zr), list(self.uwagi), dict(self.fakty))

    def nie(self, powod: str, *zrodla: str) -> WynikSprawdzenia:
        self.zrodlo(*zrodla)
        return self._wynik(Status.NIE_SPELNIA, [powod])

    def koniec(self) -> WynikSprawdzenia:
        return self._wynik(Status.BRAK_DANYCH if self.braki else Status.SPELNIA, [])


@dataclass
class Kontekst:
    dane: dict
    P: dict = field(default_factory=lambda: PARAMETRY_DOMYSLNE)
    dzis: date = field(default_factory=date.today)


# ═══════════════════════════════════════════════════════════════════════════
# 2. REGUŁY WYMIARU (używane też przez kalkulator)
# ═══════════════════════════════════════════════════════════════════════════
def wymiar_macierzynskiego_tyg(liczba_dzieci: int, P: dict) -> int:
    """Wymiar urlopu macierzyńskiego: 1 dziecko 20 tyg., 2 – 31, 3 – 33, 4 – 35, 5+ – 37.
    Źródło: Kodeks_pracy_wyciąg_z_przepisów.pdf str. 3, art. 180 § 1; Załącznik…docx, tabela
    „urlop macierzyński”; Poradnik_dla_rodziców_ZUS_2026.pdf str. 30 (PDF 31).
    Ten sam wymiar przy przyjęciu dziecka: Kodeks pracy str. 8, art. 183 § 1 i § 1¹."""
    t = P["urlop_macierzynski_tyg"]
    return int(t[str(liczba_dzieci)] if liczba_dzieci < 5 else t["5+"])


def wymiar_rodzicielskiego_tyg(liczba_dzieci: int, za_zyciem: bool, P: dict) -> int:
    """Wymiar urlopu rodzicielskiego: 41 tyg. (1 dziecko), 43 (więcej), z „Za życiem” 65/67.
    Źródło: Kodeks_pracy_wyciąg_z_przepisów.pdf str. 6, art. 182¹a § 1–2; Załącznik, sekcja
    „Urlop rodzicielski – czas trwania”; Poradnik str. 31–32 (PDF 32–33)."""
    t = P["urlop_rodzicielski_tyg"]
    if za_zyciem:
        return int(t["za_zyciem_1"] if liczba_dzieci == 1 else t["za_zyciem_mnogi"])
    return int(t["1"] if liczba_dzieci == 1 else t["mnogi"])


def limit_z_praca_tyg(liczba_dzieci: int, za_zyciem: bool, P: dict) -> int:
    """Maksymalny łączny czas rodzicielskiego łączonego z pracą: 82/86 tyg., z „Za życiem” 130/134.
    Źródło: Kodeks_pracy_wyciąg_z_przepisów.pdf str. 7, art. 182¹f § 1 i § 1¹; Poradnik str. 32."""
    t = P["urlop_rodzicielski_z_praca_limit_tyg"]
    if za_zyciem:
        return int(t["za_zyciem_1"] if liczba_dzieci == 1 else t["za_zyciem_mnogi"])
    return int(t["1"] if liczba_dzieci == 1 else t["mnogi"])


def oblicz_uzupelniajacy(dzieci: list[dict], data_porodu: date, P: dict,
                         od_daty: date | None = None) -> tuple[int, str]:
    """Wymiar uzupełniającego urlopu macierzyńskiego (w tygodniach) i opis wyliczenia.

    Reguła – Kodeks_pracy_wyciąg_z_przepisów.pdf str. 5, art. 180² § 1–3; Załącznik…docx,
    tabela przypadków 1–6; Poradnik str. 31 (PDF 32):
      pkt 1: poród przed ukończeniem 28. tyg. ciąży LUB masa ≤ 1000 g
             → 1 tydzień urlopu za każdy tydzień pobytu dziecka w szpitalu do upływu 15. tyg. po porodzie;
      pkt 2: poród od 28. do przed 37. tyg. i masa > 1000 g
             → 1 tydzień za każdy tydzień pobytu w szpitalu do upływu 8. tyg. po porodzie;
      pkt 3: poród od 37. tyg., jeśli pobyt w szpitalu trwa ≥ 2 kolejne dni, a pierwszy z nich
             wypada między 5. a 28. dniem po porodzie → 1 tydzień za każdy tydzień pobytu
             od 5. dnia do upływu 8. tyg. po porodzie.
      § 2: przy kilkorgu dzieciach – najniższa masa urodzeniowa i dziecko najdłużej hospitalizowane.
      § 3: okresy pobytu się sumuje, niepełny tydzień zaokrągla w górę.
    Przy przyjęciu na wychowanie liczą się tylko dni po przyjęciu (`od_daty`) – Kodeks pracy str. 8,
    art. 183 § 3¹.

    Konwencja liczenia dni (interpretacja – przepisy jej nie precyzują): dzień porodu = dzień 0
    i pierwszy dzień 1. tygodnia (Kodeks pracy str. 9, art. 183¹ § 2: pierwszy dzień urlopu = dzień
    porodu), „n-ty dzień po porodzie” = data porodu + n dni.
    Hospitalizacja dziecka: [{od, do}] (daty) albo [{dzien_od, dzien_do}] (dni po porodzie)."""
    if not dzieci:
        return 0, "brak danych o dziecku"
    tydz = min(int(c.get("tydzien_ciazy_przy_urodzeniu") or 40) for c in dzieci)
    masa = min(int(c.get("masa_urodzeniowa_g") or 9999) for c in dzieci)       # § 2: najniższa masa
    mx = P["urlop_uzupelniajacy_max_tyg"]
    if tydz < 28 or masa <= 1000:
        kat, okno_od, okno_do, limit = "pkt 1 (przed 28. tyg. lub ≤ 1000 g)", 0, 15 * 7 - 1, int(mx["ponizej_28_tyg_lub_do_1000g"])
    elif tydz < 37:
        kat, okno_od, okno_do, limit = "pkt 2 (28.–37. tyg., > 1000 g)", 0, 8 * 7 - 1, int(mx["od_28_do_37_tyg_powyzej_1000g_lub_hospitalizacja"])
    else:
        kat, okno_od, okno_do, limit = "pkt 3 (od 37. tyg., pobyt od 5. dnia)", 5, 8 * 7 - 1, int(mx["od_28_do_37_tyg_powyzej_1000g_lub_hospitalizacja"])

    def dni_szpitala(c: dict) -> set[int]:
        s: set[int] = set()
        for h in c.get("hospitalizacja") or []:
            if "dzien_od" in h:
                a, b = int(h["dzien_od"]), int(h["dzien_do"])
            else:
                a, b = (data(h["od"]) - data_porodu).days, (data(h["do"]) - data_porodu).days
            s.update(range(a, b + 1))
        if od_daty:
            s = {x for x in s if x >= (od_daty - data_porodu).days}
        return s

    najdluzej = 0
    for c in dzieci:                                 # § 2: dziecko najdłużej hospitalizowane
        s = dni_szpitala(c)
        # pkt 3: warunek ≥ 2 kolejnych dni, z których pierwszy wypada w 5.–28. dniu po porodzie
        if kat.startswith("pkt 3") and not any(x in s and x + 1 in s for x in range(5, 29)):
            continue
        najdluzej = max(najdluzej, len([x for x in s if okno_od <= x <= okno_do]))
    tyg = min(limit, math.ceil(najdluzej / 7)) if najdluzej else 0              # § 3: w górę
    return tyg, f"{kat}: {najdluzej} dni w szpitalu w oknie → {tyg} tyg. (limit {limit})"


def granica_wieku_przyjecia(rodzaj: str, odroczony: bool, P: dict) -> int:
    """Limit wieku dziecka przy przyjęciu: rodzina zastępcza 7 lat (10 przy odroczeniu
    obowiązku szkolnego), przysposobienie 14 lat.
    Źródło: Kodeks pracy str. 8, art. 183 § 1 i § 1¹; ustawa zasiłkowa str. 7, art. 29 ust. 1 pkt 2–3;
    treść zadania str. 8–9."""
    lim = P["wiek_limit_lat"]
    if rodzaj == "przysposobienie":
        return int(lim["przysposobienie"])
    return int(lim["rodzina_zastepcza_odroczony_obowiazek"] if odroczony else lim["rodzina_zastepcza"])


# ═══════════════════════════════════════════════════════════════════════════
# 3. USTALENIA WSPÓLNE (rola, zdarzenie, ubezpieczenie, …)
# ═══════════════════════════════════════════════════════════════════════════
def _pesel_ok(p: Any) -> bool:
    return isinstance(p, str) and len(p) == 11 and p.isdigit()


def _data_z_pesel(p: str) -> date | None:
    """Data urodzenia z PESEL (miesiąc +20 dla 2000–2099, +80 dla 1800–1899).
    Reguła numeru PESEL – wiedza ogólna, nie z plików ZUS; schemat zmienne_uzytkownika.json
    opisuje data_urodzenia jako „wyliczana z PESEL”."""
    rr, mm, dd = int(p[0:2]), int(p[2:4]), int(p[4:6])
    wiek = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}[(mm // 20) * 20]
    try:
        return date(wiek + rr, mm % 20, dd)
    except ValueError:
        return None


def _rola(s: _Spr) -> str | None:
    """'matka' albo 'ojciec' (rodzic biologiczny); przy przyjęciu dziecka rola wpływa tylko na
    urlop ojcowski. Ustalenie: 10. cyfra PESEL parzysta = kobieta (reguła numeru PESEL – wiedza
    ogólna); bez PESEL: w_ciazy = true → matka. Inaczej zgłaszamy brak pola „pesel”."""
    p = s.pole("pesel")
    if _pesel_ok(p):
        return "matka" if int(p[9]) % 2 == 0 else "ojciec"
    if s.pole("w_ciazy") is True:
        return "matka"
    s.brak("pesel")
    return None


def _wiek_wnioskodawcy(s: _Spr, na_dzien: date) -> int | None:
    du = data(s.pole("data_urodzenia")) if s.pole("data_urodzenia") is not BRAK else None
    if du is None and _pesel_ok(s.pole("pesel")):
        du = _data_z_pesel(s.pole("pesel"))
    if du is None:
        return None
    return na_dzien.year - du.year - ((na_dzien.month, na_dzien.day) < (du.month, du.day))


def _zdarzenie(s: _Spr) -> tuple[dict | None, str | None]:
    """Ustala zdarzenie, od którego liczymy świadczenia rodzicielskie:
      - ciąża (w_ciazy = true) → przewidywany poród (przewidywana_data_porodu); wpisy w „dzieci” bez
        data_urodzenia traktujemy jako oczekiwane dziecko (np. z dziecko.zaswiadczenie_za_zyciem),
      - inaczej: najnowsze dziecko z listy „dzieci” → poród (dziecko.data_urodzenia) albo
        przyjęcie na wychowanie (dziecko.przyjete_na_wychowanie.data_przyjecia; przy przysposobieniu
        prawo powstaje po przyjęciu I wystąpieniu do sądu – ustawa zasiłkowa str. 7, art. 29 ust. 1 pkt 2).
    Zwraca (zdarzenie, None) albo (None, powód wykluczenia) albo (None, None) przy brakach."""
    dzieci = s.pole("dzieci")
    dzieci = dzieci if isinstance(dzieci, list) else []
    w_ciazy = s.pole("w_ciazy")
    if w_ciazy is True:
        pdp = s.wymagaj("przewidywana_data_porodu")
        if pdp is BRAK:
            return None, None
        # Oczekiwane dziecko = wpis w „dzieci” bez data_urodzenia (i bez przyjęcia na wychowanie). Pozwala podać
        # dane znane przed porodem, np. dziecko.zaswiadczenie_za_zyciem przy diagnozie prenatalnej
        # (zaświadczenie dotyczy chorób powstałych w okresie prenatalnym – treść zadania str. 5–6, przypis 2).
        oczekiwane = [c for c in dzieci if not c.get("data_urodzenia") and not c.get("przyjete_na_wychowanie")]
        return {"sciezka": "urodzenie", "data": data(pdp), "urodzone": False,
                "dziecko": oczekiwane[0] if oczekiwane else None,
                "dzieci_zdarzenia": oczekiwane, "przyjecie": None}, None
    if dzieci:
        def klucz(c: dict) -> date:
            p = c.get("przyjete_na_wychowanie") or {}
            return data(p.get("data_przyjecia")) or data(c.get("data_urodzenia")) or date.min
        c = max(dzieci, key=klucz)
        p = c.get("przyjete_na_wychowanie")
        if p:
            dp = data(p.get("data_przyjecia"))
            rodzaj = p.get("rodzaj")
            if not dp:
                s.brak("dziecko.przyjete_na_wychowanie.data_przyjecia")
            if not rodzaj:
                s.brak("dziecko.przyjete_na_wychowanie.rodzaj")
            if not dp or not rodzaj:
                return None, None
            dzien = dp
            if rodzaj == "przysposobienie":
                dws = data(p.get("data_wystapienia_do_sadu"))
                if not dws:
                    s.brak("dziecko.przyjete_na_wychowanie.data_wystapienia_do_sadu")
                    return None, None
                dzien = max(dp, dws)
            razem = [x for x in dzieci if (x.get("przyjete_na_wychowanie") or {}).get("data_przyjecia") == p.get("data_przyjecia")]
            return {"sciezka": "przyjecie", "data": dzien, "urodzone": True, "dziecko": c,
                    "dzieci_zdarzenia": razem, "przyjecie": p}, None
        du = data(c.get("data_urodzenia"))
        if not du:
            s.brak("dziecko.data_urodzenia")
            return None, None
        razem = [x for x in dzieci if not x.get("przyjete_na_wychowanie") and data(x.get("data_urodzenia")) == du]
        return {"sciezka": "urodzenie", "data": du, "urodzone": du <= s.ctx.dzis, "dziecko": c,
                "dzieci_zdarzenia": razem, "przyjecie": None}, None
    if w_ciazy is BRAK:
        s.brak("w_ciazy")
    if s.pole("dzieci") is BRAK:
        s.brak("dzieci")
    if s.braki:
        return None, None
    return None, "nie jesteś w ciąży i nie podano dziecka (urodzonego ani przyjętego na wychowanie)"


def _liczba_dzieci(s: _Spr, ev: dict) -> int | None:
    """Liczba dzieci z jednego porodu (pole liczba_dzieci_przy_porodzie) albo przyjętych jednocześnie.
    Wpływa na wymiar urlopów – Kodeks pracy str. 3 (art. 180 § 1), str. 6 (art. 182¹a), str. 8 (art. 183)."""
    if ev["sciezka"] == "przyjecie":
        return max(1, len(ev["dzieci_zdarzenia"]))
    v = s.pole("liczba_dzieci_przy_porodzie")
    if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
        return v
    if ev["urodzone"] and ev["dzieci_zdarzenia"]:
        s.uwaga(f"Liczbę dzieci z porodu ({len(ev['dzieci_zdarzenia'])}) policzono z listy „dzieci” "
                "(dzieci z tą samą datą urodzenia).")
        return len(ev["dzieci_zdarzenia"])
    s.brak("liczba_dzieci_przy_porodzie")
    return None


def _za_zyciem(s: _Spr, ev: dict, wymagane: bool = False) -> bool | None:
    """Czy dziecko ma zaświadczenie „Za życiem” (pole dziecko.zaswiadczenie_za_zyciem).
    Wydłuża rodzicielski do 65/67 tyg. – Kodeks pracy str. 6, art. 182¹a § 2."""
    dzieci = ev["dzieci_zdarzenia"] or ([ev["dziecko"]] if ev["dziecko"] else [])
    znane = [c.get("zaswiadczenie_za_zyciem") for c in dzieci if c.get("zaswiadczenie_za_zyciem") is not None]
    if any(znane):
        return True
    if znane:
        return False
    if wymagane:
        s.brak("dziecko.zaswiadczenie_za_zyciem")
        return None
    s.uwaga("Przyjęto brak zaświadczenia „Za życiem” (pole dziecko.zaswiadczenie_za_zyciem nie podane).")
    return False


def _dzieci_zyja(ev: dict) -> bool:
    """Czy przy życiu jest choć jedno dziecko ze zdarzenia (dziecko.urodzone_zywe, dziecko.data_zgonu)."""
    d = ev["dzieci_zdarzenia"]
    if not d:
        return True
    return any(c.get("urodzone_zywe", True) is not False and not c.get("data_zgonu") for c in d)


def _ubezpieczenie(s: _Spr) -> str | None:
    """Rodzaj ubezpieczenia chorobowego: 'obowiazkowe' | 'dobrowolne' | 'brak' (None przy brakach).
    - tytuły bez ubezpieczenia chorobowego (dzieło, student, bezrobocie, brak, ulga na start, KRUS)
      → 'brak' – Poradnik str. 35 (PDF 36);
    - umowa o pracę → obowiązkowe; zlecenie / JDG → dobrowolne (trzeba podać pole
      ubezpieczenie_chorobowe) – treść zadania str. 3."""
    tytul = s.wymagaj("tytul_ubezpieczenia")
    if tytul is BRAK:
        return None
    s.fakty["tytul_ubezpieczenia"] = tytul
    if tytul in TYTULY_BEZ_ZASILKU_ZUS:
        return "brak"
    uch = s.pole("ubezpieczenie_chorobowe")
    if uch in ("obowiazkowe", "dobrowolne", "brak"):
        return uch
    if tytul in TYTULY_PRACOWNIK:
        s.zrodlo("ZAD_s3")
        s.uwaga("Umowa o pracę → przyjęto obowiązkowe ubezpieczenie chorobowe (treść zadania str. 3).")
        return "obowiazkowe"
    s.brak("ubezpieczenie_chorobowe")
    return None


def _ubezpieczony_w_dniu(s: _Spr, ev: dict) -> bool | None:
    """Czy wnioskodawca podlega ubezpieczeniu chorobowemu w dniu porodu / przyjęcia.
    Pole ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia jest „wyliczane” – jeśli go nie ma,
    liczymy je z data_ustania_ubezpieczenia (null = ubezpieczenie trwa)."""
    v = s.pole("ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia")
    if isinstance(v, bool):
        return v
    du = s.pole("data_ustania_ubezpieczenia")
    if du is BRAK:
        s.brak("ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia (albo data_ustania_ubezpieczenia)")
        return None
    if du is None:
        if not ev["urodzone"]:
            s.uwaga("Przyjęto, że ubezpieczenie chorobowe będzie trwać do dnia porodu.")
        return True
    return data(du) >= ev["data"]


def _wyjatek_art_30(s: _Spr) -> bool | None:
    """Zasiłek macierzyński mimo braku ubezpieczenia w dniu porodu, jeśli ubezpieczenie ustało
    w ciąży z powodu upadłości, likwidacji lub śmierci pracodawcy albo z naruszeniem przepisów
    stwierdzonym prawomocnym wyrokiem – ustawa zasiłkowa str. 8, art. 30 ust. 1."""
    przyczyna = s.pole("przyczyna_rozwiazania_umowy")
    if przyczyna is BRAK:
        s.brak("przyczyna_rozwiazania_umowy")
        return None
    if przyczyna in ("upadlosc", "likwidacja", "smierc_pracodawcy"):
        return True
    if przyczyna == "naruszenie_przepisow":
        wyrok = s.pole("prawomocny_wyrok_naruszenie_przepisow")
        if wyrok is BRAK:
            s.brak("prawomocny_wyrok_naruszenie_przepisow")
            return None
        return wyrok is True
    return False


def _prawo_do_zasilku_macierzynskiego(s: _Spr, ev: dict) -> bool | None:
    """Warunek wspólny wszystkich urlopów płatnych zasiłkiem macierzyńskim:
    ubezpieczenie chorobowe w dniu porodu / przyjęcia (ustawa zasiłkowa str. 6–7, art. 29 ust. 1;
    Poradnik str. 29 (PDF 30) „Kluczowy warunek”; treść zadania str. 10 – ryzyko H3)
    albo wyjątek z art. 30 (str. 8). Zasiłek macierzyński NIE ma okresu wyczekiwania
    (art. 4 dotyczy tylko zasiłku chorobowego – ustawa zasiłkowa str. 2).
    Przy False ustawia s.powod."""
    s.zrodlo("UZ_29_1_2", "POR_29")
    rodzaj = _ubezpieczenie(s)
    if rodzaj == "brak":
        s.zrodlo("POR_35")
        s.powod = (f"brak ubezpieczenia chorobowego (tytuł: {s.fakty.get('tytul_ubezpieczenia')}) – "
                   "zasiłek macierzyński przysługuje tylko ubezpieczonym")
        return False
    w_dniu = _ubezpieczony_w_dniu(s, ev)      # sprawdzane też przy brakach – żeby zgłosić wszystkie braki naraz
    if rodzaj is None or w_dniu is None:
        return None
    if w_dniu:
        _uwaga_zadluzenie(s)
        return True
    art30 = _wyjatek_art_30(s)
    if art30 is None:
        return None
    if art30:
        s.zrodlo("UZ_30", "UZ_61")
        s.uwaga("Zasiłek po ustaniu ubezpieczenia (ustawa zasiłkowa art. 30) – wypłaca ZUS (art. 61).")
        return True
    s.zrodlo("ZAD_s10")
    s.powod = "nie podlegasz ubezpieczeniu chorobowemu w dniu porodu / przyjęcia dziecka"
    return False


def _uwaga_zadluzenie(s: _Spr) -> None:
    """JDG: zadłużenie > 1% płacy minimalnej wstrzymuje zasiłek do spłaty; prawo przedawnia się,
    jeśli dług nie zostanie spłacony w 6 mies. – ustawa zasiłkowa str. 1, art. 2a; Poradnik str. 24."""
    if s.fakty.get("tytul_ubezpieczenia") not in TYTULY_JDG:
        return
    dl = s.pole("zadluzenie_skladkowe")
    kwota = dl.get("kwota", 0) if isinstance(dl, dict) else 0
    prog = s.ctx.P["placa_minimalna_zl"] * s.ctx.P["zadluzenie_prog_procent_placy_min"] / 100
    if kwota and kwota > prog:
        s.zrodlo("UZ_2a", "POR_24")
        s.uwaga(f"Zadłużenie składkowe {kwota} zł > {prog:.2f} zł – zasiłek wypłacany dopiero po spłacie całości; "
                "brak spłaty w 6 mies. = przedawnienie prawa (ustawa zasiłkowa art. 2a).")


def _podstawa_dostepna(s: _Spr) -> None:
    """Do kwoty potrzebna jest podstawa wymiaru: pracownik / zleceniobiorca – podstawa_wymiaru_12_miesiecy,
    JDG – zadeklarowana_podstawa_jdg (ustawa zasiłkowa str. 9–13, art. 36–52). Pola dodatkowe spoza
    schematu, które też wystarczą: podstawa, podstawa_poprzedniego_zasilku."""
    if s.pole("podstawa") not in (BRAK, None) or s.pole("podstawa_poprzedniego_zasilku") not in (BRAK, None):
        return
    if s.fakty.get("tytul_ubezpieczenia") in TYTULY_JDG:
        s.wymagaj("zadeklarowana_podstawa_jdg")
    else:
        s.wymagaj("podstawa_wymiaru_12_miesiecy")


def _ojcostwo(s: _Spr, ev: dict) -> bool | None:
    """Ojciec biologiczny: przy rodzicach bez ślubu potrzebne uznanie ojcostwa
    (zmienne_uzytkownika.json – opis pól stan_cywilny i uznanie_ojcostwa)."""
    if ev["sciezka"] != "urodzenie":
        return True
    sc = s.pole("stan_cywilny")
    if sc is BRAK:
        s.brak("stan_cywilny")
        return None
    if sc == "zonaty_zamezna":
        return True
    u = s.pole("uznanie_ojcostwa")
    if u is BRAK:
        s.brak("uznanie_ojcostwa")
        return None
    s.zrodlo("JSN_zmienne")
    return u is True


def _warunki_przyjecia(s: _Spr, ev: dict) -> str | None:
    """Warunki przyjęcia dziecka na wychowanie. Zwraca powód wykluczenia albo None.
      - rodzina zastępcza ZAWODOWA – brak prawa: Kodeks pracy str. 8, art. 183 § 1 i § 4;
        ustawa zasiłkowa str. 7, art. 29 ust. 1 pkt 3;
      - wiek dziecka w dniu przyjęcia poniżej limitu (7 / 10 / 14 lat) – granica_wieku_przyjecia()."""
    p = ev["przyjecie"]
    rodzaj = p.get("rodzaj")
    if rodzaj == "rodzina_zastepcza_zawodowa":
        s.zrodlo("KP_183_1", "UZ_29_1_2")
        return "rodzina zastępcza zawodowa nie ma prawa do zasiłku macierzyńskiego"
    du = data(ev["dziecko"].get("data_urodzenia"))
    if not du:
        s.brak("dziecko.data_urodzenia")
        return None
    przyj = data(p.get("data_przyjecia"))
    odroczony = ev["dziecko"].get("odroczony_obowiazek_szkolny")
    if rodzaj != "przysposobienie" and odroczony is None and przyj >= urodziny(du, 7):
        s.brak("dziecko.odroczony_obowiazek_szkolny")      # potrzebne tylko dla dziecka 7–10 lat
        return None
    limit = granica_wieku_przyjecia(rodzaj, bool(odroczony), s.ctx.P)
    s.fakty["granica_wieku_lat"] = limit
    s.fakty["dziecko_konczy_limit"] = urodziny(du, limit)
    if przyj >= urodziny(du, limit):
        s.zrodlo("UZ_29_1_2", "KP_183_1", "KP_183_11")
        return f"dziecko w dniu przyjęcia miało co najmniej {limit} lat"
    return None


def _wariant_81_5(s: _Spr, ev: dict, rola: str | None) -> bool:
    """Jednolity wniosek (81,5% za cały okres): pole jednolity_wniosek_81_5_procent.czy = true
    i data_zlozenia najpóźniej 21 dni po porodzie / przyjęciu – ustawa zasiłkowa str. 8, art. 30a;
    str. 9, art. 31 ust. 3; Poradnik str. 34 (PDF 35). Przy porodzie wniosek składa matka (art. 30a ust. 1),
    przy przyjęciu – każdy ubezpieczony (ust. 2)."""
    w = s.pole("jednolity_wniosek_81_5_procent")
    if not isinstance(w, dict) or not w.get("czy"):
        return False
    if ev["sciezka"] == "urodzenie" and rola == "ojciec":
        return False
    s.zrodlo("UZ_30a", "POR_34")
    dz = data(w.get("data_zlozenia"))
    if dz and (dz - ev["data"]).days > s.ctx.P["termin_wniosku_81_5_dni"]:
        s.uwaga(f"Jednolity wniosek złożony {(dz - ev['data']).days} dni po zdarzeniu (> 21) – przysługuje 100% + 70%.")
        return False
    if not dz:
        s.uwaga("Jednolity wniosek bez daty złożenia – przyjęto, że zostanie złożony w 21 dni.")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# 4. FUNKCJE SPRAWDZAJĄCE – PO JEDNEJ NA ŚWIADCZENIE
# ═══════════════════════════════════════════════════════════════════════════
def _okres_zasilkowy_wykorzystany(s: _Spr, wymagany: bool) -> int | None:
    """Dni zasiłku chorobowego już wykorzystane w ciąży: pole okres_zasilkowy_wykorzystany_dni albo suma
    dni z zaswiadczenia_e_zla z kod_literowy_b = true (ustawa zasiłkowa str. 3, art. 9 ust. 2 – okresy
    sprzed ciąży się nie wliczają). Bez danych: 0 (zasiłek chorobowy) albo brak (świadczenie rehabilitacyjne)."""
    v = s.pole("okres_zasilkowy_wykorzystany_dni")
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    ezla = s.pole("zaswiadczenia_e_zla")
    if isinstance(ezla, list):
        dni = sum((data(z["do"]) - data(z["od"])).days + 1 for z in ezla if z.get("kod_literowy_b"))
        s.uwaga(f"Wykorzystany okres zasiłkowy policzono z e-ZLA z kodem B: {dni} dni.")
        return dni
    if wymagany:
        s.brak("okres_zasilkowy_wykorzystany_dni")
        return None
    s.uwaga("Przyjęto 0 wykorzystanych dni okresu zasiłkowego (brak okres_zasilkowy_wykorzystany_dni i e-ZLA).")
    return 0


def _koniec_wyczekiwania(s: _Spr, rodzaj: str) -> date | None:
    """Pierwszy dzień prawa do zasiłku chorobowego po okresie wyczekiwania:
    30 dni nieprzerwanego ubezpieczenia (obowiązkowe) / 90 dni (dobrowolne) – ustawa zasiłkowa str. 2,
    art. 4 ust. 1; treść zadania str. 3. Poprzednie okresy wlicza się, jeśli przerwa ≤ 30 dni (art. 4 ust. 2).
    Bez okresu wyczekiwania po ≥ 10 latach ubezpieczenia obowiązkowego (art. 4 ust. 3 pkt 3)."""
    P = s.ctx.P
    dni = int(P["okres_wyczekiwania_dni"][rodzaj])
    s.zrodlo("UZ_4", "ZAD_s3")
    okresy = s.pole("okresy_ubezpieczenia")
    if isinstance(okresy, list) and okresy:
        ok = sorted(okresy, key=lambda o: data(o["od"]))
        start = data(ok[-1]["od"])
        for prev in reversed(ok[:-1]):                     # łańcuch z przerwami ≤ 30 dni (art. 4 ust. 2)
            if (start - data(prev["do"])).days - 1 <= P["okres_wyczekiwania_przerwa_max_dni"]:
                start = data(prev["od"])
            else:
                break
        obow = sum(((data(o["do"]) if o.get("do") else s.ctx.dzis) - data(o["od"])).days + 1
                   for o in ok if o.get("tytul") in TYTULY_PRACOWNIK)
        if obow >= P["okres_wyczekiwania_zwolnienie_lat_obowiazkowego"] * 365:
            s.uwaga("≥ 10 lat ubezpieczenia obowiązkowego – bez okresu wyczekiwania (ustawa zasiłkowa art. 4 ust. 3 pkt 3).")
            return date.min
        return start + timedelta(days=dni)
    od = s.wymagaj("data_objecia_ubezpieczeniem_chorobowym")
    if od is BRAK:
        return None
    return data(od) + timedelta(days=dni)


def _porod_minal(s: _Spr) -> str | None:
    """Świadczenia w ciąży przysługują do dnia porodu (treść zadania str. 4). Jeśli przewidywana data porodu
    już minęła, dane są nieaktualne (poród się odbył) – zwracamy powód zamiast liczyć ujemny okres."""
    pdp = s.pole("przewidywana_data_porodu")
    if pdp not in (BRAK, None) and data(pdp) <= s.ctx.dzis:
        return (f"przewidywana data porodu ({data(pdp)}) już minęła – jeśli dziecko się urodziło, ustaw "
                "w_ciazy = false i dodaj dziecko z data_urodzenia")
    return None


def sprawdz_zasilek_chorobowy_ciaza(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek chorobowy w ciąży (100% podstawy, do 270 dni).
    Warunki: ciąża; ubezpieczenie chorobowe (ustawa zasiłkowa str. 2, art. 6 ust. 1); okres wyczekiwania
    (art. 4); niewyczerpany okres zasiłkowy 270 dni (str. 3, art. 8 ust. 1); po ustaniu ubezpieczenia – tylko
    przy niezdolności powstałej do 14 dni od ustania i trwającej ≥ 30 dni (str. 3, art. 7).
    Opis procesu: treść zadania str. 2–4; Załącznik, sekcja „Zasiłek chorobowy w okresie ciąży”; Poradnik str. 23–24."""
    s = _Spr("ZASILEK_CHOROBOWY_CIAZA", ctx)
    s.zrodlo("ZAD_s2_4", "UZ_6_7", "UZ_8_9", "UZ_11", "ZAL_chor", "POR_23", "POR_24")
    w_ciazy = s.wymagaj("w_ciazy")
    if w_ciazy is False:
        return s.nie("świadczenie dotyczy kobiety w ciąży (w_ciazy = false)")
    if _rola(s) == "ojciec":
        return s.nie("świadczenie dotyczy kobiety w ciąży")
    p = _porod_minal(s)
    if p:
        return s.nie(p)
    rodzaj = _ubezpieczenie(s)
    if rodzaj == "brak":
        return s.nie(f"brak ubezpieczenia chorobowego (tytuł: {s.fakty.get('tytul_ubezpieczenia')})", "ZAD_s3", "POR_35")
    du = s.pole("data_ustania_ubezpieczenia")
    if du not in (BRAK, None) and data(du) < ctx.dzis:
        # Po ustaniu tytułu: niezdolność powstała ≤ 14 dni od ustania i trwa ≥ 30 dni (art. 7 pkt 1).
        ezla = s.pole("zaswiadczenia_e_zla")
        ezla = ezla if isinstance(ezla, list) else []
        if not any(data(z["od"]) <= data(du) + timedelta(days=14)
                   and (data(z["do"]) - data(z["od"])).days + 1 >= 30 for z in ezla):
            return s.nie("ubezpieczenie ustało, a zasiłek po ustaniu przysługuje tylko przy niezdolności powstałej "
                         "do 14 dni od ustania i trwającej co najmniej 30 dni", "UZ_6_7")
        s.fakty["po_ustaniu"] = True
        s.zrodlo("UZ_61")
        s.uwaga("Zasiłek po ustaniu ubezpieczenia – wypłaca ZUS (ustawa zasiłkowa art. 61); oświadczenie Z-10.")
    od_prawa = _koniec_wyczekiwania(s, rodzaj) if rodzaj else None
    pdp = s.wymagaj("przewidywana_data_porodu")
    wyk = _okres_zasilkowy_wykorzystany(s, wymagany=False)
    if wyk is not None and wyk >= ctx.P["okres_zasilkowy_dni"]:
        return s.nie("wyczerpany 270-dniowy okres zasiłkowy – sprawdź świadczenie rehabilitacyjne", "UZ_8_9")
    _podstawa_dostepna(s)
    if s.braki:
        return s.koniec()
    od = max(ctx.dzis, od_prawa)
    do = min(data(pdp) - timedelta(days=1), od + timedelta(days=ctx.P["okres_zasilkowy_dni"] - wyk - 1))
    if od > do:
        return s.nie(f"prawo do zasiłku powstanie dopiero {od_prawa} (po okresie wyczekiwania), czyli po porodzie", "UZ_4")
    s.fakty.update(od=od, do=do, wykorzystane_dni=wyk, ubezpieczenie=rodzaj,
                   wiek=_wiek_wnioskodawcy(s, ctx.dzis))
    if od_prawa > ctx.dzis:
        s.uwaga(f"Okres wyczekiwania kończy się {od_prawa - timedelta(days=1)} – prawo od {od_prawa}.")
    return s.koniec()


def sprawdz_swiadczenie_rehabilitacyjne(ctx: Kontekst) -> WynikSprawdzenia:
    """Świadczenie rehabilitacyjne w ciąży (100% podstawy, max 12 mies.).
    Warunki: wyczerpany zasiłek chorobowy (270 dni w ciąży) i dalsza niezdolność z rokowaniem –
    ustawa zasiłkowa str. 5, art. 18 ust. 1–3 (orzeka lekarz orzecznik ZUS); wysokość str. 6, art. 19 ust. 1;
    wniosek ZNp-7 (katalog_wnioskow_pdf.json)."""
    s = _Spr("SWIADCZENIE_REHABILITACYJNE", ctx)
    s.zrodlo("UZ_18_19", "UZ_8_9", "KAT_ZNP7", "POR_24")
    w_ciazy = s.wymagaj("w_ciazy")
    if w_ciazy is False:
        return s.nie("w kalkulatorze liczone dla ciąży (100% podstawy); poza ciążą 90%/75% – ustawa zasiłkowa art. 19")
    if _rola(s) == "ojciec":
        return s.nie("świadczenie liczone dla kobiety w ciąży")
    p = _porod_minal(s)
    if p:
        return s.nie(p)
    wyk = _okres_zasilkowy_wykorzystany(s, wymagany=True)
    if wyk is not None and wyk < ctx.P["okres_zasilkowy_dni"]:
        return s.nie(f"przysługuje dopiero po wyczerpaniu 270 dni zasiłku chorobowego (wykorzystano {wyk} dni)")
    _ubezpieczenie(s)
    pdp = s.wymagaj("przewidywana_data_porodu")
    _podstawa_dostepna(s)
    if s.braki:
        return s.koniec()
    s.fakty.update(od=ctx.dzis, do=min(data(pdp) - timedelta(days=1),
                                       dodaj_miesiace(ctx.dzis, ctx.P["swiadczenie_rehabilitacyjne_max_miesiecy"]) - timedelta(days=1)))
    s.uwaga("Prawo ustala ZUS na podstawie orzeczenia lekarza orzecznika (ustawa zasiłkowa art. 18 ust. 3).")
    return s.koniec()


def sprawdz_zasilek_w_wysokosci_macierzynskiego(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek w wysokości zasiłku macierzyńskiego – do dnia porodu, 100% podstawy.
    Warunki: pracownica w ciąży, umowa rozwiązana w ciąży z powodu upadłości, likwidacji lub śmierci
    pracodawcy (ustawa zasiłkowa str. 8, art. 30 ust. 3); treść zadania str. 4 dodaje naruszenie przepisów
    potwierdzone prawomocnym wyrokiem. Wniosek ZAS-55 (katalog_wnioskow_pdf.json)."""
    s = _Spr("ZASILEK_W_WYSOKOSCI_MACIERZYNSKIEGO", ctx)
    s.zrodlo("ZAD_s4", "UZ_30", "KAT_ZAS55")
    w_ciazy = s.wymagaj("w_ciazy")
    if w_ciazy is False:
        return s.nie("świadczenie dotyczy kobiety w ciąży")
    if _rola(s) == "ojciec":
        return s.nie("świadczenie dotyczy kobiety w ciąży")
    p = _porod_minal(s)
    if p:
        return s.nie(p)
    tytul = s.pole("tytul_ubezpieczenia")
    if tytul not in (BRAK, None) and tytul not in TYTULY_PRACOWNIK | {"brak", "bezrobocie_z_zasilkiem", "bezrobocie_bez_zasilku"}:
        return s.nie("świadczenie dotyczy pracownicy, której rozwiązano umowę o pracę")
    du = s.pole("data_ustania_ubezpieczenia")
    if du is None:
        return s.nie("umowa o pracę trwa – świadczenie dotyczy utraty pracy w ciąży")
    if du is BRAK:
        s.brak("data_ustania_ubezpieczenia")
    przyczyna = s.pole("przyczyna_rozwiazania_umowy")
    if przyczyna is BRAK:
        s.brak("przyczyna_rozwiazania_umowy")
    elif przyczyna in (None, "inna"):
        return s.nie("przysługuje tylko przy upadłości, likwidacji lub śmierci pracodawcy albo naruszeniu przepisów stwierdzonym wyrokiem")
    elif przyczyna == "naruszenie_przepisow":
        wyrok = s.pole("prawomocny_wyrok_naruszenie_przepisow")
        if wyrok is BRAK:
            s.brak("prawomocny_wyrok_naruszenie_przepisow")
        elif wyrok is not True:
            return s.nie("przy naruszeniu przepisów potrzebny jest prawomocny wyrok sądu", "ZAD_s4")
        else:
            s.uwaga("Ustawa (art. 30 ust. 3) wymienia tylko upadłość, likwidację i śmierć pracodawcy; naruszenie "
                    "przepisów z wyrokiem – wg treści zadania str. 4. Do potwierdzenia z ZUS.")
    pdp = s.wymagaj("przewidywana_data_porodu")
    if du not in (BRAK, None) and pdp is not BRAK and data(du) >= data(pdp):
        return s.nie("zatrudnienie trwało do porodu – przysługuje zasiłek macierzyński")
    _podstawa_dostepna(s)
    if s.braki:
        return s.koniec()
    s.zrodlo("UZ_47", "UZ_61")
    s.fakty.update(od=data(du) + timedelta(days=1), do=data(pdp) - timedelta(days=1))
    s.uwaga("Warunek: nie zapewniono innego zatrudnienia (ustawa zasiłkowa art. 30 ust. 3). Wypłaca ZUS (art. 61).")
    return s.koniec()


def sprawdz_urlop_macierzynski(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek macierzyński za urlop macierzyński (matka, poród).
    Warunki: poród; ubezpieczenie chorobowe w dniu porodu (ustawa zasiłkowa str. 6, art. 29 ust. 1 pkt 1)
    albo wyjątek z art. 30; zasiłek przysługuje za okres urlopu z Kodeksu pracy (str. 8, art. 29a ust. 1;
    Kodeks pracy str. 10, art. 184). Wymiar: Kodeks pracy str. 3, art. 180 § 1."""
    s = _Spr("URLOP_MACIERZYNSKI", ctx)
    s.zrodlo("KP_180_1", "ZAL_mac", "POR_30", "UZ_29a", "KP_184", "ZAD_s4_5")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    rola = _rola(s)
    if rola == "ojciec":
        return s.nie("urlop macierzyński wykorzystuje matka; ojciec – zob. przejęcie części urlopu macierzyńskiego", "KP_180_4_5")
    if ev and ev["sciezka"] == "przyjecie":
        return s.nie("przy przyjęciu dziecka przysługuje urlop na warunkach urlopu macierzyńskiego", "KP_183_1")
    if ev:
        prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
        if prawo is False:
            return s.nie(s.powod)
        n = _liczba_dzieci(s, ev)
        if n:
            przed = int(s.pole("urlop_macierzynski.tygodnie_przed_porodem") or 0) if s.pole("urlop_macierzynski.tygodnie_przed_porodem") is not BRAK else 0
            koniec_urlopu = ev["data"] + timedelta(days=wymiar_macierzynskiego_tyg(n, ctx.P) * 7 - przed * 7 - 1)
            if koniec_urlopu < ctx.dzis:
                return s.nie(f"okres urlopu macierzyńskiego już minął ({koniec_urlopu})")
            s.fakty.update(liczba_dzieci=n)
        s.fakty.update(zdarzenie=ev, rola="matka", wariant_81_5=_wariant_81_5(s, ev, "matka"))
    _podstawa_dostepna(s)
    return s.koniec()


PRZEJECIE_ZRODLA = {"rezygnacja": ("KP_180_4_5", "UZ_29_3_10"),
                    "orzeczenie_niezdolnosci": ("KP_180_6_7", "UZ_29_3_10"),
                    "szpital_matki": ("KP_180_10_11", "UZ_29_3_10"),
                    "porzucenie_dziecka": ("KP_180_12_13", "UZ_29_3_10"),
                    "zgon_matki": ("KP_180_12_13", "UZ_29_3_10")}


def sprawdz_przejecie_macierzynskiego(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek macierzyński za przejętą część urlopu macierzyńskiego (ojciec).
    Sytuacje: rezygnacja matki po min. 14 tyg. (Kodeks pracy str. 3, art. 180 § 4–5; ustawa zasiłkowa str. 7,
    art. 29 ust. 3); po 8 tyg. przy orzeczeniu o niezdolności do samodzielnej egzystencji (§ 6–7) i pobycie
    matki w szpitalu (§ 10–11, str. 4); zgon matki / porzucenie dziecka (§ 12–13, str. 4). Treść zadania str. 7."""
    s = _Spr("URLOP_MACIERZYNSKI_PRZEJECIE", ctx)
    s.zrodlo("ZAD_s7", "UZ_29_3_10", "KP_180_14")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    rola = _rola(s)
    if rola == "matka":
        return s.nie("dotyczy ojca przejmującego część urlopu macierzyńskiego od matki")
    if ev and ev["sciezka"] == "przyjecie":
        return s.nie("przy przyjęciu dziecka – zob. urlop na warunkach urlopu macierzyńskiego")
    powody_ok = []
    zg = s.pole("zgon_matki_lub_porzucenie_dziecka")
    if zg in ("zgon_matki", "porzucenie_dziecka"):
        powody_ok.append(zg)
    if s.pole("orzeczenie_niezdolnosci_samodzielnej_egzystencji_matki") is True:
        powody_ok.append("orzeczenie_niezdolnosci")
    hosp = s.pole("hospitalizacja_matki")
    if isinstance(hosp, list) and hosp:
        powody_ok.append("szpital_matki")
    rez = s.pole("rezygnacja_z_macierzynskiego_po_14_tyg")
    if isinstance(rez, dict) and rez.get("czy"):
        powody_ok.append("rezygnacja")
    if not powody_ok:
        if zg is BRAK:
            s.brak("zgon_matki_lub_porzucenie_dziecka")
        if rez is BRAK:
            s.brak("rezygnacja_z_macierzynskiego_po_14_tyg")
        if not s.braki:
            return s.nie("przejęcie możliwe tylko przy rezygnacji matki po 14 tyg., zgonie matki, porzuceniu "
                         "dziecka, pobycie matki w szpitalu lub jej niezdolności do samodzielnej egzystencji",
                         "KP_180_4_5", "KP_180_6_7", "KP_180_10_11", "KP_180_12_13")
    else:
        s.fakty["powod_przejecia"] = powody_ok[0]
        s.zrodlo(*PRZEJECIE_ZRODLA[powody_ok[0]])
    if ev:
        if _ojcostwo(s, ev) is False:
            return s.nie("brak uznania ojcostwa (rodzice bez ślubu)", "JSN_zmienne")
        prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
        if prawo is False:
            return s.nie(s.powod)
        n = _liczba_dzieci(s, ev)
        if n:
            s.fakty["liczba_dzieci"] = n
        s.fakty.update(zdarzenie=ev, rola="ojciec")
    _podstawa_dostepna(s)
    return s.koniec()


def sprawdz_urlop_uzupelniajacy(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek macierzyński za uzupełniający urlop macierzyński (100%, 8 lub 15 tyg.).
    Warunki: wcześniactwo / niska masa / hospitalizacja dziecka – Kodeks pracy str. 5, art. 180²;
    tylko jedno z rodziców, jednorazowo, bezpośrednio po macierzyńskim (treść zadania str. 8);
    przy przyjęciu – pobyt w szpitalu po przyjęciu (Kodeks pracy str. 8, art. 183 § 3¹)."""
    s = _Spr("URLOP_UZUPELNIAJACY", ctx)
    s.zrodlo("KP_1802", "ZAL_uzup", "POR_31", "ZAD_s8")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    rola = _rola(s)
    plan_rodzic = s.pole("urlop_uzupelniajacy.rodzic")
    if rola and plan_rodzic not in (BRAK, None) and plan_rodzic != rola:
        return s.nie("w planie uzupełniający urlop wykorzystuje drugi rodzic – przysługuje tylko jednemu z rodziców")
    if not ev:
        return s.koniec()
    if not _dzieci_zyja(ev):
        return s.nie("urlop służy opiece nad dzieckiem – brak dziecka przy życiu", "KP_1801")
    prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
    if prawo is False:
        return s.nie(s.powod)
    if ev["sciezka"] == "urodzenie" and not ev["urodzone"]:
        for k in ("dziecko.tydzien_ciazy_przy_urodzeniu", "dziecko.masa_urodzeniowa_g", "dziecko.hospitalizacja"):
            s.brak(k)
        s.uwaga("Dane o wcześniactwie i hospitalizacji dziecka będą znane po porodzie.")
        return s.koniec()
    dzieci = ev["dzieci_zdarzenia"] or [ev["dziecko"]]
    # Zasada kolejności: jeśli wiemy już, że żadne dziecko nie było w szpitalu, to NIE – bez pytania o tydzień i masę.
    if all(c.get("hospitalizacja") is not None for c in dzieci) and not any(c.get("hospitalizacja") for c in dzieci):
        return s.nie("dziecko nie przebywało w szpitalu po porodzie")
    for k in ("tydzien_ciazy_przy_urodzeniu", "masa_urodzeniowa_g", "hospitalizacja"):
        if any(c.get(k) is None for c in dzieci):
            s.brak(f"dziecko.{k}")
    if s.braki:
        return s.koniec()
    if not any(c.get("hospitalizacja") for c in dzieci):
        return s.nie("dziecko nie przebywało w szpitalu po porodzie")
    dp = data(ev["dziecko"]["data_urodzenia"]) if ev["sciezka"] == "przyjecie" else ev["data"]
    od_daty = data(ev["przyjecie"]["data_przyjecia"]) if ev["sciezka"] == "przyjecie" else None
    if od_daty:
        s.zrodlo("KP_183_31")
    U, opis = oblicz_uzupelniajacy(dzieci, dp, ctx.P, od_daty)
    if U == 0:
        return s.nie(f"warunki z Kodeksu pracy art. 180² nie są spełnione ({opis})")
    s.fakty.update(tygodnie=U, opis=opis, zdarzenie=ev, rola=rola)
    n = _liczba_dzieci(s, ev)
    if n:
        s.fakty["liczba_dzieci"] = n
    _podstawa_dostepna(s)
    return s.koniec()


def _sprawdz_rodzicielski(ctx: Kontekst, kod: str, z_praca: bool) -> WynikSprawdzenia:
    """Wspólne warunki urlopu rodzicielskiego (z pracą i bez):
    poród lub przyjęcie; ubezpieczenie (ustawa zasiłkowa art. 29); dziecko przy życiu; termin –
    do końca roku, w którym dziecko kończy 6 lat (Kodeks pracy str. 6, art. 182¹c), przy przysposobieniu
    do 14 r.ż. (str. 9, art. 183 § 4¹). Łączenie z pracą: tylko pracownik, max 1/2 etatu (str. 7, art. 182¹e)."""
    s = _Spr(kod, ctx)
    s.zrodlo("KP_1821a", "ZAL_rodz", "POR_31", "POR_32", "UZ_31_1_3", "KP_1821c")
    if z_praca:
        s.zrodlo("KP_1821e", "KP_1821f", "UZ_31_4a", "ZAD_s9")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    rola = _rola(s)
    if z_praca:
        tytul = s.pole("tytul_ubezpieczenia")
        if tytul not in (BRAK, None) and tytul not in TYTULY_PRACOWNIK:
            return s.nie("łączenie urlopu z pracą (z wydłużeniem urlopu) dotyczy pracownika na umowie o pracę")
        czesci = s.pole("czesci_urlopu_rodzicielskiego")
        wp = [float(c.get("wymiar_pracy_w_trakcie") or 0) for c in (czesci if isinstance(czesci, list) else [])
              if c.get("rodzic") == rola]
        maxw = float(ctx.P["urlop_rodzicielski_praca_max_wymiar"])
        if wp and max(wp) > maxw:
            return s.nie(f"praca w trakcie urlopu najwyżej {maxw:g} etatu (w planie: {max(wp):g})")
        s.fakty["wymiar_pracy"] = max(wp) if wp and max(wp) > 0 else None
    if not ev:
        return s.koniec()
    if not _dzieci_zyja(ev):
        return s.nie("urlop służy opiece nad dzieckiem – brak dziecka przy życiu", "KP_1801")
    if ev["sciezka"] == "przyjecie":
        p = _warunki_przyjecia(s, ev)
        if p:
            return s.nie(p)
        if ev["przyjecie"].get("rodzaj") == "przysposobienie" and s.fakty.get("dziecko_konczy_limit") and \
                s.fakty["dziecko_konczy_limit"] <= ctx.dzis:
            return s.nie("dziecko ukończyło 14 lat", "KP_183_4")
    elif ev["urodzone"]:
        koniec_roku = date(data(ev["dziecko"]["data_urodzenia"]).year + ctx.P["urlop_rodzicielski_do_konca_roku_wieku_lat"], 12, 31)
        if koniec_roku < ctx.dzis:
            return s.nie("minął termin: rodzicielski do końca roku, w którym dziecko kończy 6 lat")
    if rola == "ojciec" and _ojcostwo(s, ev) is False:
        return s.nie("brak uznania ojcostwa (rodzice bez ślubu)", "JSN_zmienne")
    prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
    if prawo is False:
        return s.nie(s.powod)
    n = _liczba_dzieci(s, ev)
    za = _za_zyciem(s, ev)
    if n:
        s.fakty["liczba_dzieci"] = n
    s.fakty.update(zdarzenie=ev, rola=rola, za_zyciem=za, wariant_81_5=_wariant_81_5(s, ev, rola))
    _podstawa_dostepna(s)
    return s.koniec()


def sprawdz_urlop_rodzicielski(ctx: Kontekst) -> WynikSprawdzenia:
    return _sprawdz_rodzicielski(ctx, "URLOP_RODZICIELSKI", z_praca=False)


def sprawdz_urlop_rodzicielski_z_praca(ctx: Kontekst) -> WynikSprawdzenia:
    return _sprawdz_rodzicielski(ctx, "URLOP_RODZICIELSKI_Z_PRACA", z_praca=True)


def sprawdz_urlop_ojcowski(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek macierzyński za urlop ojcowski (100%, 14 dni).
    Warunki: ojciec; do 12. miesiąca życia dziecka albo 12 mies. od uprawomocnienia przysposobienia
    (nie dłużej niż do 14 r.ż.) – Kodeks pracy str. 7–8, art. 182³; przysługuje też ojcu, który zaczął pracę
    po narodzinach dziecka – treść zadania str. 8 (liczy się bieżące ubezpieczenie, nie z dnia porodu)."""
    s = _Spr("URLOP_OJCOWSKI", ctx)
    s.zrodlo("KP_1823", "ZAL_ojc", "POR_32", "POR_33", "ZAD_s8")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    rola = _rola(s)
    if rola == "matka":
        return s.nie("urlop ojcowski to wyłączne prawo ojca")
    if ev:
        if not _dzieci_zyja(ev):
            return s.nie("urlop służy opiece nad dzieckiem – brak dziecka przy życiu")
        if ev["sciezka"] == "przyjecie":
            if ev["przyjecie"].get("rodzaj") != "przysposobienie":
                return s.nie("przy przyjęciu dziecka urlop ojcowski przysługuje tylko przy przysposobieniu (adopcji)")
            upr = data(ev["przyjecie"].get("data_uprawomocnienia"))
            if not upr:
                s.brak("dziecko.przyjete_na_wychowanie.data_uprawomocnienia")
            else:
                du = data(ev["dziecko"].get("data_urodzenia"))
                granica = dodaj_miesiace(upr, 12)
                if du:
                    granica = min(granica, urodziny(du, 14))
                if granica <= ctx.dzis:
                    return s.nie("minął termin: 12 mies. od uprawomocnienia przysposobienia (najpóźniej do 14 r.ż.)")
                s.fakty.update(od_najwczesniej=upr, termin=granica - timedelta(days=1))
        else:
            granica = dodaj_miesiace(ev["data"], ctx.P["urlop_ojcowski_do_miesiaca_zycia"])
            if granica <= ctx.dzis:
                return s.nie("dziecko ukończyło 12 miesięcy – prawo do urlopu ojcowskiego wygasło")
            s.fakty.update(od_najwczesniej=ev["data"], termin=granica - timedelta(days=1))
            if _ojcostwo(s, ev) is False:
                return s.nie("brak uznania ojcostwa (rodzice bez ślubu)", "JSN_zmienne")
        s.fakty["zdarzenie"] = ev
    rodzaj = _ubezpieczenie(s)
    if rodzaj == "brak":
        return s.nie(f"brak ubezpieczenia chorobowego (tytuł: {s.fakty.get('tytul_ubezpieczenia')})", "POR_35")
    du = s.pole("data_ustania_ubezpieczenia")
    if du not in (BRAK, None) and data(du) < ctx.dzis:
        return s.nie("ubezpieczenie chorobowe ustało")
    _uwaga_zadluzenie(s)
    _podstawa_dostepna(s)
    return s.koniec()


def sprawdz_urlop_na_warunkach_macierzynskiego(ctx: Kontekst) -> WynikSprawdzenia:
    """Zasiłek macierzyński za urlop na warunkach urlopu macierzyńskiego (przyjęcie dziecka).
    Warunki: przysposobienie (przyjęcie + wniosek do sądu, dziecko < 14 lat) albo rodzina zastępcza
    niezawodowa (dziecko < 7 lat, < 10 przy odroczeniu obowiązku szkolnego) – Kodeks pracy str. 8,
    art. 183 § 1 i § 1¹; ustawa zasiłkowa str. 7, art. 29 ust. 1 pkt 2–3; ubezpieczenie w dniu przyjęcia."""
    s = _Spr("URLOP_NA_WARUNKACH_MACIERZYNSKIEGO", ctx)
    s.zrodlo("KP_183_1", "KP_183_11", "ZAL_przyj", "UZ_29_1_2", "POR_30", "ZAD_s8", "ZAD_s9", "ROZ_15_16")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie("dotyczy przyjęcia dziecka na wychowanie (" + powod + ")")
    if ev and ev["sciezka"] == "urodzenie":
        return s.nie("dotyczy przyjęcia dziecka na wychowanie (przysposobienie, rodzina zastępcza niezawodowa)")
    if not ev:
        return s.koniec()
    p = _warunki_przyjecia(s, ev)
    if p:
        return s.nie(p)
    prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
    if prawo is False:
        return s.nie(s.powod)
    if s.fakty.get("dziecko_konczy_limit") and s.fakty["dziecko_konczy_limit"] <= ctx.dzis:
        return s.nie("dziecko przekroczyło limit wieku – okres urlopu minął")
    za = _za_zyciem(s, ev)
    s.fakty.update(zdarzenie=ev, rola=_rola(s) if _pesel_ok(s.pole("pesel")) else None,
                   liczba_dzieci=_liczba_dzieci(s, ev), za_zyciem=za, wariant_81_5=_wariant_81_5(s, ev, None))
    _podstawa_dostepna(s)
    return s.koniec()


def sprawdz_swiadczenie_rodzicielskie(ctx: Kontekst) -> WynikSprawdzenia:
    """Świadczenie rodzicielskie z gminy (1000 zł/mies.) – dla osób BEZ prawa do zasiłku macierzyńskiego
    (bezrobotni, studenci, umowa o dzieło itd.) – Poradnik str. 35 (PDF 36); katalog_wnioskow_pdf.json, SR-7.
    Kwota: zmienne_uzytkownika.json, parametry_admin (w plikach ZUS kwoty nie ma; ustawa zasiłkowa str. 9,
    art. 31 ust. 3a tylko się do niej odwołuje)."""
    s = _Spr("SWIADCZENIE_RODZICIELSKIE", ctx)
    s.zrodlo("POR_35", "KAT_SR7", "JSN_param")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    if not ev:
        _ubezpieczenie(s)
        return s.koniec()
    if not _dzieci_zyja(ev):
        return s.nie("brak dziecka przy życiu (interpretacja – reguł dla tej sytuacji nie ma w plikach)")
    inne = s.pole("inne_pobierane_swiadczenia")
    if isinstance(inne, list) and any("macierzy" in str(x.get("rodzaj", "")) for x in inne):
        return s.nie("pobierasz już zasiłek macierzyński")
    prawo = _prawo_do_zasilku_macierzynskiego(s, ev)
    if prawo is True:
        return s.nie("masz prawo do zasiłku macierzyńskiego z ZUS – świadczenie rodzicielskie jest dla osób bez tego prawa")
    if prawo is None:
        return s.koniec()
    n = _liczba_dzieci(s, ev)
    s.fakty.update(zdarzenie=ev, liczba_dzieci=n, za_zyciem=_za_zyciem(s, ev))
    s.uwaga("Wniosek do gminy do 3 mies. od urodzenia = świadczenie za cały okres (katalog_wnioskow_pdf.json, SR-7).")
    return s.koniec()


def _dochod_na_osobe(s: _Spr) -> float | None:
    """Dochód na osobę (pole dochod_na_osobe, „wyliczane”). Jeśli go nie ma – uproszczone wyliczenie
    z dochod_rodziny_rok_bazowy i sklad_rodziny: (opodatkowane + nieopodatkowane − utracone + uzyskane)
    / 12 / liczba osób (uproszczenie – pełnych zasad ustalania dochodu nie ma w plikach)."""
    v = s.pole("dochod_na_osobe")
    if isinstance(v, (int, float)):
        return float(v)
    dr, sk = s.pole("dochod_rodziny_rok_bazowy"), s.pole("sklad_rodziny")
    if isinstance(dr, dict) and isinstance(sk, list) and sk:
        suma = (dr.get("dochody_opodatkowane", 0) + dr.get("dochody_nieopodatkowane", 0)
                - dr.get("dochody_utracone", 0) + dr.get("dochody_uzyskane", 0))
        s.uwaga("Dochód na osobę policzono w uproszczeniu z dochod_rodziny_rok_bazowy i sklad_rodziny.")
        return suma / 12 / len(sk)
    s.brak("dochod_na_osobe (albo dochod_rodziny_rok_bazowy + sklad_rodziny)")
    return None


def _termin_jednorazowego(s: _Spr, ev: dict) -> str | None:
    """Wniosek o świadczenie jednorazowe – do 12 mies. od urodzenia (katalog_wnioskow_pdf.json:
    BECIKOWE, ZA-ZYCIEM „12 miesięcy od urodzenia”)."""
    do = dodaj_miesiace(ev["data"], s.ctx.P["termin_wniosku_jednorazowego_miesiecy"]) - timedelta(days=1)
    if do < s.ctx.dzis:
        return f"minął termin na wniosek ({do})"
    s.fakty.update(od=ev["data"], do=do, zdarzenie=ev)
    return None


def sprawdz_becikowe(ctx: Kontekst) -> WynikSprawdzenia:
    """Becikowe – jednorazowa zapomoga 1000 zł z gminy.
    Warunki: dochód ≤ 1922 zł/os.; opieka medyczna od 10. tyg. ciąży; wniosek do 12 mies. od urodzenia –
    katalog_wnioskow_pdf.json (BECIKOWE); kwota i kryterium – zmienne_uzytkownika.json (parametry_admin);
    opis pola opieka_medyczna_od_10_tyg – zmienne_uzytkownika.json. Brak tych reguł w plikach ZUS."""
    s = _Spr("BECIKOWE", ctx)
    s.zrodlo("KAT_BECIKOWE", "JSN_param", "JSN_zmienne")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    doch = _dochod_na_osobe(s)
    if doch is not None and doch > ctx.P["becikowe_kryterium_zl"]:
        return s.nie(f"dochód {doch:.2f} zł/os. przekracza kryterium {ctx.P['becikowe_kryterium_zl']} zł")
    if ev and ev["sciezka"] == "urodzenie":
        opieka = s.wymagaj("opieka_medyczna_od_10_tyg")
        if opieka is False:
            return s.nie("warunkiem jest opieka medyczna od 10. tygodnia ciąży")
    if ev:
        t = _termin_jednorazowego(s, ev)
        if t:
            return s.nie(t)
    return s.koniec()


def sprawdz_jednorazowe_za_zyciem(ctx: Kontekst) -> WynikSprawdzenia:
    """Jednorazowe świadczenie „Za życiem” 4000 zł z gminy.
    Warunki: dziecko z zaświadczeniem „Za życiem” (definicja – treść zadania str. 5, przypis 2);
    opieka medyczna od 10. tyg. ciąży; wniosek do 12 mies. – katalog_wnioskow_pdf.json (ZA-ZYCIEM),
    zmienne_uzytkownika.json (parametry_admin: za_zyciem_zl; opis pola opieka_medyczna_od_10_tyg)."""
    s = _Spr("JEDNORAZOWE_ZA_ZYCIEM", ctx)
    s.zrodlo("KAT_ZAZYCIEM", "JSN_param", "JSN_zmienne", "ZAD_s5")
    ev, powod = _zdarzenie(s)
    if powod:
        return s.nie(powod)
    if not ev:
        return s.koniec()
    za = _za_zyciem(s, ev, wymagane=True)
    if za is False:
        return s.nie("dziecko nie ma zaświadczenia „Za życiem”")
    if ev["sciezka"] == "urodzenie":
        opieka = s.wymagaj("opieka_medyczna_od_10_tyg")
        if opieka is False:
            return s.nie("warunkiem jest opieka medyczna od 10. tygodnia ciąży")
    t = _termin_jednorazowego(s, ev)
    if t:
        return s.nie(t)
    return s.koniec()


# ═══════════════════════════════════════════════════════════════════════════
# 5. KATALOG ŚWIADCZEŃ I PUNKTY WEJŚCIA
# ═══════════════════════════════════════════════════════════════════════════
KATALOG_SWIADCZEN: dict[str, dict[str, Any]] = {
    "ZASILEK_CHOROBOWY_CIAZA": {"nazwa": "Zasiłek chorobowy w ciąży (100%)", "tryb_wyplaty": "miesiecznie",
                                "funkcja": sprawdz_zasilek_chorobowy_ciaza},
    "SWIADCZENIE_REHABILITACYJNE": {"nazwa": "Świadczenie rehabilitacyjne w ciąży (100%)", "tryb_wyplaty": "miesiecznie",
                                    "funkcja": sprawdz_swiadczenie_rehabilitacyjne},
    "ZASILEK_W_WYSOKOSCI_MACIERZYNSKIEGO": {"nazwa": "Zasiłek w wysokości zasiłku macierzyńskiego (po utracie pracy w ciąży)",
                                            "tryb_wyplaty": "miesiecznie",
                                            "funkcja": sprawdz_zasilek_w_wysokosci_macierzynskiego},
    "URLOP_MACIERZYNSKI": {"nazwa": "Zasiłek macierzyński za urlop macierzyński", "tryb_wyplaty": "urlop",
                           "funkcja": sprawdz_urlop_macierzynski},
    "URLOP_MACIERZYNSKI_PRZEJECIE": {"nazwa": "Zasiłek macierzyński za przejętą część urlopu macierzyńskiego (ojciec)",
                                     "tryb_wyplaty": "urlop", "funkcja": sprawdz_przejecie_macierzynskiego},
    "URLOP_NA_WARUNKACH_MACIERZYNSKIEGO": {"nazwa": "Zasiłek macierzyński za urlop na warunkach urlopu macierzyńskiego (przyjęcie dziecka)",
                                           "tryb_wyplaty": "urlop", "funkcja": sprawdz_urlop_na_warunkach_macierzynskiego},
    "URLOP_UZUPELNIAJACY": {"nazwa": "Zasiłek macierzyński za uzupełniający urlop macierzyński", "tryb_wyplaty": "urlop",
                            "funkcja": sprawdz_urlop_uzupelniajacy},
    "URLOP_RODZICIELSKI": {"nazwa": "Zasiłek macierzyński za urlop rodzicielski", "tryb_wyplaty": "urlop",
                           "funkcja": sprawdz_urlop_rodzicielski},
    "URLOP_RODZICIELSKI_Z_PRACA": {"nazwa": "Zasiłek macierzyński za urlop rodzicielski łączony z pracą (do 1/2 etatu)",
                                   "tryb_wyplaty": "urlop", "funkcja": sprawdz_urlop_rodzicielski_z_praca},
    "URLOP_OJCOWSKI": {"nazwa": "Zasiłek macierzyński za urlop ojcowski", "tryb_wyplaty": "urlop",
                       "funkcja": sprawdz_urlop_ojcowski},
    "SWIADCZENIE_RODZICIELSKIE": {"nazwa": "Świadczenie rodzicielskie (gmina)", "tryb_wyplaty": "miesiecznie",
                                  "funkcja": sprawdz_swiadczenie_rodzicielskie},
    "BECIKOWE": {"nazwa": "Becikowe – jednorazowa zapomoga z tytułu urodzenia dziecka (gmina)", "tryb_wyplaty": "jednorazowo",
                 "funkcja": sprawdz_becikowe},
    "JEDNORAZOWE_ZA_ZYCIEM": {"nazwa": "Jednorazowe świadczenie „Za życiem” (gmina)", "tryb_wyplaty": "jednorazowo",
                              "funkcja": sprawdz_jednorazowe_za_zyciem},
}


def rola_wnioskodawcy(dane: dict) -> str | None:
    """Publiczna wersja _rola(): 'matka' / 'ojciec' / None."""
    return _rola(_Spr("URLOP_MACIERZYNSKI", Kontekst(dane)))


def sprawdz_swiadczenie(kod: str, dane: dict, P: dict | None = None,
                        data_ref: date | None = None) -> WynikSprawdzenia:
    """Sprawdza jedno świadczenie z KATALOG_SWIADCZEN.
    Dane są najpierw ujednolicane (normalizuj_dane: "true" → True, "2" → 2, "" → None).
    Błąd formatu w danych (np. data „10.02.2027” zamiast „2027-02-10”) NIE przerywa działania –
    to świadczenie dostaje stan BRAK_DANYCH z opisem błędu, pozostałe liczą się normalnie."""
    ctx = Kontekst(normalizuj_dane(dane), P or PARAMETRY_DOMYSLNE, data_ref or date.today())
    try:
        return KATALOG_SWIADCZEN[kod]["funkcja"](ctx)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as e:
        meta = KATALOG_SWIADCZEN[kod]
        return WynikSprawdzenia(kod, meta["nazwa"], meta["tryb_wyplaty"], Status.BRAK_DANYCH,
                                [f"poprawny format danych ({type(e).__name__}: {e})"], [], [],
                                ["Nie udało się odczytać danych – sprawdź format pól: daty RRRR-MM-DD, liczby, true/false."])


def sprawdz_wszystkie(dane: dict, P: dict | None = None, data_ref: date | None = None) -> list[WynikSprawdzenia]:
    """Sprawdza wszystkie świadczenia z katalogu (w kolejności katalogu) → lista obiektów WynikSprawdzenia."""
    return [sprawdz_swiadczenie(k, dane, P, data_ref) for k in KATALOG_SWIADCZEN]


def sprawdz_wszystkie_jako_slowniki(dane: dict, P: dict | None = None, data_ref: date | None = None) -> list[dict]:
    """To samo co sprawdz_wszystkie, ale jako lista słowników gotowych do JSON (REST API):
    [{kod, nazwa, tryb_wyplaty, status, komunikat, brakujace_dane, powody, uwagi, zrodla}, …]."""
    return [w.jako_slownik() for w in sprawdz_wszystkie(dane, P, data_ref)]


# Wszystkie pola danych użytkownika, które analizują sprawdzanie_swiadczen.py i kalkulator_zasilku.py
# (nazwy jak w zmienne_uzytkownika.json; „dziecko.X” = pole X w elementach listy „dzieci”).
# Przydatne do budowy formularza i do testów kompletności danych.
ANALIZOWANE_POLA: dict[str, list[str]] = {
    "wnioskodawca": ["pesel", "data_urodzenia", "stan_cywilny"],
    "ubezpieczenie_i_zatrudnienie": [
        "tytul_ubezpieczenia", "ubezpieczenie_chorobowe", "data_objecia_ubezpieczeniem_chorobowym",
        "okresy_ubezpieczenia", "ubezpieczenie_chorobowe_w_dniu_porodu_lub_przyjecia", "data_ustania_ubezpieczenia",
        "przyczyna_rozwiazania_umowy", "prawomocny_wyrok_naruszenie_przepisow", "platnik_liczba_ubezpieczonych_chorobowo",
        "platnik_wyplaca_zasilki", "wymiar_etatu", "podstawa_wymiaru_12_miesiecy", "zadeklarowana_podstawa_jdg",
        "zadluzenie_skladkowe"],
    "ciaza_i_zdrowie": [
        "w_ciazy", "przewidywana_data_porodu", "liczba_dzieci_przy_porodzie", "opieka_medyczna_od_10_tyg",
        "zaswiadczenia_e_zla", "okres_zasilkowy_wykorzystany_dni", "hospitalizacja_matki",
        "orzeczenie_niezdolnosci_samodzielnej_egzystencji_matki", "zgon_matki_lub_porzucenie_dziecka"],
    "dzieci": [
        "dzieci", "dziecko.data_urodzenia", "dziecko.urodzone_zywe", "dziecko.data_zgonu",
        "dziecko.tydzien_ciazy_przy_urodzeniu", "dziecko.masa_urodzeniowa_g", "dziecko.hospitalizacja",
        "dziecko.zaswiadczenie_za_zyciem", "dziecko.przyjete_na_wychowanie", "dziecko.odroczony_obowiazek_szkolny"],
    "drugi_rodzic_i_rodzina": ["uznanie_ojcostwa", "drugi_rodzic.tytul_ubezpieczenia"],
    "plan_urlopow": [
        "urlop_macierzynski", "jednolity_wniosek_81_5_procent", "rezygnacja_z_macierzynskiego_po_14_tyg",
        "czesci_urlopu_rodzicielskiego", "urlop_uzupelniajacy", "czesci_urlopu_ojcowskiego"],
    "swiadczenia_gminne": ["dochod_na_osobe", "dochod_rodziny_rok_bazowy", "sklad_rodziny", "inne_pobierane_swiadczenia"],
}


def brakujace_pola(dane: dict) -> list[str]:
    """Które z ANALIZOWANE_POLA nie występują w danych (pola dziecka sprawdzane w każdym elemencie „dzieci”)."""
    braki = []
    dzieci = dane.get("dzieci") if isinstance(dane.get("dzieci"), list) else []
    for lista in ANALIZOWANE_POLA.values():
        for k in lista:
            if k.startswith("dziecko."):
                if not dzieci or any(k.split(".", 1)[1] not in c for c in dzieci):
                    braki.append(k)
            elif pole(dane, k) is BRAK:
                braki.append(k)
    return braki


# ── Podgląd z konsoli ──────────────────────────────────────────────────────
#   python3 sprawdzanie_swiadczen.py dane_uzytkownika.json [RRRR-MM-DD]
# Ten blok wykonuje się WYŁĄCZNIE przy uruchomieniu pliku z konsoli. Przy imporcie
# (from sprawdzanie_swiadczen import …) nic się nie wypisuje – funkcje tylko zwracają listy.
if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        sys.exit("Użycie: python3 sprawdzanie_swiadczen.py dane_uzytkownika.json [RRRR-MM-DD]")
    with open(sys.argv[1], encoding="utf-8") as f:
        wczytane = json.load(f)
    ref = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    for osoba in (wczytane if isinstance(wczytane, list) else [wczytane]):     # plik: jedna osoba albo lista osób
        for w in sprawdz_wszystkie_jako_slowniki(osoba, data_ref=ref):
            print(f"[{w['status']:<11}] {w['komunikat']}")
        print()
