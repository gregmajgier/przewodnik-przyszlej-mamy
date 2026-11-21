"""Kalkulator świadczeń (funkcje wskazane w `wynik.funkcja` w reguly_uprawnien.json) i walidator planu urlopów.

Konwencje (wspólne z scripts/calc/kalkulator_zasilku.py):
- kwoty BRUTTO (przed zaliczką PIT), w `Decimal`, zaokrąglane do grosza (połówki w górę);
- kwota miesięczna = podstawa × procent; stawka dzienna = kwota miesięczna / 30 (ustawa zasiłkowa art. 36 ust. 3);
  kwota za okres = stawka dzienna × liczba dni;
- zasiłek macierzyński niższy niż `zasilek.podwyzszenie_do_swiadczenia_rodzicielskiego_zl` podwyższa się do tej
  kwoty (art. 31 ust. 3a) — porównujemy kwotę brutto (litera ustawy; Poradnik ZUS porównuje kwotę po PIT);
  przy łączeniu urlopu rodzicielskiego z pracą zasiłek zmniejsza się proporcjonalnie (art. 31 ust. 4a) — po podwyższeniu;
- tydzień urlopu = 7 dni kalendarzowych; pierwszy dzień urlopu po porodzie = dzień porodu (KP art. 183¹).
Funkcja kalkulatora dostaje `CalcContext` i zwraca `Wyliczenie`. Brak danych do kwoty nie zmienia statusu
uprawnienia — trafia do `Wyliczenie.brakujace_dane`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .derived import (
    P,
    dodaj_miesiace,
    dziecko_odniesienia,
    oblicz_wymiar_uzupelniajacego,
    urodziny,
    wiek_lat,
    wiek_miesiecy,
    wymiar_macierzynskiego_tyg,
    zl,
    zywe_urodzone_dzieci,
)
from .schemas import BladPlanu, OkresSwiadczenia, UserProfile, Wyliczenie


@dataclass
class CalcContext:
    profile: UserProfile
    wyl: dict[str, Any]
    params: dict
    dzis: date
    rule: dict


def _f(x: Decimal | None) -> float | None:
    return None if x is None else float(zl(x))


def _pct(params: dict, path: str) -> Decimal:
    return Decimal(str(P(params, path)))


def _podstawa(ctx: CalcContext) -> Decimal | None:
    v = ctx.wyl.get("podstawa_wymiaru_zasilku")
    return None if v is None else Decimal(str(v))


def _wyplaca(ctx: CalcContext) -> str:
    return "płatnik składek (pracodawca)" if ctx.wyl.get("platnik_wyplaca_zasilki") else "ZUS"


def kwota_miesieczna(podstawa: Decimal, procent: Decimal, params: dict, *, podwyzszenie: bool = True,
                     wymiar_pracy: float = 0, uwagi: list[str] | None = None) -> Decimal:
    """Krok 1: podstawa × %; krok 2: podwyższenie do kwoty świadczenia rodzicielskiego; krok 3: × (1 − wymiar pracy)."""
    m = podstawa * procent / 100
    if podwyzszenie:
        minimum = _pct(params, "zasilek.podwyzszenie_do_swiadczenia_rodzicielskiego_zl")
        if m < minimum:
            if uwagi is not None:
                uwagi.append(f"Kwota {zl(m)} zł < {minimum} zł — podwyższona do {minimum} zł (ustawa zasiłkowa art. 31 ust. 3a).")
            m = minimum
    if wymiar_pracy:
        m = m * (1 - Decimal(str(wymiar_pracy)))
    return zl(m)


def okres(nazwa: str, od: date | None, dni: int, procent: Decimal | None, miesieczna: Decimal | None,
          wyplaca: str | None = None) -> OkresSwiadczenia:
    stawka = zl(miesieczna / 30) if miesieczna is not None else None
    return OkresSwiadczenia(
        nazwa=nazwa, od=od, do=(od + timedelta(days=dni - 1)) if od and dni > 0 else None, dni=dni,
        tygodnie=round(dni / 7, 2), procent=float(procent) if procent is not None else None,
        stawka_dzienna=_f(stawka), kwota=_f(stawka * dni) if stawka is not None else None, wyplaca=wyplaca,
    )


def _suma(okresy: list[OkresSwiadczenia]) -> float | None:
    if not okresy or any(o.kwota is None for o in okresy):
        return None
    return _f(sum(Decimal(str(o.kwota)) for o in okresy))


def _brak_podstawy(w: Wyliczenie) -> Wyliczenie:
    w.brakujace_dane.append("wyl.podstawa_wymiaru_zasilku")
    w.uwagi.append("Kwoty policzymy po podaniu przychodów z 12 miesięcy (albo zadeklarowanej podstawy JDG).")
    return w


# ═══════════════════════════════ wymiary urlopów (Kodeks pracy) ═══════════════════════════════


def liczba_dzieci(ctx: CalcContext) -> int:
    return ctx.profile.porod.liczba_dzieci or 1


def wymiar_rodzicielskiego_tyg(n: int, za_zyciem: bool, params: dict) -> int:
    t = P(params, "urlop.rodzicielski_tyg")
    if za_zyciem:
        return int(t["za_zyciem_1"] if n == 1 else t["za_zyciem_mnogi"])
    return int(t["1"] if n == 1 else t["mnogi"])


def limit_z_praca_tyg(n: int, za_zyciem: bool, params: dict) -> int:
    t = P(params, "urlop.rodzicielski_z_praca_limit_tyg")
    if za_zyciem:
        return int(t["za_zyciem_1"] if n == 1 else t["za_zyciem_mnogi"])
    return int(t["1"] if n == 1 else t["mnogi"])


def dni_przed_porodem(ctx: CalcContext, porod: date) -> int:
    """Dni urlopu macierzyńskiego wykorzystane przed porodem (maks. 6 tyg., art. 180 § 2 KP)."""
    pl = ctx.profile.plan.urlop_macierzynski
    maks = P(ctx.params, "urlop.macierzynski_przed_porodem_max_tyg") * 7
    if pl and pl.od and pl.od < porod:
        return min((porod - pl.od).days, maks)
    if pl and pl.tygodnie_przed_porodem:
        return min(pl.tygodnie_przed_porodem * 7, maks)
    return 0


def okres_macierzynskiego(ctx: CalcContext) -> tuple[date | None, int]:
    """(początek, liczba dni) urlopu macierzyńskiego matki wg planu i art. 180 KP."""
    porod = ctx.wyl.get("data_odniesienia_porodu")
    if porod is None:
        return None, wymiar_macierzynskiego_tyg(liczba_dzieci(ctx), ctx.params) * 7
    przed = dni_przed_porodem(ctx, porod)
    start = porod - timedelta(days=przed)
    dni = wymiar_macierzynskiego_tyg(liczba_dzieci(ctx), ctx.params) * 7
    rez = ctx.profile.plan.rezygnacja_z_macierzynskiego_po_14_tyg
    if rez and rez.czy and rez.data and rez.data > start:
        dni = min(dni, (rez.data - start).days)
    return start, dni


def wariant_81_5(ctx: CalcContext) -> tuple[bool, list[str]]:
    """Czy obowiązuje 81,5% za cały okres (wniosek do 21 dni po porodzie — art. 30a ustawy zasiłkowej)."""
    uw: list[str] = []
    wn = ctx.profile.plan.wniosek_81_5
    if not (wn and wn.czy):
        return False, uw
    porod = ctx.profile.porod.data_porodu
    if porod and wn.data_zlozenia and (wn.data_zlozenia - porod).days > P(ctx.params, "termin.wniosek_81_5_dni"):
        uw.append(f"Wniosek o 81,5% złożony {wn.data_zlozenia} — po terminie 21 dni od porodu; obowiązuje 100% + 70%.")
        return False, uw
    return True, uw


# ═══════════════════════════════ zasiłki w ciąży ═══════════════════════════════


def oblicz_zasilek_chorobowy_ciaza(ctx: CalcContext) -> Wyliczenie:
    """Pracownik: pierwsze 33 dni niezdolności w roku kalendarzowym (14 dni od roku po ukończeniu 50 lat)
    to wynagrodzenie chorobowe od pracodawcy (KP art. 92 — w ciąży 100%); dalej zasiłek chorobowy 100%
    (art. 11 ust. 2 pkt 1). Okres zasiłkowy 270 dni obejmuje oba (art. 8–9). Stawka dzienna = 1/30 podstawy."""
    w = Wyliczenie(funkcja="oblicz_zasilek_chorobowy_ciaza")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        return _brak_podstawy(w)
    pr = _pct(ctx.params, "zasilek.chorobowy_ciaza_procent")
    mies = kwota_miesieczna(podstawa, pr, ctx.params, podwyzszenie=False)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)

    ezla = [e for e in (ctx.profile.zdrowie.ezla or []) if e.kod_B and e.od and e.do]
    if not ezla:
        w.uwagi.append("Podaj okresy e-ZLA z kodem B, aby policzyć kwotę za zwolnienie.")
        return w
    dni = sorted({e.od + timedelta(days=i) for e in ezla for i in range((e.do - e.od).days + 1)})

    u = ctx.profile.ubezpieczenie
    pracownik = u.tytul == "umowa_o_prace" and u.chorobowe == "obowiazkowe"
    ur = ctx.wyl.get("data_urodzenia_wnioskodawcy")
    if pracownik and ur is None:
        w.uwagi.append("Brak daty urodzenia (PESEL) — przyjęto limit 33 dni wynagrodzenia chorobowego.")
    wykorzystane_okres = ctx.profile.zdrowie.okres_zasilkowy_wykorzystany_dni or 0
    zostalo = P(ctx.params, "zasilek.okres_zasilkowy_dni") - wykorzystane_okres

    pracodawca_w_roku: dict[int, int] = {}
    if pracownik:
        pracodawca_w_roku[ctx.dzis.year] = u.dni_wynagrodzenia_chorobowego_w_roku or 0
    dni_pracodawca: list[date] = []
    dni_zasilek: list[date] = []
    poza_okresem = 0
    for d in dni:
        if zostalo <= 0:
            poza_okresem += 1
            continue
        zostalo -= 1
        if pracownik:
            limit = P(ctx.params, "zasilek.wynagrodzenie_chorobowe_dni.standard")
            if ur is not None and d.year > ur.year + P(ctx.params, "zasilek.wynagrodzenie_chorobowe_wiek_progu"):
                limit = P(ctx.params, "zasilek.wynagrodzenie_chorobowe_dni.po_50_r_z")
            if pracodawca_w_roku.get(d.year, 0) < limit:
                pracodawca_w_roku[d.year] = pracodawca_w_roku.get(d.year, 0) + 1
                dni_pracodawca.append(d)
                continue
        dni_zasilek.append(d)

    if dni_pracodawca:
        w.okresy.append(okres("Wynagrodzenie chorobowe (100% w ciąży)", dni_pracodawca[0], len(dni_pracodawca), pr, mies,
                              "pracodawca"))
        w.okresy[-1].do = dni_pracodawca[-1]
    if dni_zasilek:
        w.okresy.append(okres("Zasiłek chorobowy w ciąży (kod B)", dni_zasilek[0], len(dni_zasilek), pr, mies, _wyplaca(ctx)))
        w.okresy[-1].do = dni_zasilek[-1]
    if poza_okresem:
        w.uwagi.append(f"{poza_okresem} dni po wyczerpaniu okresu zasiłkowego — sprawdź świadczenie rehabilitacyjne (ZNp-7).")
    w.kwota_laczna = _suma(w.okresy)
    w.szczegoly = {"dni_niezdolnosci": len(dni), "dni_pracodawca": len(dni_pracodawca), "dni_zasilku": len(dni_zasilek),
                   "pozostalo_okresu_zasilkowego_dni": max(0, zostalo)}
    return w


def oblicz_zasilek_w_wysokosci_macierzynskiego(ctx: CalcContext) -> Wyliczenie:
    """Po rozwiązaniu umowy w ciąży (upadłość, likwidacja, śmierć pracodawcy, naruszenie przepisów + wyrok):
    100% podstawy od dnia po ustaniu zatrudnienia do dnia porodu (art. 30 ust. 3 ustawy zasiłkowej)."""
    w = Wyliczenie(funkcja="oblicz_zasilek_w_wysokosci_macierzynskiego")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        return _brak_podstawy(w)
    pr = _pct(ctx.params, "zasilek.procent.macierzynski")
    mies = kwota_miesieczna(podstawa, pr, ctx.params, uwagi=w.uwagi)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    ustanie, porod = ctx.profile.ubezpieczenie.data_ustania, ctx.wyl.get("data_odniesienia_porodu")
    if ustanie and porod and porod > ustanie:
        w.okresy.append(okres("Zasiłek w wysokości zasiłku macierzyńskiego", ustanie + timedelta(days=1),
                              (porod - ustanie).days, pr, mies, "ZUS"))
        w.kwota_laczna = _suma(w.okresy)
        if ctx.profile.porod.data_porodu is None:
            w.uwagi.append("Okres liczony do przewidywanej daty porodu — po porodzie kwota się zmieni.")
    else:
        w.brakujace_dane += [k for k, v in (("ubezpieczenie.data_ustania", ustanie), ("ciaza.przewidywana_data_porodu", porod)) if v is None]
    return w


def oblicz_swiadczenie_rehabilitacyjne(ctx: CalcContext) -> Wyliczenie:
    """Art. 18–19 ustawy zasiłkowej: w ciąży 100%; poza ciążą 90% przez pierwsze 90 dni, potem 75%;
    łącznie maks. 360 dni. Okres orzeka lekarz orzecznik ZUS — pokazujemy maksimum."""
    w = Wyliczenie(funkcja="oblicz_swiadczenie_rehabilitacyjne")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        return _brak_podstawy(w)
    w.podstawa_wymiaru = _f(podstawa)
    max_dni = P(ctx.params, "zasilek.rehabilitacyjny_max_dni")
    wyczerpanie = ctx.profile.zdrowie.data_wyczerpania_zasilku
    start = wyczerpanie + timedelta(days=1) if wyczerpanie else None
    if ctx.profile.ciaza.w_ciazy:
        pr = _pct(ctx.params, "zasilek.rehabilitacyjny_ciaza_procent")
        mies = kwota_miesieczna(podstawa, pr, ctx.params, podwyzszenie=False)
        w.okresy.append(okres("Świadczenie rehabilitacyjne w ciąży", start, max_dni, pr, mies, "ZUS"))
    else:
        p1, p2 = _pct(ctx.params, "zasilek.rehabilitacyjny_standard_90_dni_procent"), _pct(ctx.params, "zasilek.rehabilitacyjny_standard_pozostale_procent")
        m1 = kwota_miesieczna(podstawa, p1, ctx.params, podwyzszenie=False)
        m2 = kwota_miesieczna(podstawa, p2, ctx.params, podwyzszenie=False)
        w.okresy.append(okres("Świadczenie rehabilitacyjne — pierwsze 90 dni", start, 90, p1, m1, "ZUS"))
        w.okresy.append(okres("Świadczenie rehabilitacyjne — pozostały okres", start + timedelta(days=90) if start else None,
                              max_dni - 90, p2, m2, "ZUS"))
    w.kwota_miesieczna = _f(mies) if ctx.profile.ciaza.w_ciazy else _f(m1)
    w.stawka_dzienna = w.okresy[0].stawka_dzienna
    w.kwota_laczna = _suma(w.okresy)
    w.uwagi.append("Kwota łączna to maksimum (360 dni) — faktyczny okres ustala lekarz orzecznik ZUS.")
    if start is None:
        w.brakujace_dane.append("zdrowie.data_wyczerpania_zasilku")
    return w


# ═══════════════════════════════ macierzyństwo ═══════════════════════════════


def _tygodnie_rodzicielskiego_rodzica(ctx: CalcContext, rodzic: str, pula: int) -> tuple[list, int]:
    """Części urlopu rodzicielskiego danego rodzica z planu; bez planu: domyślny podział."""
    nieprzen = P(ctx.params, "urlop.rodzicielski_nieprzenoszalny_tyg")
    czesci = [c for c in (ctx.profile.plan.czesci_urlopu_rodzicielskiego or []) if c.rodzic == rodzic and c.od and c.do]
    if czesci:
        return czesci, sum((c.do - c.od).days + 1 for c in czesci)
    if rodzic == "matka":
        return [], (pula - nieprzen) * 7
    matka_bez_prawa = ctx.profile.matka.ubezpieczona_w_dniu_porodu is False
    return [], ((pula - nieprzen) if matka_bez_prawa else nieprzen) * 7


def oblicz_zasilek_macierzynski(ctx: CalcContext) -> Wyliczenie:
    """Zasiłek za urlop macierzyński matki (art. 180 KP: 20/31/33/35/37 tyg., maks. 6 tyg. przed porodem,
    min. 14 tyg. po porodzie osobiście). Porównanie wariantów: 81,5% za cały okres (wniosek do 21 dni po porodzie)
    albo 100% za macierzyński + 70% za rodzicielski matki."""
    w = Wyliczenie(funkcja="oblicz_zasilek_macierzynski")
    start, dni_mac = okres_macierzynskiego(ctx)
    n = liczba_dzieci(ctx)
    za_zyciem = bool(ctx.wyl.get("ma_dziecko_za_zyciem"))
    pula = wymiar_rodzicielskiego_tyg(n, za_zyciem, ctx.params)
    czesci, dni_rod_matki = _tygodnie_rodzicielskiego_rodzica(ctx, "matka", pula)
    w.szczegoly = {"wymiar_macierzynskiego_tyg": wymiar_macierzynskiego_tyg(n, ctx.params), "liczba_dzieci": n,
                   "pula_rodzicielskiego_tyg": pula, "rodzicielski_matki_dni": dni_rod_matki,
                   "dni_przed_porodem": dni_przed_porodem(ctx, ctx.wyl["data_odniesienia_porodu"]) if ctx.wyl.get("data_odniesienia_porodu") else 0}
    podstawa = _podstawa(ctx)
    if podstawa is None:
        if start:
            w.okresy.append(okres("Urlop macierzyński", start, dni_mac, None, None, _wyplaca(ctx)))
        return _brak_podstawy(w)
    w.podstawa_wymiaru = _f(podstawa)
    p100, p70, p815 = (_pct(ctx.params, f"zasilek.procent.{k}") for k in ("macierzynski", "rodzicielski", "jednolity_wniosek_21_dni"))
    m100 = kwota_miesieczna(podstawa, p100, ctx.params)
    m70 = kwota_miesieczna(podstawa, p70, ctx.params)
    m815 = kwota_miesieczna(podstawa, p815, ctx.params)
    stawka = lambda m: m / 30  # noqa: E731
    wariant_a = zl(stawka(m815) * (dni_mac + dni_rod_matki))
    wariant_b = zl(stawka(m100) * dni_mac + stawka(m70) * dni_rod_matki)
    w.szczegoly.update(wariant_81_5={"kwota_miesieczna": _f(m815), "kwota_laczna": _f(wariant_a)},
                       wariant_100_70={"macierzynski_miesiecznie": _f(m100), "rodzicielski_miesiecznie": _f(m70),
                                       "kwota_laczna": _f(wariant_b)})
    czy815, uw = wariant_81_5(ctx)
    w.uwagi += uw
    proc, mies = (p815, m815) if czy815 else (p100, m100)
    kwota_miesieczna(podstawa, proc, ctx.params, uwagi=w.uwagi)  # komunikat o podwyższeniu (jeśli dotyczy)
    w.okresy.append(okres("Urlop macierzyński" + (" (81,5%)" if czy815 else " (100%)"), start, dni_mac, proc, mies, _wyplaca(ctx)))
    w.kwota_miesieczna, w.stawka_dzienna = _f(mies), _f(mies / 30)
    w.kwota_laczna = _suma(w.okresy)
    w.szczegoly["wybrany_wariant"] = "81,5%" if czy815 else "100% + 70%"
    w.uwagi.append("Wariant 81,5% daje równą kwotę przez cały okres; łączna suma obu wariantów jest zbliżona.")
    if ctx.profile.porod.data_porodu is None:
        w.uwagi.append("Daty liczone od przewidywanej daty porodu.")
    return w


def _rodzicielski_okresy(ctx: CalcContext, rodzic: str, procent: Decimal, podstawa: Decimal, start: date | None,
                         w: Wyliczenie) -> Decimal:
    """Okresy urlopu rodzicielskiego rodzica z wydłużeniem przy pracy (KP art. 182¹f: wydłużenie = dni × wymiar
    pracy, bez niepełnego dnia; zasiłek × (1 − wymiar pracy) — art. 31 ust. 4a)."""
    n, za_zyciem = liczba_dzieci(ctx), bool(ctx.wyl.get("ma_dziecko_za_zyciem"))
    pula = wymiar_rodzicielskiego_tyg(n, za_zyciem, ctx.params)
    czesci, dni = _tygodnie_rodzicielskiego_rodzica(ctx, rodzic, pula)
    p70 = _pct(ctx.params, "zasilek.procent.rodzicielski")
    pierwsza = kwota_miesieczna(podstawa, procent, ctx.params)
    if czesci:
        for i, c in enumerate(czesci, 1):
            dni_c = (c.do - c.od).days + 1
            wp = c.wymiar_pracy_w_trakcie or 0
            m = kwota_miesieczna(podstawa, procent, ctx.params, wymiar_pracy=wp, uwagi=w.uwagi if i == 1 else None)
            w.okresy.append(okres(f"Urlop rodzicielski — część {i}" + (f" (praca {wp:g} etatu)" if wp else ""),
                                  c.od, dni_c, procent, m, _wyplaca(ctx)))
            if wp:
                wydl = math.floor(dni_c * wp)
                m_full = kwota_miesieczna(podstawa, procent, ctx.params)
                w.okresy.append(okres(f"Urlop rodzicielski — wydłużenie części {i} (art. 182¹f KP)",
                                      c.do + timedelta(days=1), wydl, procent, m_full, _wyplaca(ctx)))
        limit = limit_z_praca_tyg(n, za_zyciem, ctx.params) * 7
        if sum(o.dni or 0 for o in w.okresy if o.nazwa.startswith("Urlop rodzicielski")) > limit:
            w.uwagi.append(f"Łączny urlop z wydłużeniem przekracza limit {limit // 7} tyg. (art. 182¹f § 1 KP).")
    else:
        m = kwota_miesieczna(podstawa, procent, ctx.params, uwagi=w.uwagi)
        w.okresy.append(okres("Urlop rodzicielski (domyślny podział)", start, dni, procent, m, _wyplaca(ctx)))
        w.uwagi.append("Brak planu części urlopu — przyjęto domyślny podział puli.")
    if procent != p70:
        w.uwagi.append("9 tygodni urlopu rodzicielskiego drugiego rodzica jest zawsze płatne 70% (art. 31 ust. 3f).")
    return pierwsza


def oblicz_zasilek_rodzicielski(ctx: CalcContext) -> Wyliczenie:
    """Urlop rodzicielski wnioskodawcy: pula 41/43 tyg. (Za życiem 65/67), 9 tyg. nieprzenoszalne dla każdego
    rodzica (art. 182¹a KP); 70% albo 81,5% (wniosek do 21 dni po porodzie); łączenie z pracą do 1/2 etatu."""
    w = Wyliczenie(funkcja="oblicz_zasilek_rodzicielski")
    rodzic = "ojciec" if ctx.profile.wnioskodawca.rola == "ojciec" else "matka"
    n, za_zyciem = liczba_dzieci(ctx), bool(ctx.wyl.get("ma_dziecko_za_zyciem"))
    pula = wymiar_rodzicielskiego_tyg(n, za_zyciem, ctx.params)
    w.szczegoly = {"pula_tyg": pula, "nieprzenoszalne_tyg": P(ctx.params, "urlop.rodzicielski_nieprzenoszalny_tyg"),
                   "rodzic": rodzic, "liczba_dzieci": n, "za_zyciem": za_zyciem}
    podstawa = _podstawa(ctx)
    if podstawa is None:
        return _brak_podstawy(w)
    w.podstawa_wymiaru = _f(podstawa)
    czy815, uw = wariant_81_5(ctx)
    w.uwagi += uw
    procent = _pct(ctx.params, "zasilek.procent.jednolity_wniosek_21_dni" if czy815 else "zasilek.procent.rodzicielski")
    start = None
    if rodzic == "matka":
        s_mac, d_mac = okres_macierzynskiego(ctx)
        start = s_mac + timedelta(days=d_mac) if s_mac else None
        uz = ctx.wyl.get("uzupelniajacy_wymiar_tyg")
        if start and uz:
            start += timedelta(weeks=uz)
    elif ctx.profile.matka.data_konca_urlopu_macierzynskiego:
        start = ctx.profile.matka.data_konca_urlopu_macierzynskiego + timedelta(days=1)
    mies = _rodzicielski_okresy(ctx, rodzic, procent, podstawa, start, w)
    w.kwota_miesieczna, w.stawka_dzienna = _f(mies), _f(mies / 30)
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_macierzynski_ojciec(ctx: CalcContext) -> Wyliczenie:
    """Ojciec przejmuje pozostałą część urlopu macierzyńskiego (art. 180 § 4–17 KP): 100%, od dnia po końcu
    urlopu matki do końca wymiaru liczonego od porodu."""
    w = Wyliczenie(funkcja="oblicz_zasilek_macierzynski_ojciec")
    porod = ctx.profile.porod.data_porodu
    n = liczba_dzieci(ctx)
    if porod is None:
        w.brakujace_dane.append("porod.data_porodu")
        return w
    koniec = porod + timedelta(weeks=wymiar_macierzynskiego_tyg(n, ctx.params)) - timedelta(days=1)
    koniec_matki = ctx.profile.matka.data_konca_urlopu_macierzynskiego
    if koniec_matki is None:
        rez = ctx.profile.plan.rezygnacja_z_macierzynskiego_po_14_tyg
        koniec_matki = rez.data - timedelta(days=1) if rez and rez.data else porod + timedelta(
            weeks=P(ctx.params, "urlop.macierzynski_min_matka_tyg")) - timedelta(days=1)
        w.uwagi.append(f"Przyjęto koniec urlopu matki {koniec_matki} (podaj matka.data_konca_urlopu_macierzynskiego).")
    start = koniec_matki + timedelta(days=1)
    dni = max(0, (koniec - koniec_matki).days)
    w.szczegoly = {"koniec_wymiaru_macierzynskiego": koniec.isoformat(), "dni_dla_ojca": dni}
    podstawa = _podstawa(ctx)
    pr = _pct(ctx.params, "zasilek.procent.macierzynski")
    if podstawa is None:
        w.okresy.append(okres("Przejęty urlop macierzyński", start, dni, pr, None, _wyplaca(ctx)))
        return _brak_podstawy(w)
    mies = kwota_miesieczna(podstawa, pr, ctx.params, uwagi=w.uwagi)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    w.okresy.append(okres("Przejęty urlop macierzyński (100%)", start, dni, pr, mies, _wyplaca(ctx)))
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_ojcowski(ctx: CalcContext) -> Wyliczenie:
    """14 dni, jednorazowo albo w 2 częściach po min. 7 dni, 100%, do 12. miesiąca życia dziecka (art. 182³ KP).
    Liczba dzieci z porodu nie wydłuża urlopu."""
    w = Wyliczenie(funkcja="oblicz_zasilek_ojcowski")
    pr = _pct(ctx.params, "zasilek.procent.ojcowski")
    podstawa = _podstawa(ctx)
    mies = kwota_miesieczna(podstawa, pr, ctx.params, uwagi=w.uwagi) if podstawa is not None else None
    czesci = [c for c in (ctx.profile.plan.czesci_urlopu_ojcowskiego or []) if c.od and c.do]
    if czesci:
        for i, c in enumerate(czesci, 1):
            w.okresy.append(okres(f"Urlop ojcowski — część {i}", c.od, (c.do - c.od).days + 1, pr, mies, _wyplaca(ctx)))
    else:
        w.okresy.append(okres("Urlop ojcowski (14 dni)", None, P(ctx.params, "urlop.ojcowski_dni"), pr, mies, _wyplaca(ctx)))
    ur, _ = dziecko_odniesienia(ctx.profile)
    if ur:
        w.szczegoly["termin_wykorzystania"] = (dodaj_miesiace(ur, P(ctx.params, "urlop.ojcowski_max_wiek_dziecka_mies")) - timedelta(days=1)).isoformat()
    if podstawa is None:
        return _brak_podstawy(w)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_uzupelniajacy(ctx: CalcContext) -> Wyliczenie:
    """Uzupełniający urlop macierzyński (art. 180² KP): 1 tydzień za każdy tydzień pobytu dziecka w szpitalu,
    maks. 15 albo 8 tyg.; jednorazowo, bezpośrednio po urlopie macierzyńskim; 100%."""
    w = Wyliczenie(funkcja="oblicz_zasilek_uzupelniajacy")
    wymiar, limit, opis = oblicz_wymiar_uzupelniajacego(ctx.profile, ctx.params)
    w.szczegoly = {"wymiar_tyg": wymiar, "limit_tyg": limit, "wyliczenie": opis}
    if not wymiar:
        w.brakujace_dane.append("dzieci[].hospitalizacja")
        return w
    s_mac, d_mac = okres_macierzynskiego(ctx)
    start = s_mac + timedelta(days=d_mac) if s_mac else None
    pr = _pct(ctx.params, "zasilek.procent.uzupelniajacy")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        w.okresy.append(okres("Uzupełniający urlop macierzyński", start, wymiar * 7, pr, None, _wyplaca(ctx)))
        return _brak_podstawy(w)
    mies = kwota_miesieczna(podstawa, pr, ctx.params, uwagi=w.uwagi)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    w.okresy.append(okres(f"Uzupełniający urlop macierzyński ({wymiar} tyg., 100%)", start, wymiar * 7, pr, mies, _wyplaca(ctx)))
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_adopcja(ctx: CalcContext) -> Wyliczenie:
    """Przyjęcie dziecka na wychowanie (art. 183 KP): urlop na warunkach macierzyńskiego jak przy porodzie
    (20–37 tyg.), nie dłużej niż do ukończenia przez dziecko 7 lat (10 przy odroczonym obowiązku szkolnym)
    w rodzinie zastępczej / 14 lat przy przysposobieniu, ale nie krócej niż 9 tyg. (§ 3 — wtedy rodzicielski 38/62 tyg.);
    rodzicielski 41/43 (Za życiem 65/67). Zasiłek 100% i 70%."""
    w = Wyliczenie(funkcja="oblicz_zasilek_adopcja")
    ur, dz = dziecko_odniesienia(ctx.profile)
    prz = dz.przyjete_na_wychowanie if dz else None
    if ur is None or prz is None or prz.rodzaj is None:
        w.brakujace_dane += ["dzieci[].data_urodzenia", "dzieci[].przyjete_na_wychowanie"]
        return w
    limity = P(ctx.params, "urlop.przyjecie")
    if prz.rodzaj == "przysposobienie":
        wiek = limity["przysposobienie_max_wiek_lat"]
    else:
        wiek = limity["rodzina_zastepcza_odroczony_max_wiek_lat" if dz.odroczony_obowiazek_szkolny else "rodzina_zastepcza_max_wiek_lat"]
    granica = urodziny(ur, wiek)
    start = prz.data_przyjecia or ctx.dzis
    n = liczba_dzieci(ctx)
    std = wymiar_macierzynskiego_tyg(n, ctx.params) * 7
    dni = min(std, max(0, (granica - start).days))
    par3 = dni < limity["min_tyg"] * 7
    if par3:
        dni = limity["min_tyg"] * 7
    za_zyciem = bool(dz.zaswiadczenie_za_zyciem)
    if par3:
        rod_tyg = int(limity["rodzicielski_par3_tyg"]["za_zyciem" if za_zyciem else "zwykly"])
    else:
        rod_tyg = wymiar_rodzicielskiego_tyg(n, za_zyciem, ctx.params)
    rod_dni = rod_tyg * 7
    if prz.rodzaj == "przysposobienie" and not par3:
        rod_dni = max(0, min(rod_dni, (granica - (start + timedelta(days=dni))).days))
    w.szczegoly = {"limit_wieku_lat": wiek, "granica_wieku": granica.isoformat(), "na_warunkach_macierzynskiego_dni": dni,
                   "minimum_9_tyg": par3, "rodzicielski_dni": rod_dni}
    p100, p70 = _pct(ctx.params, "zasilek.procent.macierzynski"), _pct(ctx.params, "zasilek.procent.rodzicielski")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        w.okresy += [okres("Urlop na warunkach urlopu macierzyńskiego", start, dni, p100, None, _wyplaca(ctx)),
                     okres("Urlop rodzicielski", start + timedelta(days=dni), rod_dni, p70, None, _wyplaca(ctx))]
        return _brak_podstawy(w)
    m100 = kwota_miesieczna(podstawa, p100, ctx.params, uwagi=w.uwagi)
    m70 = kwota_miesieczna(podstawa, p70, ctx.params)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(m100), _f(m100 / 30)
    w.okresy += [okres("Urlop na warunkach urlopu macierzyńskiego (100%)", start, dni, p100, m100, _wyplaca(ctx)),
                 okres("Urlop rodzicielski (70%)", start + timedelta(days=dni), rod_dni, p70, m70, _wyplaca(ctx))]
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_martwe_urodzenie(ctx: CalcContext) -> Wyliczenie:
    """Art. 180¹ KP: martwe urodzenie lub zgon przed upływem 8 tyg. życia — 8 tyg. po porodzie, nie krócej niż
    7 dni od zgonu; zgon po 8 tyg. — do 7 dni od zgonu. Przy ciąży mnogiej wymiar wg liczby dzieci żyjących,
    nie krócej niż 7 dni od zgonu. Zasiłek 100%."""
    w = Wyliczenie(funkcja="oblicz_zasilek_martwe_urodzenie")
    pr_, porod = ctx.profile.porod, ctx.profile.porod.data_porodu
    if porod is None:
        w.brakujace_dane.append("porod.data_porodu")
        return w
    zgon = porod if pr_.stan_dziecka == "martwe" else pr_.data_zgonu_dziecka
    if zgon is None:
        w.brakujace_dane.append("porod.data_zgonu_dziecka")
        return w
    n = liczba_dzieci(ctx)
    przed = dni_przed_porodem(ctx, porod)
    min_dni = P(ctx.params, "urlop.martwe_min_dni_od_zgonu")
    standard_koniec = porod + timedelta(days=wymiar_macierzynskiego_tyg(n, ctx.params) * 7 - przed - 1)
    zyjace = n - 1
    if zyjace <= 0:
        osiem = porod + timedelta(weeks=P(ctx.params, "urlop.martwe_urodzenie_tyg")) - timedelta(days=1)
        koniec = max(osiem, zgon + timedelta(days=min_dni)) if zgon <= osiem else zgon + timedelta(days=min_dni)
    else:
        koniec = max(porod + timedelta(days=wymiar_macierzynskiego_tyg(zyjace, ctx.params) * 7 - przed - 1),
                     zgon + timedelta(days=min_dni))
        w.uwagi.append(f"Ciąża mnoga: wymiar wg liczby dzieci żyjących ({zyjace}).")
    koniec = min(koniec, standard_koniec)
    start = porod - timedelta(days=przed)
    dni = (koniec - start).days + 1
    w.szczegoly = {"data_zgonu": zgon.isoformat(), "koniec_urlopu": koniec.isoformat(), "dni": dni}
    pr = _pct(ctx.params, "zasilek.procent.macierzynski")
    podstawa = _podstawa(ctx)
    if podstawa is None:
        w.okresy.append(okres("Urlop macierzyński po stracie dziecka", start, dni, pr, None, _wyplaca(ctx)))
        return _brak_podstawy(w)
    mies = kwota_miesieczna(podstawa, pr, ctx.params, uwagi=w.uwagi)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    w.okresy.append(okres("Urlop macierzyński po stracie dziecka (100%)", start, dni, pr, mies, _wyplaca(ctx)))
    w.kwota_laczna = _suma(w.okresy)
    return w


def oblicz_zasilek_opiekunczy(ctx: CalcContext) -> Wyliczenie:
    """80% podstawy za dzień opieki, łącznie do 60 dni w roku kalendarzowym (art. 32–35 ustawy zasiłkowej)."""
    w = Wyliczenie(funkcja="oblicz_zasilek_opiekunczy")
    limit = P(ctx.params, "zasilek.opiekunczy_max_dni_w_roku")
    zostalo = max(0, limit - (ctx.profile.zdrowie.zasilek_opiekunczy_wykorzystany_dni or 0))
    w.szczegoly = {"limit_dni_w_roku": limit, "pozostalo_dni": zostalo}
    podstawa = _podstawa(ctx)
    if podstawa is None:
        return _brak_podstawy(w)
    pr = _pct(ctx.params, "zasilek.opiekunczy_procent")
    mies = kwota_miesieczna(podstawa, pr, ctx.params, podwyzszenie=False)
    w.podstawa_wymiaru, w.kwota_miesieczna, w.stawka_dzienna = _f(podstawa), _f(mies), _f(mies / 30)
    w.okresy.append(okres(f"Zasiłek opiekuńczy — pozostałe {zostalo} dni w {ctx.dzis.year} r.", None, zostalo, pr, mies, _wyplaca(ctx)))
    w.kwota_laczna = _suma(w.okresy)
    w.uwagi.append("Kwota łączna to maksimum za niewykorzystane dni w tym roku; wypłata za faktyczne dni opieki.")
    return w


def oblicz_zasilek_pogrzebowy(ctx: CalcContext) -> Wyliczenie:
    """Jednorazowo `zasilek.pogrzebowy_zl`; wniosek najpóźniej 12 miesięcy od dnia śmierci (przy martwym
    urodzeniu — od dnia porodu)."""
    w = Wyliczenie(funkcja="oblicz_zasilek_pogrzebowy", kwota_jednorazowa=float(P(ctx.params, "zasilek.pogrzebowy_zl")))
    w.kwota_laczna = w.kwota_jednorazowa
    pr = ctx.profile.porod
    zgon = pr.data_porodu if pr.stan_dziecka == "martwe" else pr.data_zgonu_dziecka
    if zgon:
        w.szczegoly["termin_wniosku"] = (dodaj_miesiace(zgon, P(ctx.params, "termin.pogrzebowy_mies")) - timedelta(days=1)).isoformat()
    else:
        w.brakujace_dane.append("porod.data_zgonu_dziecka")
    w.uwagi.append("Zasiłek wypłaca ZUS osobie, która pokryła koszty pogrzebu (rachunki dołącz do wniosku Z-12).")
    return w


# ═══════════════════════════════ świadczenia rodzinne i stałe ═══════════════════════════════


def oblicz_aktywny_rodzic(ctx: CalcContext) -> Wyliczenie:
    """Aktywny rodzic: na każde dziecko 12–35 mies. — „aktywni rodzice w pracy” lub „aktywnie w żłobku”
    (do wysokości opłaty) albo „aktywnie w domu”; tryby się wykluczają, pokazujemy najkorzystniejszy.
    Przy opiece naprzemiennej kwota dzielona po połowie. Kwoty i warunki: do weryfikacji z ZUS."""
    w = Wyliczenie(funkcja="oblicz_aktywny_rodzic")
    sw = P(ctx.params, "swiadczenia")
    zywe = zywe_urodzone_dzieci(ctx.profile, ctx.dzis) or []
    maluchy = [d for d in zywe if sw["aktywny_rodzic_wiek_od_mies"] <= wiek_miesiecy(d.data_urodzenia, ctx.dzis) <= sw["aktywny_rodzic_wiek_do_mies"]]
    suma = Decimal(0)
    tryby = []
    for d in maluchy:
        opcje = {}
        if ctx.wyl.get("oboje_rodzice_aktywni_zawodowo"):
            opcje["w_pracy"] = Decimal(str(sw["aktywny_rodzic_praca_zl"]))
        if d.placowka_opieki is not None:
            maks = Decimal(str(sw["aktywny_rodzic_zlobek_zl"]))
            oplata = d.placowka_opieki.oplata_miesieczna
            opcje["w_zlobku"] = min(maks, Decimal(str(oplata))) if oplata is not None else maks
        else:
            opcje["w_domu"] = Decimal(str(sw["aktywny_rodzic_dom_zl"]))
        tryb, kwota = max(opcje.items(), key=lambda kv: kv[1])
        tryby.append({"dziecko": d.imie, "tryb": tryb, "kwota": float(kwota), "dostepne": {k: float(v) for k, v in opcje.items()}})
        suma += kwota
    if ctx.profile.rodzina.opieka_naprzemienna:
        suma /= 2
        w.uwagi.append("Opieka naprzemienna: kwota dzielona po połowie między rodziców.")
    w.kwota_miesieczna = _f(suma)
    w.szczegoly = {"dzieci": tryby}
    w.uwagi.append("Kwoty i warunki trybów programu do potwierdzenia z ZUS (do_weryfikacji).")
    return w


def oblicz_zasilek_rodzinny(ctx: CalcContext) -> Wyliczenie:
    """Zasiłek rodzinny wg wieku dziecka (do 5 lat / 5–18 / 18–24) + jednorazowy dodatek z tytułu urodzenia
    (dziecko urodzone w ostatnich 12 miesiącach). Kwoty — parametry do weryfikacji."""
    w = Wyliczenie(funkcja="oblicz_zasilek_rodzinny")
    sw = P(ctx.params, "swiadczenia")
    kw = sw["zasilek_rodzinny_kwoty_zl"]
    suma = Decimal(0)
    dzieci = []
    for d in zywe_urodzone_dzieci(ctx.profile, ctx.dzis) or []:
        wiek = wiek_lat(d.data_urodzenia, ctx.dzis)
        if wiek < 5:
            k = kw["do_5_lat"]
        elif wiek < sw["zasilek_rodzinny_wiek_max_lat"]:
            k = kw["od_5_do_18_lat"]
        elif d.uczy_sie and wiek < sw["zasilek_rodzinny_wiek_max_ucz_lat"]:
            k = kw["od_18_do_24_lat"]
        else:
            continue
        suma += Decimal(str(k))
        dzieci.append({"dziecko": d.imie, "wiek": wiek, "kwota": k})
    w.kwota_miesieczna = _f(suma)
    nowo = [d for d in zywe_urodzone_dzieci(ctx.profile, ctx.dzis) or []
            if dodaj_miesiace(d.data_urodzenia, 12) > ctx.dzis]
    if nowo:
        w.kwota_jednorazowa = float(sw["dodatek_urodzenie_zl"]) * len(nowo)
        w.uwagi.append("Dodatek z tytułu urodzenia dziecka — wniosek do 12 miesięcy od urodzenia.")
    w.szczegoly = {"dzieci": dzieci}
    w.uwagi.append("Kwoty zasiłku rodzinnego i dodatków do potwierdzenia (do_weryfikacji).")
    return w


def kwota_stala(ctx: CalcContext) -> Wyliczenie:
    """800+ (miesięcznie na dziecko), becikowe (jednorazowo na każde dziecko z porodu), Za życiem (jednorazowo
    na dziecko z zaświadczeniem)."""
    w = Wyliczenie(funkcja="kwota_stala")
    sw = P(ctx.params, "swiadczenia")
    rid = ctx.rule["id"]
    if rid == "ZASILEK_800PLUS":
        n = ctx.wyl.get("liczba_dzieci_do_800plus") or 0
        kwota = Decimal(str(sw["800plus_zl_mies"])) * n
        if ctx.profile.rodzina.opieka_naprzemienna:
            kwota /= 2
            w.uwagi.append("Opieka naprzemienna: kwota dzielona po połowie.")
        w.kwota_miesieczna = _f(kwota)
        w.szczegoly = {"liczba_dzieci": n}
    elif rid == "BECIKOWE":
        n = liczba_dzieci(ctx) if ctx.profile.porod.data_porodu else 1
        w.kwota_jednorazowa = float(sw["becikowe_zl"]) * n
    elif rid == "ZA_ZYCIEM_4000":
        n = sum(1 for d in ctx.profile.dzieci or [] if d.zaswiadczenie_za_zyciem) or 1
        w.kwota_jednorazowa = float(sw["za_zyciem_zl"]) * n
    else:
        param = ctx.rule["wynik"]["parametry"][0]
        w.kwota_jednorazowa = float(P(ctx.params, param))
    w.kwota_laczna = w.kwota_jednorazowa
    return w


def kwota_stala_okres(ctx: CalcContext) -> Wyliczenie:
    """Świadczenie rodzicielskie (SR-7): stała kwota miesięczna przez 52/65/67/69/71 tyg. wg liczby dzieci
    z porodu, od dnia porodu (wniosek do 3 miesięcy = za cały okres)."""
    w = Wyliczenie(funkcja="kwota_stala_okres")
    sw = P(ctx.params, "swiadczenia")
    n = liczba_dzieci(ctx)
    tab = sw["rodzicielskie_tyg"]
    tyg = int(tab[str(n)] if n < 5 else tab["5_plus"])
    mies = Decimal(str(sw["rodzicielskie_zl_mies"]))
    if ctx.profile.rodzina.opieka_naprzemienna:
        mies /= 2
    start = ctx.wyl.get("data_odniesienia_porodu")
    w.kwota_miesieczna = _f(mies)
    w.okresy.append(OkresSwiadczenia(nazwa=f"Świadczenie rodzicielskie ({tyg} tyg.)", od=start,
                                     do=start + timedelta(weeks=tyg) - timedelta(days=1) if start else None,
                                     dni=tyg * 7, tygodnie=tyg, kwota=None, wyplaca="gmina"))
    w.szczegoly = {"okres_tyg": tyg, "liczba_dzieci": n}
    w.uwagi.append("Okres świadczenia wg liczby dzieci — do weryfikacji z gminą.")
    return w


def kwota_brak(ctx: CalcContext) -> Wyliczenie:
    return Wyliczenie(funkcja="kwota_brak", uwagi=["Uprawnienie bez kwoty pieniężnej."])


def brak(ctx: CalcContext) -> Wyliczenie:
    w = Wyliczenie(funkcja="brak")
    if ctx.rule["id"] == "OCHRONA_STOSUNKU_PRACY" and ctx.wyl.get("umowa_przedluzona_do_porodu"):
        w.uwagi.append(f"Twoja umowa terminowa przedłuża się do dnia porodu (art. 177 § 3 KP) — "
                       f"zamiast {ctx.profile.ubezpieczenie.data_konca_umowy} trwa do {ctx.wyl.get('data_odniesienia_porodu')}.")
    return w


FUNKCJE: dict[str, Callable[[CalcContext], Wyliczenie]] = {f.__name__: f for f in (
    oblicz_zasilek_chorobowy_ciaza, oblicz_zasilek_w_wysokosci_macierzynskiego, oblicz_swiadczenie_rehabilitacyjne,
    oblicz_zasilek_macierzynski, oblicz_zasilek_rodzicielski, oblicz_zasilek_macierzynski_ojciec, oblicz_zasilek_ojcowski,
    oblicz_zasilek_uzupelniajacy, oblicz_zasilek_adopcja, oblicz_zasilek_martwe_urodzenie, oblicz_zasilek_opiekunczy,
    oblicz_zasilek_pogrzebowy, oblicz_aktywny_rodzic, oblicz_zasilek_rodzinny, kwota_stala, kwota_stala_okres,
    kwota_brak, brak,
)}


# ═══════════════════════════════ walidacja planu urlopów ═══════════════════════════════


def waliduj_plan_urlopow(profile: UserProfile, wyl: dict[str, Any], params: dict, dzis: date) -> list[BladPlanu]:
    """Sprawdza plan urlopów wg 11 reguł z sekcji `walidacje_planu`. Zwraca błędy i ostrzeżenia z datami."""
    out: list[BladPlanu] = []
    plan = profile.plan

    def blad(rid: str, txt: str, d: date | None = None, poziom: str = "blad") -> None:
        out.append(BladPlanu(id=rid, poziom=poziom, komunikat=txt, data=d))

    porod = profile.porod.data_porodu
    pdp = wyl.get("data_odniesienia_porodu")
    n = profile.porod.liczba_dzieci or 1
    mac_tyg = wymiar_macierzynskiego_tyg(n, params)
    um = plan.urlop_macierzynski
    szczegolne = bool(profile.matka.orzeczenie_niezdolnosci_do_samodzielnej_egzystencji or wyl.get("matka_hospitalizowana")
                      or profile.matka.stan == "porzucila_dziecko")
    min_tyg = P(params, "urlop.macierzynski_min_matka_szczegolne_tyg" if szczegolne else "urlop.macierzynski_min_matka_tyg")

    # mac_min_14
    if porod:
        granica = porod + timedelta(weeks=min_tyg) - timedelta(days=1)
        rez = plan.rezygnacja_z_macierzynskiego_po_14_tyg
        if rez and rez.czy and rez.data and rez.data <= granica:
            blad("mac_min_14", f"Matka może zrezygnować z urlopu macierzyńskiego najwcześniej po {min_tyg} tyg. od porodu — "
                               f"rezygnacja możliwa od {granica + timedelta(days=1)}.", granica + timedelta(days=1))
        if um and um.do and um.do < granica and profile.wnioskodawca.rola == "matka":
            blad("mac_min_14", f"Urlop macierzyński matki kończy się {um.do}, a musi trwać co najmniej do {granica} "
                               f"({min_tyg} tyg. po porodzie).", granica)
    # mac_przed_porodem
    if um and pdp:
        maks = P(params, "urlop.macierzynski_przed_porodem_max_tyg")
        najwczesniej = pdp - timedelta(weeks=maks)
        if um.od and um.od < najwczesniej:
            blad("mac_przed_porodem", f"Urlop macierzyński można zacząć najwcześniej {najwczesniej} ({maks} tyg. przed porodem).",
                 najwczesniej)
        if um.tygodnie_przed_porodem is not None and um.tygodnie_przed_porodem > maks:
            blad("mac_przed_porodem", f"Przed porodem można wykorzystać najwyżej {maks} tyg. urlopu macierzyńskiego.")
    # mac_wymiar
    if um and um.od and um.do:
        dni = (um.do - um.od).days + 1
        if dni > mac_tyg * 7:
            blad("mac_wymiar", f"Plan urlopu macierzyńskiego ma {dni} dni, a przy {n} dziecku/dzieciach wymiar to {mac_tyg} tyg. "
                               f"({mac_tyg * 7} dni) — koniec najpóźniej {um.od + timedelta(days=mac_tyg * 7 - 1)}.",
                 um.od + timedelta(days=mac_tyg * 7 - 1))
        elif dni < mac_tyg * 7 and not (plan.rezygnacja_z_macierzynskiego_po_14_tyg and plan.rezygnacja_z_macierzynskiego_po_14_tyg.czy):
            blad("mac_wymiar", f"Plan wykorzystuje {dni} z {mac_tyg * 7} dni urlopu macierzyńskiego — reszta przepadnie, "
                               "chyba że przejmie ją ojciec (rezygnacja po 14 tyg.).", um.do, "ostrzezenie")

    czesci = [c for c in plan.czesci_urlopu_rodzicielskiego or [] if c.od and c.do]
    za_zyciem = bool(wyl.get("ma_dziecko_za_zyciem"))
    pula = wymiar_rodzicielskiego_tyg(n, za_zyciem, params)
    nieprzen = P(params, "urlop.rodzicielski_nieprzenoszalny_tyg")
    # rod_nieprzenoszalne
    for rodzic in ("matka", "ojciec"):
        dni = sum((c.do - c.od).days + 1 for c in czesci if c.rodzic == rodzic)
        if dni > (pula - nieprzen) * 7:
            blad("rod_nieprzenoszalne", f"{rodzic.capitalize()} planuje {dni} dni urlopu rodzicielskiego, a może najwyżej "
                                        f"{(pula - nieprzen) * 7} dni — {nieprzen} tyg. przysługuje wyłącznie drugiemu rodzicowi.")
    if czesci and sum((c.do - c.od).days + 1 for c in czesci) > pula * 7:
        blad("rod_nieprzenoszalne", f"Łączny plan urlopu rodzicielskiego obojga rodziców przekracza pulę {pula} tyg. "
                                    "(wydłużenie przy pracy liczy się osobno).")
    # rod_max_czesci
    maks_czesci = P(params, "urlop.rodzicielski_max_czesci")
    if len(czesci) > maks_czesci:
        blad("rod_max_czesci", f"Urlop rodzicielski podzielono na {len(czesci)} części — dozwolone najwyżej {maks_czesci}.")
    # rod_termin
    ur, _ = dziecko_odniesienia(profile)
    if ur and czesci:
        koniec = date(ur.year + P(params, "urlop.rodzicielski_do_konca_roku_wiek_dziecka"), 12, 31)
        for c in czesci:
            if c.do > koniec:
                blad("rod_termin", f"Część urlopu rodzicielskiego kończy się {c.do}, a urlop trzeba wykorzystać do {koniec} "
                                   "(koniec roku, w którym dziecko kończy 6 lat).", koniec)
    # rod_praca
    maks_w = P(params, "urlop.rodzicielski_praca_max_wymiar")
    for c in czesci:
        if (c.wymiar_pracy_w_trakcie or 0) > maks_w:
            blad("rod_praca", f"W części od {c.od} zaplanowano pracę {c.wymiar_pracy_w_trakcie:g} etatu — "
                              f"łącząc urlop z pracą można pracować najwyżej {maks_w:g} etatu.", c.od)
    # ojc_dni
    oj = [c for c in plan.czesci_urlopu_ojcowskiego or [] if c.od and c.do]
    if oj:
        dni_oj = [(c.do - c.od).days + 1 for c in oj]
        limit_oj, min_cz = P(params, "urlop.ojcowski_dni"), P(params, "urlop.ojcowski_min_czesc_dni")
        if len(oj) > P(params, "urlop.ojcowski_max_czesci"):
            blad("ojc_dni", f"Urlop ojcowski można podzielić najwyżej na {P(params, 'urlop.ojcowski_max_czesci')} części.")
        if sum(dni_oj) > limit_oj:
            blad("ojc_dni", f"Plan urlopu ojcowskiego ma {sum(dni_oj)} dni — przysługuje {limit_oj} dni.")
        elif sum(dni_oj) < limit_oj:
            blad("ojc_dni", f"Plan wykorzystuje {sum(dni_oj)} z {limit_oj} dni urlopu ojcowskiego.", poziom="ostrzezenie")
        for c, d in zip(oj, dni_oj):
            if d < min_cz:
                blad("ojc_dni", f"Część urlopu ojcowskiego od {c.od} ma {d} dni — każda część musi mieć co najmniej {min_cz} dni.", c.od)
        # ojc_termin
        if ur:
            koniec_oj = dodaj_miesiace(ur, P(params, "urlop.ojcowski_max_wiek_dziecka_mies")) - timedelta(days=1)
            for c in oj:
                if c.do > koniec_oj:
                    blad("ojc_termin", f"Urlop ojcowski trzeba wykorzystać do {koniec_oj} (12 miesięcy życia dziecka).", koniec_oj)
    # uzup_jednorazowo
    uz = plan.urlop_uzupelniajacy
    if uz and (uz.od or uz.wymiar_tyg):
        wymiar, limit, _opis = oblicz_wymiar_uzupelniajacego(profile, params)
        if uz.wymiar_tyg and wymiar is not None and uz.wymiar_tyg > wymiar:
            blad("uzup_jednorazowo", f"Zaplanowano {uz.wymiar_tyg} tyg. urlopu uzupełniającego, a przysługuje {wymiar} tyg.")
        koniec_mac = um.do if um and um.do else None
        if koniec_mac is None and porod:
            start_mac = um.od if um and um.od and um.od <= porod else porod
            koniec_mac = start_mac + timedelta(weeks=mac_tyg) - timedelta(days=1)
        if uz.od and koniec_mac and uz.od != koniec_mac + timedelta(days=1):
            blad("uzup_jednorazowo", f"Urlop uzupełniający musi zacząć się bezpośrednio po urlopie macierzyńskim — "
                                     f"{koniec_mac + timedelta(days=1)}.", koniec_mac + timedelta(days=1))
    # wniosek_81_5
    wn = plan.wniosek_81_5
    if porod and wn and wn.czy:
        termin = porod + timedelta(days=P(params, "termin.wniosek_81_5_dni"))
        if wn.data_zlozenia and wn.data_zlozenia > termin:
            blad("wniosek_81_5", f"Wniosek o 81,5% złożony {wn.data_zlozenia} — termin minął {termin}; "
                                 "obowiązuje 100% za macierzyński i 70% za rodzicielski.", termin)
        elif wn.data_zlozenia is None and dzis > termin:
            blad("wniosek_81_5", f"Termin na wniosek o 81,5% minął {termin}.", termin, "ostrzezenie")
        elif wn.data_zlozenia is None:
            blad("wniosek_81_5", f"Złóż wniosek o 81,5% najpóźniej {termin}.", termin, "ostrzezenie")
    return out
