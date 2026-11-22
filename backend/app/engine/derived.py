"""Zmienne wyliczane (przestrzeń `wyl.*` z zmienne_uzytkownika.json v1.1) — deterministycznie, bez AI.

`compute_derived_variables(profile, params, dzis)` zwraca słownik {nazwa_bez_prefiksu: wartość}.
Wartość `None` znaczy „nie da się ustalić z podanych danych” — reguły pokażą wtedy `brak_danych`.

Źródła przepisów (te same, co w scripts/calc/zrodla_i_parametry.py):
- ustawa zasiłkowa: art. 3 (13,71%), 4 (wyczekiwanie), 7 (po ustaniu), 8 (270 dni), 36–38 i 43–50 (podstawa), 61 (płatnik);
- Kodeks pracy: art. 177 § 3 i § 3¹ (przedłużenie umowy do porodu), 180 § 10 (szpital matki),
  180² (urlop uzupełniający), 182¹c (rodzicielski do końca roku 6 r.ż.), 182³ (ojcowski), 183 (przyjęcie dziecka).

Konwencje (przepisy ich nie rozstrzygają — opisane, żeby dało się je zmienić w jednym miejscu):
- kwoty liczymy w `Decimal` i zaokrąglamy do grosza (połówki w górę);
- „dzień porodu = dzień 0”, „n-ty dzień po porodzie = data porodu + n”;
- przed porodem datą odniesienia jest przewidywana data porodu (`wyl.data_odniesienia_porodu`).
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .schemas import Dziecko, OkresUbezpieczenia, UserProfile

CHOROBOWE_AKTYWNE = ("obowiazkowe", "dobrowolne")
TYTULY_AKTYWNE_ZAWODOWO = ("umowa_o_prace", "umowa_zlecenia", "jdg", "wspolpraca_jdg", "ulga_na_start")
TYTULY_JDG = ("jdg", "wspolpraca_jdg", "duchowny")  # podstawa z zadeklarowanej kwoty, zasiłki wypłaca ZUS
TYTULY_BEZ_CHOROBOWEGO = (
    "student", "bezrobotna_z_zasilkiem", "bezrobotna_bez_zasilku", "umowa_o_dzielo", "krus", "ulga_na_start", "brak",
)
STAN_ZGONU = ("martwe", "zgon_do_8_tyg", "zgon_po_8_tyg")
# Świadczenia wykluczające świadczenie rodzicielskie (ustawa o świadczeniach rodzinnych art. 17c ust. 6);
# `rodzina.inne_pobierane_swiadczenia[].rodzaj` porównujemy po normalizacji (małe litery, `_`).
WYKLUCZAJACE_SR7 = (
    "zasilek_macierzynski", "uposazenie_macierzynskie", "swiadczenie_pielegnacyjne",
    "specjalny_zasilek_opiekunczy", "zasilek_dla_opiekuna", "dodatek_urlop_wychowawczy",
)
PESEL_WAGI = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


# ═══════════════════════════════════════ narzędzia ═══════════════════════════════════════


def P(params: dict, path: str) -> Any:
    """Parametr z drzewa `parametry_drzewo` po ścieżce z kropkami (KeyError, gdy brak — błąd kontraktu)."""
    node: Any = params
    for part in path.split("."):
        node = node[part]
    return node


def zl(x: Any) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dodaj_miesiace(d: date, n: int) -> date:
    """Ten sam dzień n miesięcy później (31.01 + 1 mies. = 28/29.02)."""
    m = d.month - 1 + n
    rok, mies = d.year + m // 12, m % 12 + 1
    return date(rok, mies, min(d.day, calendar.monthrange(rok, mies)[1]))


def urodziny(ur: date, lat: int) -> date:
    """Dzień ukończenia `lat` lat (29 lutego -> 1 marca w roku nieprzestępnym)."""
    try:
        return ur.replace(year=ur.year + lat)
    except ValueError:
        return date(ur.year + lat, 3, 1)


def wiek_lat(ur: date, dzis: date) -> int:
    return dzis.year - ur.year - ((dzis.month, dzis.day) < (ur.month, ur.day))


def wiek_miesiecy(ur: date, dzis: date) -> int:
    """Pełne ukończone miesiące życia."""
    m = (dzis.year - ur.year) * 12 + dzis.month - ur.month
    return m - (1 if dzis.day < ur.day else 0)


def i3(*vals: bool | None) -> bool | None:
    """Kleene AND: False wygrywa, potem None."""
    if any(v is False for v in vals):
        return False
    if any(v is None for v in vals):
        return None
    return True


def lub3(*vals: bool | None) -> bool | None:
    """Kleene OR: True wygrywa, potem None."""
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    return False


def nachodzi(a_od: date, a_do: date, b_od: date, b_do: date) -> bool:
    return a_od <= b_do and b_od <= a_do


# ═══════════════════════════════════════ PESEL ═══════════════════════════════════════


def pesel_poprawny(pesel: str | None) -> bool:
    if not pesel or len(pesel) != 11 or not pesel.isdigit():
        return False
    suma = sum(int(c) * w for c, w in zip(pesel[:10], PESEL_WAGI))
    if (10 - suma % 10) % 10 != int(pesel[10]):
        return False
    return data_z_pesel(pesel) is not None


def data_z_pesel(pesel: str) -> date | None:
    """Data urodzenia z PESEL. Stulecie zakodowane w miesiącu: 1–12 → 1900, 21–32 → 2000, 41–52 → 2100,
    61–72 → 2200, 81–92 → 1800."""
    rr, mm, dd = int(pesel[0:2]), int(pesel[2:4]), int(pesel[4:6])
    stulecie = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}.get((mm // 20) * 20)
    if stulecie is None:
        return None
    try:
        return date(stulecie + rr, mm % 20, dd)
    except ValueError:
        return None


def plec_z_pesel(pesel: str) -> str:
    """10. cyfra (przedostatnia): parzysta = K, nieparzysta = M."""
    return "K" if int(pesel[9]) % 2 == 0 else "M"


# ═══════════════════════════════════════ podstawa wymiaru ═══════════════════════════════════════


@dataclass
class PodstawaWymiaru:
    wartosc: Decimal | None
    metoda: str
    miesiace: list[dict] = field(default_factory=list)
    uwagi: list[str] = field(default_factory=list)


def oblicz_podstawe_wymiaru(profile: UserProfile, params: dict) -> PodstawaWymiaru:
    """Podstawa wymiaru zasiłku (miesięczna, już po odliczeniu 13,71%).

    Kolejność:
    1. Przerwa od poprzedniego zasiłku < `zasilek.podstawa.przerwa_dziedziczenia_dni` → podstawa poprzedniego
       zasiłku (art. 43).
    2. JDG (`ubezpieczenie.zadeklarowana_podstawa_jdg`): średnia zadeklarowanych kwot × (1 − 13,71%) z 12 mies.
       (art. 48); krócej niż 12 pełnych miesięcy: śr. najniższa podstawa + 1/12 śr. nadwyżki × liczba miesięcy
       (art. 48a); brak pełnego miesiąca: najniższa podstawa (art. 49). Kwoty powyżej limitu dobrowolnego
       chorobowego są przycinane.
    3. Pozostali (`ubezpieczenie.przychody_12_miesiecy`, ostatnie 12 miesięcy):
       - miesiąc przepracowany w mniej niż połowie → wyłączony (art. 38 ust. 2 pkt 1 / art. 50);
       - pracownik, miesiąc przepracowany w co najmniej połowie, ale niepełny → uzupełniony proporcjonalnie:
         kwota × dni_do_przepracowania / dni_przepracowane (art. 38 ust. 2 pkt 2 w zw. z art. 37);
       - wszystkie miesiące wyłączone → bierzemy wszystkie (pracownik: uzupełnione) (art. 38 ust. 3 / 50 ust. 2);
       - średnia × (1 − 13,71%) (art. 36 ust. 1, art. 3 pkt 3–4);
       - pracownik na pełnym etacie: nie mniej niż płaca minimalna × (1 − 13,71%) (art. 45).
    """
    u = profile.ubezpieczenie
    wn = 1 - Decimal(str(P(params, "zasilek.podstawa.pomniejszenie_procent"))) / 100
    uwagi: list[str] = []

    przerwa = u.przerwa_od_poprzedniego_zasilku_dni
    if przerwa is not None and przerwa < P(params, "zasilek.podstawa.przerwa_dziedziczenia_dni"):
        if u.podstawa_poprzedniego_zasilku is not None:
            return PodstawaWymiaru(
                zl(u.podstawa_poprzedniego_zasilku),
                "art. 43 — podstawa poprzedniego zasiłku (przerwa krótsza niż miesiąc)",
                uwagi=["Wyjątek: zmiana wymiaru czasu pracy między zasiłkami wymaga ustalenia podstawy na nowo."],
            )
        uwagi.append("Przerwa od poprzedniego zasiłku < 1 miesiąca: podstawa powinna być taka jak poprzedniego zasiłku — "
                     "podaj ubezpieczenie.podstawa_poprzedniego_zasilku. Liczę z przychodów (prognoza).")

    if u.tytul in TYTULY_JDG:
        return _podstawa_jdg(profile, params, wn, uwagi)
    return _podstawa_z_przychodow(profile, params, wn, uwagi)


def _ostatnie_12(lista: list, klucz_rok: str = "rok", klucz_mies: str = "miesiac") -> list:
    ok = [m for m in lista if getattr(m, klucz_rok) is not None and getattr(m, klucz_mies) is not None]
    return sorted(ok, key=lambda m: (getattr(m, klucz_rok), getattr(m, klucz_mies)))[-12:]


def _podstawa_jdg(profile: UserProfile, params: dict, wn: Decimal, uwagi: list[str]) -> PodstawaWymiaru:
    deklaracje = profile.ubezpieczenie.zadeklarowana_podstawa_jdg
    if deklaracje is None:
        return PodstawaWymiaru(None, "brak danych: ubezpieczenie.zadeklarowana_podstawa_jdg", uwagi=uwagi)
    najnizsza = Decimal(str(P(params, "zasilek.podstawa.jdg_najnizsza_zl")))
    limit = Decimal(str(P(params, "zasilek.podstawa.limit_dobrowolne_zl")))
    mies = [m for m in _ostatnie_12(deklaracje) if m.kwota is not None]
    if not mies:
        return PodstawaWymiaru(zl(najnizsza * wn), "art. 49 — najniższa podstawa (brak pełnego miesiąca ubezpieczenia)",
                               uwagi=uwagi)
    wiersze = []
    for m in mies:
        kwota = Decimal(str(m.kwota))
        if kwota > limit:
            uwagi.append(f"{m.miesiac:02d}.{m.rok}: kwota powyżej limitu {limit} zł — przycięta.")
            kwota = limit
        wiersze.append({"rok": m.rok, "miesiac": m.miesiac, "kwota": float(kwota), "netto": float(zl(kwota * wn)),
                        "status": "uwzględniony"})
    n = len(wiersze)
    if n >= 12:
        wartosc = zl(sum(Decimal(str(w["netto"])) for w in wiersze) / n)
        return PodstawaWymiaru(wartosc, "art. 48 — średnia z 12 miesięcy (−13,71%)", wiersze, uwagi)
    sr_najn = zl(najnizsza * wn)
    sr_nadw = sum(zl(max(Decimal(0), Decimal(str(w["kwota"])) - najnizsza) * wn) for w in wiersze) / n
    wartosc = zl(sr_najn + sr_nadw * n / 12)
    uwagi.append(f"Ubezpieczenie krótsze niż 12 miesięcy ({n} pełnych) — wzór z art. 48a.")
    return PodstawaWymiaru(wartosc, f"art. 48a — najniższa podstawa + 1/12 nadwyżki × {n}", wiersze, uwagi)


def _podstawa_z_przychodow(profile: UserProfile, params: dict, wn: Decimal, uwagi: list[str]) -> PodstawaWymiaru:
    u = profile.ubezpieczenie
    if u.przychody_12_miesiecy is None:
        return PodstawaWymiaru(None, "brak danych: ubezpieczenie.przychody_12_miesiecy", uwagi=uwagi)
    pracownik = u.tytul == "umowa_o_prace"
    limit = Decimal(str(P(params, "zasilek.podstawa.limit_dobrowolne_zl")))
    mies = [m for m in _ostatnie_12(u.przychody_12_miesiecy) if m.podstawa_wymiaru_skladek is not None]
    if not mies:
        return PodstawaWymiaru(None, "brak pełnego miesiąca przychodów (art. 37/49 wymaga wynagrodzenia z umowy)", uwagi=uwagi)

    def uzupelniona(m) -> Decimal:
        kwota = Decimal(str(m.podstawa_wymiaru_skladek))
        dp, dd = m.dni_przepracowane, m.dni_do_przepracowania
        if pracownik and dp and dd and dp < dd:
            return kwota * Decimal(dd) / Decimal(dp)
        return kwota

    wiersze: list[dict] = []
    for m in mies:
        kwota = Decimal(str(m.podstawa_wymiaru_skladek))
        if not pracownik and u.chorobowe == "dobrowolne" and kwota > limit:
            uwagi.append(f"{m.miesiac:02d}.{m.rok}: przychód powyżej limitu {limit} zł — przycięty.")
            kwota = limit
        dp, dd = m.dni_przepracowane, m.dni_do_przepracowania
        status = "uwzględniony"
        if dd and dp is not None and dp * 2 < dd:
            status = "wyłączony (mniej niż połowa czasu pracy)"
        elif pracownik and dd and dp and dp < dd:
            kwota = kwota * Decimal(dd) / Decimal(dp)
            status = f"uzupełniony ({dp}/{dd} dni)"
        wiersze.append({"rok": m.rok, "miesiac": m.miesiac, "kwota": float(zl(kwota)), "netto": float(zl(kwota * wn)),
                        "status": status})

    uwzgl = [w for w in wiersze if not w["status"].startswith("wyłączony")]
    if not uwzgl:
        uwagi.append("We wszystkich miesiącach przepracowano mniej niż połowę — przyjęto wszystkie (art. 38 ust. 3 / 50 ust. 2).")
        for w, m in zip(wiersze, mies):
            kwota = uzupelniona(m)
            w.update(kwota=float(zl(kwota)), netto=float(zl(kwota * wn)), status="uwzględniony (art. 38 ust. 3)")
        uwzgl = wiersze
    if len(mies) < 12:
        uwagi.append(f"Podano {len(mies)} mies. — średnia z pełnych miesięcy ubezpieczenia (art. 36 ust. 2).")
    wartosc = zl(sum(Decimal(str(w["netto"])) for w in uwzgl) / len(uwzgl))
    metoda = f"art. 36 — średnia z {len(uwzgl)} mies. (−13,71%)"

    if pracownik:
        minimum = zl(Decimal(str(P(params, "zasilek.podstawa.placa_minimalna_zl"))) * wn)
        if u.wymiar_etatu is not None and u.wymiar_etatu >= 1 and wartosc < minimum:
            uwagi.append(f"Podstawa podniesiona do minimum {minimum} zł (art. 45 — pełny etat).")
            wartosc, metoda = minimum, metoda + " → minimum z art. 45"
        elif u.wymiar_etatu is None and wartosc < minimum:
            uwagi.append("Podaj wymiar etatu: przy pełnym etacie podstawa nie może być niższa niż płaca minimalna − 13,71% (art. 45).")
    return PodstawaWymiaru(wartosc, metoda, wiersze, uwagi)


# ═══════════════════════════════════════ dzieci ═══════════════════════════════════════


def _dziecko_zmarle(d: Dziecko, profile: UserProfile) -> bool:
    """Dziecko z porodu, które urodziło się martwe lub zmarło (porod.stan_dziecka)."""
    p = profile.porod
    return (p.stan_dziecka in STAN_ZGONU and p.data_porodu is not None and d.data_urodzenia == p.data_porodu)


def zywe_urodzone_dzieci(profile: UserProfile, dzis: date) -> list[Dziecko] | None:
    if profile.dzieci is None:
        return None
    return [d for d in profile.dzieci
            if d.data_urodzenia is not None and d.data_urodzenia <= dzis and not _dziecko_zmarle(d, profile)]


def dziecko_odniesienia(profile: UserProfile) -> tuple[date | None, Dziecko | None]:
    """Data urodzenia dziecka, którego dotyczą urlopy: przyjęte na wychowanie (etap adopcja), dziecko z porodu,
    najmłodsze dziecko z listy; przed porodem — przewidywana data porodu."""
    dzieci = profile.dzieci or []
    if profile.wnioskodawca.etap == "adopcja_zastepcza":
        przyjete = [d for d in dzieci if d.przyjete_na_wychowanie is not None]
        if przyjete:
            d = max(przyjete, key=lambda x: x.przyjete_na_wychowanie.data_przyjecia or date.min)
            return d.data_urodzenia, d
    ref = profile.porod.data_porodu
    if ref:
        z_porodu = next((d for d in dzieci if d.data_urodzenia == ref), None)
        return ref, z_porodu
    urodzone = [d for d in dzieci if d.data_urodzenia]
    if urodzone:
        d = max(urodzone, key=lambda x: x.data_urodzenia)
        return d.data_urodzenia, d
    return profile.ciaza.przewidywana_data_porodu, None


def wymiar_macierzynskiego_tyg(liczba_dzieci: int, params: dict) -> int:
    tab = P(params, "urlop.macierzynski_tyg")
    return int(tab[str(liczba_dzieci)] if liczba_dzieci < 5 else tab["5_plus"])


def oblicz_wymiar_uzupelniajacego(profile: UserProfile, params: dict) -> tuple[int | None, int | None, str]:
    """(wymiar w tygodniach, limit kategorii, opis) — Kodeks pracy art. 180² § 1–3.

    Kategoria: poród przed `uzupelniajacy_tydzien_graniczny_ciezki` (28.) tyg. lub masa ≤ 1000 g → limit 15 tyg.,
    okno do 15. tyg. po porodzie; poród przed 37. tyg. → limit 8 tyg., okno do 8. tyg.; od 37. tyg. → limit 8 tyg.,
    liczy się pobyt od 5. dnia, jeśli w szpitalu ≥ 2 kolejne dni, z których pierwszy wypada w 5.–28. dniu.
    Wymiar = 1 tydzień za każdy tydzień pobytu w szpitalu w oknie (sumowanie, niepełny tydzień w górę),
    nie więcej niż limit. Przy kilkorgu dzieciach: najniższa masa i dziecko najdłużej w szpitalu (§ 2)."""
    data_porodu = profile.porod.data_porodu
    if data_porodu is None:
        return None, None, "poród jeszcze nie nastąpił"
    dzieci = [d for d in (profile.dzieci or []) if d.data_urodzenia == data_porodu] or (profile.dzieci or [])
    tydz = profile.porod.tydzien_ciazy
    masy = [d.masa_urodzeniowa_g for d in dzieci if d.masa_urodzeniowa_g is not None]
    masa = min(masy) if masy else None
    ciezki = P(params, "urlop.uzupelniajacy_tydzien_graniczny_ciezki")
    graniczny = P(params, "urlop.uzupelniajacy_tydzien_graniczny")
    masa_gr = P(params, "urlop.uzupelniajacy_masa_graniczna_g")
    mx = P(params, "urlop.uzupelniajacy_max_tyg")

    if (tydz is not None and tydz < ciezki) or (masa is not None and masa <= masa_gr):
        kat, limit, okno_od, okno_do = "pkt 1", int(mx["wczesniak_ciezki"]), 0, int(mx["wczesniak_ciezki"]) * 7 - 1
    elif tydz is not None and tydz < graniczny:
        kat, limit, okno_od, okno_do = "pkt 2", int(mx["wczesniak_lekki"]), 0, int(mx["wczesniak_lekki"]) * 7 - 1
    elif tydz is not None:
        kat, limit, okno_od, okno_do = "pkt 3", int(mx["wczesniak_lekki"]), 5, int(mx["wczesniak_lekki"]) * 7 - 1
    else:
        return None, None, "brak danych: porod.tydzien_ciazy"

    if not dzieci or all(d.hospitalizacja is None for d in dzieci):
        return None, limit, f"{kat}: limit {limit} tyg. — brak danych o pobycie dziecka w szpitalu (dzieci[].hospitalizacja)"

    najdluzej = 0
    for d in dzieci:
        dni: set[int] = set()
        for h in d.hospitalizacja or []:
            if h.od is None or h.do is None:
                continue
            dni.update(range((h.od - data_porodu).days, (h.do - data_porodu).days + 1))
        if kat == "pkt 3" and not any(x in dni and x + 1 in dni for x in range(5, 29)):
            continue
        najdluzej = max(najdluzej, len([x for x in dni if okno_od <= x <= okno_do]))
    wymiar = min(limit, math.ceil(najdluzej / 7)) if najdluzej else 0
    return wymiar, limit, f"{kat}: {najdluzej} dni w szpitalu w oknie → {wymiar} tyg. (limit {limit})"


# ═══════════════════════════════════════ ubezpieczenie ═══════════════════════════════════════


def _okresy_chorobowe(okresy: list[OkresUbezpieczenia], dzis: date) -> list[tuple[date, date, str]]:
    out = []
    for o in okresy:
        if o.od is None or o.chorobowe not in CHOROBOWE_AKTYWNE:
            continue
        out.append((o.od, o.do or date.max, o.chorobowe))
    return sorted(out)


def _poczatek_niezdolnosci(profile: UserProfile) -> date | None:
    """Pierwszy dzień niezdolności do pracy: najwcześniejsze e-ZLA z kodem B, a gdy go brak — najwcześniejsze e-ZLA."""
    ezla = [e for e in (profile.zdrowie.ezla or []) if e.od is not None]
    if not ezla:
        return None
    z_b = [e.od for e in ezla if e.kod_B]
    return min(z_b) if z_b else min(e.od for e in ezla)


def spelnia_okres_wyczekiwania(profile: UserProfile, params: dict, dzis: date) -> bool | None:
    """Art. 4 ustawy zasiłkowej: 30 dni (obowiązkowe) / 90 dni (dobrowolne) nieprzerwanego ubezpieczenia
    chorobowego przed dniem niezdolności. Poprzednie okresy wlicza się, gdy przerwa ≤ `ciaglosc_max_przerwa_dni`
    (same dni przerwy się nie liczą). Bez wyczekiwania przy ≥ 10 latach ubezpieczenia obowiązkowego (ust. 3 pkt 3)."""
    start = _poczatek_niezdolnosci(profile)
    if start is None:
        return None
    u = profile.ubezpieczenie
    wyczekiwanie = P(params, "zasilek.wyczekiwanie_dni")
    max_przerwa = P(params, "zasilek.ciaglosc_max_przerwa_dni")
    if u.okresy is not None:
        okresy = _okresy_chorobowe(u.okresy, dzis)
        biezacy = next((o for o in okresy if o[0] <= start <= o[1]), None)
        if biezacy is None:
            # niezdolność po ustaniu ubezpieczenia: okres wyczekiwania liczony do dnia ustania
            wczesniejsze = [o for o in okresy if o[1] < start]
            if not wczesniejsze:
                return False
            biezacy = max(wczesniejsze, key=lambda o: o[1])
        obow_dni = sum((min(o[1], dzis) - o[0]).days + 1 for o in okresy if o[2] == "obowiazkowe" and o[0] <= dzis)
        if obow_dni >= P(params, "zasilek.wyczekiwanie_zwolnienie_lat_obowiazkowego") * 365:
            return True
        wymagane = int(wyczekiwanie[biezacy[2]])
        dni = (min(biezacy[1], start - timedelta(days=1)) - biezacy[0]).days + 1
        poprzedni_start = biezacy[0]
        for o in reversed([x for x in okresy if x[1] < biezacy[0]]):
            przerwa = (poprzedni_start - o[1]).days - 1
            if przerwa > max_przerwa:
                break
            dni += (o[1] - o[0]).days + 1
            poprzedni_start = o[0]
        return dni >= wymagane
    if u.chorobowe is None or u.data_objecia_chorobowym is None:
        return None
    if u.chorobowe not in CHOROBOWE_AKTYWNE:
        return False
    return (start - u.data_objecia_chorobowym).days >= int(wyczekiwanie[u.chorobowe])


def ubezpieczony_w_dniu(profile: UserProfile, dzien: date | None, przedluzona: bool | None, dzis: date) -> bool | None:
    """Czy wnioskodawca ma ubezpieczenie chorobowe w danym dniu. Okres otwarty (`do = null`) kończy się
    na `ubezpieczenie.data_ustania`, a przy umowie terminowej — na `data_konca_umowy`, chyba że umowa
    przedłuża się do dnia porodu (art. 177 § 3 KP)."""
    if dzien is None:
        return None
    u = profile.ubezpieczenie
    koniec_otwartego = u.data_ustania
    if u.tytul == "umowa_o_prace" and u.data_konca_umowy is not None and przedluzona is not True:
        koniec_otwartego = min(filter(None, [koniec_otwartego, u.data_konca_umowy]))
    if u.okresy is not None:
        for o in u.okresy:
            if o.od is None or o.chorobowe not in CHOROBOWE_AKTYWNE:
                continue
            do = o.do or koniec_otwartego or date.max
            if przedluzona and (o.do is None or o.do == u.data_konca_umowy):
                do = max(do, dzien)  # art. 177 § 3 KP: umowa (i ubezpieczenie) trwa do dnia porodu
            if o.od <= dzien <= do:
                return True
        return False
    if u.chorobowe is None:
        return None
    if u.chorobowe == "brak":
        return False
    if u.data_objecia_chorobowym is not None and u.data_objecia_chorobowym > dzien:
        return False
    if koniec_otwartego is not None and koniec_otwartego < dzien and not przedluzona:
        return False
    return True if u.data_objecia_chorobowym is not None else None


def _seria_niezdolnosci(profile: UserProfile, start: date) -> int:
    """Liczba dni nieprzerwanej niezdolności od `start` (łączy przylegające e-ZLA)."""
    ezla = sorted((e.od, e.do) for e in (profile.zdrowie.ezla or []) if e.od and e.do)
    koniec = None
    for od, do in ezla:
        if koniec is None:
            if od <= start <= do:
                koniec = do
        elif od <= koniec + timedelta(days=1):
            koniec = max(koniec, do)
    return (koniec - start).days + 1 if koniec else 0


# ═══════════════════════════════════════ główna funkcja ═══════════════════════════════════════


def compute_derived_variables(profile: UserProfile | dict, params: dict, dzis: date | None = None) -> dict[str, Any]:
    """Wylicza wszystkie zmienne `wyl.*`. `params` = drzewo `parametry_drzewo` z reguly_uprawnien.json."""
    if not isinstance(profile, UserProfile):
        profile = UserProfile.model_validate(profile)
    dzis = dzis or date.today()
    w: dict[str, Any] = {}
    wn, u, pr, cz = profile.wnioskodawca, profile.ubezpieczenie, profile.porod, profile.ciaza

    # ── wnioskodawca ───────────────────────────────────────────────────────
    if pesel_poprawny(wn.pesel):
        w["data_urodzenia_wnioskodawcy"] = data_z_pesel(wn.pesel)
        w["plec_wnioskodawcy"] = plec_z_pesel(wn.pesel)
        w["wiek_wnioskodawcy_lat"] = wiek_lat(w["data_urodzenia_wnioskodawcy"], dzis)
    else:
        w["data_urodzenia_wnioskodawcy"] = w["plec_wnioskodawcy"] = w["wiek_wnioskodawcy_lat"] = None
    w["pracownik"] = None if u.tytul is None else u.tytul == "umowa_o_prace"

    # ── poród i ciąża ──────────────────────────────────────────────────────
    ref = pr.data_porodu or cz.przewidywana_data_porodu
    w["data_odniesienia_porodu"] = ref
    if pr.data_porodu is not None:
        w["dziecko_urodzone"] = True
    elif wn.etap in ("planuje", "w_ciazy") or cz.w_ciazy is True:
        w["dziecko_urodzone"] = False
    else:
        w["dziecko_urodzone"] = None

    poczatek_ciazy = None
    if cz.przewidywana_data_porodu is not None:
        poczatek_ciazy = cz.przewidywana_data_porodu - timedelta(days=P(params, "ochrona.ciaza_czas_trwania_dni"))
    elif pr.data_porodu is not None and pr.tydzien_ciazy is not None:
        poczatek_ciazy = pr.data_porodu - timedelta(weeks=pr.tydzien_ciazy)
    w["data_konca_3_miesiaca_ciazy"] = (
        dodaj_miesiace(poczatek_ciazy, P(params, "ochrona.umowa_terminowa_przedluzenie_od_miesiaca_ciazy"))
        if poczatek_ciazy else None
    )

    # ── art. 177 § 3 KP: przedłużenie umowy terminowej do dnia porodu ─────
    if u.tytul is not None and u.tytul != "umowa_o_prace":
        przedluzona: bool | None = False
    elif u.rodzaj_umowy_o_prace is None:
        przedluzona = None
    elif u.rodzaj_umowy_o_prace in ("czas_nieokreslony", "zastepstwo", "okres_probny_do_1_mies"):
        przedluzona = False
    elif u.data_konca_umowy is None or w["data_konca_3_miesiaca_ciazy"] is None or ref is None:
        przedluzona = None
    else:
        przedluzona = w["data_konca_3_miesiaca_ciazy"] < u.data_konca_umowy < ref
    w["umowa_przedluzona_do_porodu"] = przedluzona

    # ── ubezpieczenie ──────────────────────────────────────────────────────
    w["ubezpieczony_w_dniu_porodu"] = ubezpieczony_w_dniu(profile, ref, przedluzona, dzis)
    if ref is None:
        w["ubezpieczenie_ustalo_przed_porodem"] = None
    else:
        koniec = u.data_ustania
        if u.tytul == "umowa_o_prace" and u.data_konca_umowy is not None and przedluzona is False:
            koniec = min(filter(None, [koniec, u.data_konca_umowy]))
        w["ubezpieczenie_ustalo_przed_porodem"] = koniec is not None and koniec < ref

    if u.data_ustania is None:
        w["w_okresie_po_ustaniu_ubezpieczenia"] = False
    elif profile.zdrowie.ezla is None:
        w["w_okresie_po_ustaniu_ubezpieczenia"] = None
    else:
        po = [e.od for e in profile.zdrowie.ezla if e.od and e.od > u.data_ustania]
        okno = P(params, "zasilek.okno_po_ustaniu_ubezpieczenia_dni")
        min_dni = P(params, "zasilek.po_ustaniu_min_niezdolnosc_dni")
        w["w_okresie_po_ustaniu_ubezpieczenia"] = bool(po) and (min(po) - u.data_ustania).days <= okno \
            and _seria_niezdolnosci(profile, min(po)) >= min_dni

    if u.chorobowe in CHOROBOWE_AKTYWNE and (u.data_ustania is None or u.data_ustania >= dzis):
        aktywne: bool | None = True
    elif u.chorobowe is None:
        aktywne = None
    else:
        aktywne = False
    w["tytul_aktywny_lub_w_oknie"] = lub3(aktywne, w["w_okresie_po_ustaniu_ubezpieczenia"])

    ezla = profile.zdrowie.ezla
    w["ma_ezla_kod_b"] = None if ezla is None else any(e.kod_B is True for e in ezla)
    w["spelnia_okres_wyczekiwania"] = spelnia_okres_wyczekiwania(profile, params, dzis)
    wyk = profile.zdrowie.okres_zasilkowy_wykorzystany_dni
    w["okres_zasilkowy_wyczerpany"] = None if wyk is None else wyk >= P(params, "zasilek.okres_zasilkowy_dni")

    if u.tytul in TYTULY_JDG:
        w["platnik_wyplaca_zasilki"] = False  # art. 61: osobie prowadzącej działalność zasiłki wypłaca ZUS
    elif u.platnik is None or u.platnik.liczba_ubezpieczonych_chorobowo is None:
        w["platnik_wyplaca_zasilki"] = None
    else:
        w["platnik_wyplaca_zasilki"] = u.platnik.liczba_ubezpieczonych_chorobowo > P(params, "platnik.prog_ubezpieczonych")

    podstawa = oblicz_podstawe_wymiaru(profile, params)
    w["podstawa_wymiaru_zasilku"] = float(podstawa.wartosc) if podstawa.wartosc is not None else None

    # ── matka (przejęcie urlopu przez ojca) ────────────────────────────────
    hosp = profile.matka.hospitalizacja
    if hosp is None:
        w["matka_hospitalizowana"] = None
    elif not hosp:
        w["matka_hospitalizowana"] = False
    else:
        pl = profile.plan.urlop_macierzynski
        if wn.rola == "ojciec" and pl is not None and pl.od and pl.do:
            okno_od, okno_do = pl.od, pl.do
        elif pr.data_porodu is not None:
            n = pr.liczba_dzieci or 1
            okno_od = pr.data_porodu + timedelta(weeks=P(params, "urlop.macierzynski_min_matka_szczegolne_tyg"))
            okno_do = pr.data_porodu + timedelta(weeks=wymiar_macierzynskiego_tyg(n, params)) - timedelta(days=1)
        else:
            okno_od = okno_do = None
        if okno_od is None:
            w["matka_hospitalizowana"] = None
        else:
            w["matka_hospitalizowana"] = any(h.od and h.do and nachodzi(h.od, h.do, okno_od, okno_do) for h in hosp)

    w["uzupelniajacy_wymiar_tyg"] = oblicz_wymiar_uzupelniajacego(profile, params)[0]

    # ── dziecko odniesienia: urlopy rodzicielski i ojcowski ────────────────
    ur_ref, dz_ref = dziecko_odniesienia(profile)
    przyjecie = dz_ref.przyjete_na_wychowanie if dz_ref is not None else None
    zmarle_z_porodu = przyjecie is None and pr.stan_dziecka in STAN_ZGONU and pr.data_porodu is not None
    if zmarle_z_porodu:
        # martwe urodzenie / zgon dziecka: urlop rodzicielski nie przysługuje (KP art. 180¹ — tylko urlop macierzyński)
        w["dziecko_w_wieku_urlopu_rodzicielskiego"] = False
    elif ur_ref is None:
        w["dziecko_w_wieku_urlopu_rodzicielskiego"] = None
    elif przyjecie is not None and przyjecie.rodzaj == "przysposobienie":
        w["dziecko_w_wieku_urlopu_rodzicielskiego"] = dzis < urodziny(ur_ref, P(params, "urlop.przyjecie.przysposobienie_max_wiek_lat"))
    else:
        rok_konca = ur_ref.year + P(params, "urlop.rodzicielski_do_konca_roku_wiek_dziecka")
        w["dziecko_w_wieku_urlopu_rodzicielskiego"] = dzis <= date(rok_konca, 12, 31)

    if przyjecie is not None and przyjecie.rodzaj == "przysposobienie":
        if przyjecie.data_uprawomocnienia is None or ur_ref is None:
            w["dziecko_w_oknie_urlopu_ojcowskiego"] = None
        else:
            w["dziecko_w_oknie_urlopu_ojcowskiego"] = (
                dzis < dodaj_miesiace(przyjecie.data_uprawomocnienia, 12)
                and dzis < urodziny(ur_ref, P(params, "urlop.ojcowski_adopcja_max_wiek_dziecka_lat"))
            )
    elif ur_ref is None:
        w["dziecko_w_oknie_urlopu_ojcowskiego"] = None
    else:
        w["dziecko_w_oknie_urlopu_ojcowskiego"] = dzis < dodaj_miesiace(ur_ref, P(params, "urlop.ojcowski_max_wiek_dziecka_mies"))

    # ── przyjęcie dziecka na wychowanie ────────────────────────────────────
    if profile.dzieci is None:
        w["ma_dziecko_przyjete_na_wychowanie"] = None
        w["dziecko_przyjete_w_limicie_wieku"] = None
    else:
        przyjete = [d for d in profile.dzieci if d.przyjete_na_wychowanie is not None]
        w["ma_dziecko_przyjete_na_wychowanie"] = bool(przyjete)
        limity = P(params, "urlop.przyjecie")
        wyniki: list[bool | None] = []
        for d in przyjete:
            if d.data_urodzenia is None or d.przyjete_na_wychowanie.rodzaj is None:
                wyniki.append(None)
                continue
            if d.przyjete_na_wychowanie.rodzaj == "przysposobienie":
                limit = limity["przysposobienie_max_wiek_lat"]
            elif d.odroczony_obowiazek_szkolny:
                limit = limity["rodzina_zastepcza_odroczony_max_wiek_lat"]
            else:
                limit = limity["rodzina_zastepcza_max_wiek_lat"]
            wyniki.append(dzis < urodziny(d.data_urodzenia, limit))
        w["dziecko_przyjete_w_limicie_wieku"] = lub3(*wyniki) if wyniki else False

    # ── świadczenia na dzieci ──────────────────────────────────────────────
    zywe = zywe_urodzone_dzieci(profile, dzis)
    sw = P(params, "swiadczenia")
    if zywe is None:
        for k in ("liczba_dzieci_do_800plus", "ma_dziecko_12_35_mies", "ma_dziecko_w_zlobku", "liczba_dzieci_do_zasilku_rodzinnego",
                  "ma_dziecko_niepelnosprawne", "ma_dziecko_za_zyciem", "liczba_dzieci_do_kdr", "ma_dziecko_do_14_lat"):
            w[k] = None
        maluchy: list[Dziecko] | None = None
    else:
        pewne = [d for d in zywe if wiek_lat(d.data_urodzenia, dzis) < sw["800plus_wiek_max_lat"]
                 and d.pobyt_w_polsce is True and d.w_pieczy_instytucjonalnej is not True]
        niepewne = [d for d in zywe if wiek_lat(d.data_urodzenia, dzis) < sw["800plus_wiek_max_lat"] and d.pobyt_w_polsce is None]
        w["liczba_dzieci_do_800plus"] = len(pewne) if pewne or not niepewne else None

        maluchy = [d for d in zywe if sw["aktywny_rodzic_wiek_od_mies"] <= wiek_miesiecy(d.data_urodzenia, dzis) <= sw["aktywny_rodzic_wiek_do_mies"]]
        w["ma_dziecko_12_35_mies"] = bool(maluchy)
        w["ma_dziecko_w_zlobku"] = any(d.placowka_opieki is not None for d in maluchy)

        w["liczba_dzieci_do_zasilku_rodzinnego"] = sum(
            1 for d in zywe
            if wiek_lat(d.data_urodzenia, dzis) < sw["zasilek_rodzinny_wiek_max_lat"]
            or (d.uczy_sie and wiek_lat(d.data_urodzenia, dzis) < sw["zasilek_rodzinny_wiek_max_ucz_lat"])
        )
        w["ma_dziecko_niepelnosprawne"] = any(d.niepelnosprawnosc is not None for d in zywe)
        w["ma_dziecko_za_zyciem"] = any(d.zaswiadczenie_za_zyciem is True for d in profile.dzieci or [])
        w["liczba_dzieci_do_kdr"] = sum(
            1 for d in zywe
            if d.na_utrzymaniu is not False and (
                wiek_lat(d.data_urodzenia, dzis) < sw["kdr_wiek_max_lat"]
                or (d.uczy_sie and wiek_lat(d.data_urodzenia, dzis) < sw["kdr_wiek_max_ucz_lat"])
                or d.niepelnosprawnosc is not None
            )
        )
        w["ma_dziecko_do_14_lat"] = any(
            wiek_lat(d.data_urodzenia, dzis) < P(params, "zasilek.opiekunczy_wiek_dziecka_max_lat") for d in zywe)

    aktywny = None if u.tytul is None else u.tytul in TYTULY_AKTYWNE_ZAWODOWO
    w["oboje_rodzice_aktywni_zawodowo"] = i3(aktywny, profile.drugi_rodzic.aktywny_zawodowo)

    na_urlopie = _na_urlopie(profile, dzis)
    if maluchy is None:
        w["rodzic_aktywny_w_domu"] = None
    else:
        bez_placowki = any(d.placowka_opieki is None for d in maluchy)
        w["rodzic_aktywny_w_domu"] = bez_placowki and not na_urlopie

    if u.tytul in TYTULY_BEZ_CHOROBOWEGO or u.chorobowe == "brak":
        brak_prawa: bool | None = True
    elif w["ma_dziecko_przyjete_na_wychowanie"] and u.chorobowe in CHOROBOWE_AKTYWNE:
        brak_prawa = False
    elif w["ubezpieczony_w_dniu_porodu"] is None:
        brak_prawa = None
    else:
        brak_prawa = not w["ubezpieczony_w_dniu_porodu"]
    w["brak_prawa_do_zasilku_macierzynskiego"] = brak_prawa

    inne = profile.rodzina.inne_pobierane_swiadczenia
    w["pobiera_swiadczenie_wykluczajace_sr7"] = None if inne is None else any(
        (s.rodzaj or "").strip().lower().replace(" ", "_") in WYKLUCZAJACE_SR7 for s in inne)

    dochod, sklad = profile.rodzina.dochod_rok_bazowy, profile.rodzina.sklad
    skladniki = [dochod.dochody_opodatkowane, dochod.dochody_nieopodatkowane, dochod.dochody_utracone,
                 dochod.dochody_uzyskane] if dochod else [None]
    if not sklad or all(x is None for x in skladniki):
        w["dochod_na_osobe"] = None
    else:
        opod, nieopod, utr, uzysk = (Decimal(str(x or 0)) for x in skladniki)
        w["dochod_na_osobe"] = float(zl((opod + nieopod - utr + uzysk) / 12 / len(sklad)))

    # ── ochrona, terminy, plan ─────────────────────────────────────────────
    zlozone_urlopowe = any((x.kod or "").startswith("URLOP-") for x in profile.wnioski_zlozone or [])
    if cz.w_ciazy is True or na_urlopie or zlozone_urlopowe:
        w["w_okresie_ochrony"] = True
    elif cz.w_ciazy is None and wn.etap in (None, "w_ciazy"):
        w["w_okresie_ochrony"] = None
    else:
        w["w_okresie_ochrony"] = False

    w["dni_do_konca_terminu_81_5"] = (
        P(params, "termin.wniosek_81_5_dni") - (dzis - pr.data_porodu).days if pr.data_porodu else None)
    czesci = profile.plan.czesci_urlopu_rodzicielskiego
    w["laczy_urlop_z_praca"] = None if czesci is None else any((c.wymiar_pracy_w_trakcie or 0) > 0 for c in czesci)

    if w["podstawa_wymiaru_zasilku"] is None:
        w["przysluguje_podwyzszenie_do_sr"] = None
    else:
        wn815 = profile.plan.wniosek_81_5
        proc = P(params, "zasilek.procent.jednolity_wniosek_21_dni") if wn815 and wn815.czy else P(params, "zasilek.procent.rodzicielski")
        miesieczny = Decimal(str(w["podstawa_wymiaru_zasilku"])) * Decimal(str(proc)) / 100
        w["przysluguje_podwyzszenie_do_sr"] = miesieczny < Decimal(str(P(params, "zasilek.podwyzszenie_do_swiadczenia_rodzicielskiego_zl")))
    return w


def _na_urlopie(profile: UserProfile, dzis: date) -> bool:
    """Czy wnioskodawca jest dziś na urlopie macierzyńskim, uzupełniającym, rodzicielskim lub ojcowskim (wg planu)."""
    plan = profile.plan
    okresy = []
    if plan.urlop_macierzynski and plan.urlop_macierzynski.od and plan.urlop_macierzynski.do:
        okresy.append((plan.urlop_macierzynski.od, plan.urlop_macierzynski.do))
    if plan.urlop_uzupelniajacy and plan.urlop_uzupelniajacy.od and plan.urlop_uzupelniajacy.do:
        okresy.append((plan.urlop_uzupelniajacy.od, plan.urlop_uzupelniajacy.do))
    rola = profile.wnioskodawca.rola
    for c in plan.czesci_urlopu_rodzicielskiego or []:
        if c.od and c.do and (c.rodzic is None or c.rodzic == rola):
            okresy.append((c.od, c.do))
    for c in plan.czesci_urlopu_ojcowskiego or []:
        if c.od and c.do and rola == "ojciec":
            okresy.append((c.od, c.do))
    return any(od <= dzis <= do for od, do in okresy)


WYL_KEYS: tuple[str, ...] = (
    "data_urodzenia_wnioskodawcy", "plec_wnioskodawcy", "wiek_wnioskodawcy_lat", "pracownik", "data_odniesienia_porodu",
    "dziecko_urodzone", "ubezpieczony_w_dniu_porodu", "ubezpieczenie_ustalo_przed_porodem",
    "w_okresie_po_ustaniu_ubezpieczenia", "tytul_aktywny_lub_w_oknie", "ma_ezla_kod_b", "spelnia_okres_wyczekiwania",
    "okres_zasilkowy_wyczerpany", "platnik_wyplaca_zasilki", "podstawa_wymiaru_zasilku", "matka_hospitalizowana",
    "uzupelniajacy_wymiar_tyg", "dziecko_w_wieku_urlopu_rodzicielskiego", "dziecko_w_oknie_urlopu_ojcowskiego",
    "ma_dziecko_przyjete_na_wychowanie", "dziecko_przyjete_w_limicie_wieku", "liczba_dzieci_do_800plus",
    "ma_dziecko_12_35_mies", "ma_dziecko_w_zlobku", "oboje_rodzice_aktywni_zawodowo", "rodzic_aktywny_w_domu",
    "brak_prawa_do_zasilku_macierzynskiego", "pobiera_swiadczenie_wykluczajace_sr7", "dochod_na_osobe",
    "liczba_dzieci_do_zasilku_rodzinnego", "ma_dziecko_niepelnosprawne", "ma_dziecko_za_zyciem", "liczba_dzieci_do_kdr",
    "w_okresie_ochrony", "data_konca_3_miesiaca_ciazy", "umowa_przedluzona_do_porodu", "dni_do_konca_terminu_81_5",
    "laczy_urlop_z_praca", "przysluguje_podwyzszenie_do_sr", "ma_dziecko_do_14_lat",
)
