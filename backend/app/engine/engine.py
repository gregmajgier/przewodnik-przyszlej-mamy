"""Silnik uprawnień: profil -> zmienne wyliczane -> reguły JSONLogic -> kalkulator -> ryzyka -> wnioski i kalendarz.

Ocena warunków jest TRÓJWARTOŚCIOWA (prawda / fałsz / nieznane). Biblioteka json-logic-qubit traktuje
`null == false` jako prawdę, a `null in [...]` jako fałsz, więc naiwne wywołanie dawałoby fałszywe
„przysługuje”/„nie przysługuje” zamiast `brak_danych`. Dlatego:
- operatory logiczne `and` / `or` / `!` / `!!` liczymy sami (logika Kleene'a),
- każdy inny węzeł (porównanie, `in`, `if`, arytmetyka) to „liść”: jeśli którakolwiek zmienna w nim jest `null`,
  liść jest nieznany; w przeciwnym razie liczy go json-logic-qubit.
Wynik świadczenia (meta.algorytm w reguly_uprawnien.json): którykolwiek warunek fałszywy -> `nie_przysluguje`;
inaczej którykolwiek nieznany -> `brak_danych` (z listą brakujących zmiennych); inaczej `przysluguje`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from json_logic import jsonLogic

from .calculator import FUNKCJE, CalcContext, waliduj_plan_urlopow
from .derived import P, TYTULY_BEZ_CHOROBOWEGO, compute_derived_variables, dodaj_miesiace
from .kontrakt import Kontrakt, load_kontrakt
from .schemas import (
    AktywneRyzyko,
    DataGraniczna,
    EvaluationResponse,
    UserProfile,
    WymaganeWnioski,
    WymaganyWniosek,
    WynikSwiadczenia,
)

LOGICZNE = {"and", "or", "!", "!!"}
GRUPA_INSTYTUCJI = {"pracodawca": "pracodawca", "platnik": "pracodawca", "zus": "zus", "gmina": "gmina", "usc": "usc"}


# ═══════════════════════════════ ewaluacja trójwartościowa ═══════════════════════════════


def _get(ctx: dict, path: str) -> Any:
    node: Any = ctx
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
        if node is None:
            return None
    return node


def _vars(expr: Any, acc: set[str]) -> set[str]:
    if isinstance(expr, dict):
        for k, v in expr.items():
            if k == "var":
                acc.add(v if isinstance(v, str) else v[0])
            else:
                _vars(v, acc)
    elif isinstance(expr, list):
        for v in expr:
            _vars(v, acc)
    return acc


def ocen(expr: Any, ctx: dict) -> bool | None:
    """Ocena wyrażenia JSONLogic: True / False / None (nieznane, bo brakuje danych)."""
    if expr is None:
        return True
    if isinstance(expr, dict) and len(expr) == 1:
        op, args = next(iter(expr.items()))
        if op in LOGICZNE:
            args = args if isinstance(args, list) else [args]
            wyniki = [ocen(a, ctx) for a in args]
            if op == "and":
                return False if False in wyniki else (None if None in wyniki else True)
            if op == "or":
                return True if True in wyniki else (None if None in wyniki else False)
            if op == "!":
                return None if wyniki[0] is None else not wyniki[0]
            return wyniki[0]
    if any(_get(ctx, v) is None for v in _vars(expr, set())):
        return None
    return bool(jsonLogic(expr, ctx))


def brakujace(expr: Any, ctx: dict, zmienne: list[str]) -> list[str]:
    """Zmienne (bez parametrów) z wartością null w nierozstrzygniętym warunku."""
    nazwy = set(zmienne) | _vars(expr, set())
    return sorted(v for v in nazwy if not v.startswith("param.") and _get(ctx, v) is None)


# ═══════════════════════════════ kontekst ═══════════════════════════════


def zbuduj_kontekst(profile: UserProfile, wyl: dict, params: dict) -> dict:
    ctx = profile.kontekst()
    ctx["wyl"] = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in wyl.items()}
    ctx["param"] = params
    return ctx


def profil_drugiego_rodzica(profile: UserProfile) -> UserProfile | None:
    """Profil matki/ojca zbudowany z `drugi_rodzic` (wspólne: ciąża, poród, dzieci, rodzina) — żeby pokazać
    świadczenia drugiego rodzica, np. SR-7 dla nieubezpieczonej matki, gdy wnioskodawcą jest ojciec."""
    dr = profile.drugi_rodzic
    tytul = dr.ubezpieczenie.tytul if dr.ubezpieczenie and dr.ubezpieczenie.tytul else dr.tytul_ubezpieczenia
    if tytul is None or profile.wnioskodawca.rola not in ("matka", "ojciec"):
        return None
    rola = "ojciec" if profile.wnioskodawca.rola == "matka" else "matka"
    dane = dr.dane
    adres = profile.wnioskodawca.adres_zamieszkania
    bez = tytul in TYTULY_BEZ_CHOROBOWEGO
    plan = profile.plan.model_dump(mode="json", exclude_none=True)
    if rola != "matka":
        plan.pop("wniosek_81_5", None)
    data = {
        "wnioskodawca": {
            "etap": profile.wnioskodawca.etap, "rola": rola,
            "imie": dane.imie if dane else None, "nazwisko": dane.nazwisko if dane else None,
            "pesel": dane.pesel if dane else None,
            "obywatelstwo": dane.obywatelstwo if dane else None,
            "adres_zamieszkania": adres.model_dump() if adres and profile.rodzina.wspolne_gospodarstwo_domowe else None,
        },
        "ubezpieczenie": (
            {**dr.ubezpieczenie.model_dump(mode="json", exclude_none=True), "tytul": tytul}
            if dr.ubezpieczenie is not None
            else {"tytul": tytul, "chorobowe": "brak" if bez else None}
        ),
        "ciaza": profile.ciaza.model_dump(), "porod": profile.porod.model_dump(),
        "dzieci": [d.model_dump() for d in profile.dzieci] if profile.dzieci is not None else None,
        "rodzina": profile.rodzina.model_dump(),
        "matka": profile.matka.model_dump(),
        "plan": plan,
        "drugi_rodzic": {"tytul_ubezpieczenia": profile.ubezpieczenie.tytul,
                         "aktywny_zawodowo": None if profile.ubezpieczenie.tytul is None
                         else profile.ubezpieczenie.tytul in ("umowa_o_prace", "umowa_zlecenia", "jdg", "wspolpraca_jdg")},
    }
    if rola == "matka" and bez:
        data["matka"]["ubezpieczona_w_dniu_porodu"] = False
    return UserProfile.model_validate(data)


# ═══════════════════════════════ ocena świadczeń ═══════════════════════════════


def ocen_swiadczenia(profile: UserProfile, wyl: dict, kontrakt, dzis: date) -> list[WynikSwiadczenia]:
    ctx = zbuduj_kontekst(profile, wyl, kontrakt.params)
    etap = profile.wnioskodawca.etap
    wyniki = []
    for rule in kontrakt.reguly["swiadczenia"]:
        if etap is not None and etap not in rule["etapy"]:
            continue
        przyczyny, niespelnione, braki = [], [], set()
        nieznane = False
        for war in rule["warunki"]:
            v = ocen(war["wyrazenie"], ctx)
            if v is False:
                przyczyny.append(war["przyczyna_braku_uprawnien"])
                niespelnione.append(war["id"])
            elif v is None:
                nieznane = True
                braki.update(brakujace(war["wyrazenie"], ctx, war["zmienne"]))
        status = "nie_przysluguje" if niespelnione else ("brak_danych" if nieznane else "przysluguje")
        wynik = WynikSwiadczenia(
            id=rule["id"], nazwa=rule["nazwa"], typ=rule["typ"], instytucja=rule["instytucja"], status=status,
            przyczyny=przyczyny, niespelnione_warunki=niespelnione,
            brakujace_zmienne=sorted(braki) if status == "brak_danych" else [],
            informacje=[i["komunikat"] for i in rule.get("informacje", []) if ocen(i["warunek"], ctx) is True],
            do_weryfikacji=bool(rule.get("do_weryfikacji")), sciezka_ui=rule.get("sciezka_ui"),
        )
        if status == "przysluguje":
            fn = FUNKCJE[rule["wynik"]["funkcja"]]
            wynik.wyliczenie = fn(CalcContext(profile, wyl, kontrakt.params, dzis, rule))
            wynik.wnioski = [w["kod"] for w in rule.get("wnioski", []) if ocen(w["warunek"], ctx) is True]
        wyniki.append(wynik)
    return wyniki


def ocen_ryzyka(profile: UserProfile, wyl: dict, kontrakt) -> list[AktywneRyzyko]:
    ctx = zbuduj_kontekst(profile, wyl, kontrakt.params)
    return [
        AktywneRyzyko(id=r["id"], nazwa=r["nazwa"], poziom=r["poziom"], komunikat=r["komunikat"],
                      dotyczy=r.get("dotyczy", []), wnioski=r.get("wnioski", []), podstawa=r.get("podstawa"))
        for r in kontrakt.reguly["ryzyka"] if ocen(r["warunek"], ctx) is True
    ]


# ═══════════════════════════════ wnioski i kalendarz ═══════════════════════════════


def _termin(t: dict, profile: UserProfile, wyl: dict, params: dict, kod: str = "") -> date | None:
    """Data z `terminy[]` katalogu (param + odniesienie + kierunek)."""
    if not t.get("param") or t.get("kierunek") == "razem":
        return None
    ile = P(params, t["param"])
    porod = profile.porod.data_porodu
    odn = t.get("odniesienie")
    if odn in ("data_urodzenia", "wystawienie_karty_urodzenia"):
        baza = porod
    elif odn == "data_zgonu":
        baza = porod if profile.porod.stan_dziecka == "martwe" else profile.porod.data_zgonu_dziecka
    elif odn == "data_porodu":
        baza = porod
    elif odn == "rozpoczecie_urlopu":
        if kod == "URLOP-OJC":
            czesci = [c.od for c in profile.plan.czesci_urlopu_ojcowskiego or [] if c.od]
        else:
            rola = profile.wnioskodawca.rola
            czesci = [c.od for c in profile.plan.czesci_urlopu_rodzicielskiego or [] if c.od and c.rodzic in (None, rola)]
        baza = min(czesci) if czesci else None
    elif odn == "koniec_urlopu_macierzynskiego":
        um = profile.plan.urlop_macierzynski
        baza = um.do if um and um.do else None
    elif odn == "data_przyjecia":
        prz = [d.przyjete_na_wychowanie.data_przyjecia for d in profile.dzieci or []
               if d.przyjete_na_wychowanie and d.przyjete_na_wychowanie.data_przyjecia]
        baza = max(prz) if prz else None
    else:
        baza = None
    if baza is None:
        return None
    if t.get("jednostka") == "miesiac":
        d = dodaj_miesiace(baza, ile if t["kierunek"] == "po" else -ile)
        return d - timedelta(days=1) if t["kierunek"] == "po" else d
    return baza + timedelta(days=ile if t["kierunek"] == "po" else -ile)


def zbuduj_wnioski(wyniki: list[WynikSwiadczenia], ryzyka: list[AktywneRyzyko], profile: UserProfile, wyl: dict,
                   kontrakt, dla: str = "wnioskodawca") -> list[WymaganyWniosek]:
    katalog = {w["kod"]: w for w in kontrakt.katalog["wnioski"]}
    zlozone = {w.kod for w in profile.wnioski_zlozone or [] if w.kod}
    zebrane: dict[str, WymaganyWniosek] = {}
    zrodla = [(w.wnioski, w.id, None) for w in wyniki if w.status == "przysluguje"] + [(r.wnioski, None, r.id) for r in ryzyka]
    for kody, sw_id, r_id in zrodla:
        for kod in kody:
            k = katalog[kod]
            typ = k.get("instytucja_typ")
            if typ == "zus_lub_platnik":
                grupa = "pracodawca" if wyl.get("platnik_wyplaca_zasilki") else "zus"
            else:
                grupa = GRUPA_INSTYTUCJI.get(typ, "zus")
            if kod not in zebrane:
                terminy = [(t, _termin(t, profile, wyl, kontrakt.params, kod)) for t in k.get("terminy", [])]
                pierwszy = next(((t, d) for t, d in terminy if d), (None, None))
                zebrane[kod] = WymaganyWniosek(
                    kod=kod, nazwa=k["nazwa"], grupa=grupa, instytucja=k.get("instytucja", ""),
                    tryb_aplikacji=k.get("tryb_aplikacji"), tylko_elektronicznie=bool(k.get("tylko_elektronicznie")),
                    wysylka=k.get("wysylka", []), termin=pierwszy[1],
                    termin_opis=(pierwszy[0] or {}).get("opis") or next((t["opis"] for t in k.get("terminy", [])), None),
                    zlozony=kod in zlozone, dla=dla,
                )
            ww = zebrane[kod]
            if sw_id and sw_id not in ww.swiadczenia:
                ww.swiadczenia.append(sw_id)
            if r_id and r_id not in ww.ryzyka:
                ww.ryzyka.append(r_id)
    return list(zebrane.values())


def zbuduj_kalendarz(wnioski: list[WymaganyWniosek], wyniki: list[WynikSwiadczenia], profile: UserProfile, wyl: dict,
                     params: dict, dzis: date) -> list[DataGraniczna]:
    out: list[DataGraniczna] = []

    def dodaj(d: date | None, rodzaj: str, opis: str, kod: str | None = None, sw: str | None = None) -> None:
        if d is not None:
            out.append(DataGraniczna(data=d, rodzaj=rodzaj, opis=opis, kod_wniosku=kod, swiadczenie=sw, po_terminie=d < dzis))

    for w in wnioski:
        if w.termin and not w.zlozony:
            rodzaj = "wygasniecie_prawa" if w.kod == "Z-12" else "zlozenie_wniosku"
            dodaj(w.termin, rodzaj, f"{w.nazwa}: {w.termin_opis or 'termin'}", w.kod, (w.swiadczenia or [None])[0])
    porod = profile.porod.data_porodu
    ids = {w.id for w in wyniki if w.status == "przysluguje"}
    if porod and "ZASILEK_MACIERZYNSKI_MATKA" in ids and not (profile.plan.wniosek_81_5 and profile.plan.wniosek_81_5.data_zlozenia):
        dodaj(porod + timedelta(days=P(params, "termin.wniosek_81_5_dni")), "zlozenie_wniosku",
              "Ostatni dzień na wniosek o 81,5% zasiłku za cały okres", sw="ZASILEK_MACIERZYNSKI_MATKA")
    if porod and "ZASILEK_URLOP_OJCOWSKI" in ids:
        dodaj(dodaj_miesiace(porod, P(params, "urlop.ojcowski_max_wiek_dziecka_mies")) - timedelta(days=1), "wygasniecie_prawa",
              "Ostatni dzień urlopu ojcowskiego (12 miesięcy życia dziecka)", sw="ZASILEK_URLOP_OJCOWSKI")
    if porod and "ZASILEK_URLOP_RODZICIELSKI" in ids:
        dodaj(date(porod.year + P(params, "urlop.rodzicielski_do_konca_roku_wiek_dziecka"), 12, 31), "wygasniecie_prawa",
              "Koniec prawa do urlopu rodzicielskiego (rok, w którym dziecko kończy 6 lat)", sw="ZASILEK_URLOP_RODZICIELSKI")
    for c in profile.plan.czesci_urlopu_rodzicielskiego or []:
        if c.od and c.rodzic in (None, profile.wnioskodawca.rola):
            dodaj(c.od - timedelta(days=P(params, "termin.urlop_rodzicielski_przed_dni")), "zlozenie_wniosku",
                  f"Wniosek o część urlopu rodzicielskiego ({c.rodzic or 'rodzic'}) od {c.od} — 21 dni wcześniej", "URLOP-ROD")
            dodaj(c.od, "plan", f"Start urlopu rodzicielskiego ({c.rodzic or 'rodzic'})")
    for c in profile.plan.czesci_urlopu_ojcowskiego or []:
        if c.od:
            dodaj(c.od - timedelta(days=P(params, "termin.urlop_ojcowski_przed_dni")), "zlozenie_wniosku",
                  f"Wniosek o urlop ojcowski od {c.od} — 7 dni wcześniej", "URLOP-OJC")
    um = profile.plan.urlop_macierzynski
    if um and um.od:
        dodaj(um.od, "plan", "Start urlopu macierzyńskiego")
    if um and um.do:
        dodaj(um.do, "plan", "Koniec urlopu macierzyńskiego")
    if wyl.get("umowa_przedluzona_do_porodu"):
        dodaj(profile.ubezpieczenie.data_konca_umowy, "ostrzezenie",
              "Umowa terminowa nie wygasa tego dnia — przedłuża się do dnia porodu (art. 177 § 3 KP)")
    for w in wyniki:
        termin = w.wyliczenie.szczegoly.get("termin_wniosku") if w.wyliczenie else None
        if termin and not any(d.swiadczenie == w.id and d.data.isoformat() == termin for d in out):
            dodaj(date.fromisoformat(w.wyliczenie.szczegoly["termin_wniosku"]), "wygasniecie_prawa",
                  f"{w.nazwa}: ostatni dzień na wniosek", sw=w.id)
    unikalne: dict[tuple, DataGraniczna] = {}
    for d in out:  # ten sam dzień i ten sam wniosek/świadczenie = jeden wpis (pierwszy, z katalogu)
        unikalne.setdefault((d.data, d.kod_wniosku or d.swiadczenie or d.opis), d)
    return sorted(unikalne.values(), key=lambda d: (d.data, d.opis))


# ═══════════════════════════════ punkt wejścia ═══════════════════════════════


def evaluate_user_profile(profile_data: dict | UserProfile, rules_json: dict | None = None,
                          catalog_json: dict | None = None, dzis: date | None = None) -> EvaluationResponse:
    """Główna funkcja silnika. `rules_json` / `catalog_json` domyślnie z app/data (można podać inne, np. z panelu admina)."""
    base = load_kontrakt()
    kontrakt = Kontrakt(rules_json or base.reguly, base.zmienne, catalog_json or base.katalog)
    dzis = dzis or date.today()
    profile = profile_data if isinstance(profile_data, UserProfile) else UserProfile.model_validate(profile_data)

    wyl = compute_derived_variables(profile, kontrakt.params, dzis)
    wyniki = ocen_swiadczenia(profile, wyl, kontrakt, dzis)
    ryzyka = ocen_ryzyka(profile, wyl, kontrakt)
    lista = zbuduj_wnioski(wyniki, ryzyka, profile, wyl, kontrakt)

    drugi: list[WynikSwiadczenia] = []
    partner = profil_drugiego_rodzica(profile)
    if partner is not None:
        wyl_p = compute_derived_variables(partner, kontrakt.params, dzis)
        drugi = [w for w in ocen_swiadczenia(partner, wyl_p, kontrakt, dzis)
                 if w.status in ("przysluguje", "brak_danych")
                 and w.typ in ("swiadczenie_gminne", "zasilek_zus")]
        lista += [w for w in zbuduj_wnioski(drugi, [], partner, wyl_p, kontrakt, dla="drugi_rodzic")
                  if w.kod not in {x.kod for x in lista}]

    grupy = WymaganeWnioski()
    for w in lista:
        getattr(grupy, w.grupa).append(w)
    return EvaluationResponse(
        data_oceny=dzis, wersja_kontraktu=kontrakt.wersja, swiadczenia=wyniki, swiadczenia_drugiego_rodzica=drugi,
        ryzyka=ryzyka, wnioski=grupy, kalendarz=zbuduj_kalendarz(lista, wyniki, profile, wyl, kontrakt.params, dzis),
        walidacja_planu=waliduj_plan_urlopow(profile, wyl, kontrakt.params, dzis),
        brakujace_zmienne=sorted({v for w in wyniki for v in w.brakujace_zmienne}),
        wyl={k: (v.isoformat() if isinstance(v, date) else v) for k, v in wyl.items()},
    )
