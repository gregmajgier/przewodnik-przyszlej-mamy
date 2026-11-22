"""Silnik end-to-end: 5 person z app/data/persony_mock.json, profil częściowo pusty, walidacja planu, formularz, API."""

import copy
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.engine.engine import evaluate_user_profile, ocen
from app.engine.kontrakt import DATA, load_kontrakt
from app.engine.schemas import Porod, Ubezpieczenie

DZIS = date(2026, 11, 21)
PERSONY = {p["id"]: p["profil"] for p in json.loads((DATA / "persony_mock.json").read_text(encoding="utf-8"))["persony"]}


def ocena(profil, dzis=DZIS):
    return evaluate_user_profile(profil, dzis=dzis)


def sw(r, sid):
    return next(w for w in r.swiadczenia if w.id == sid)


def kody(r, grupa):
    return [w.kod for w in getattr(r.wnioski, grupa)]


# ── Persona 1: mama UoP, 81,5%, 9 tyg. dla ojca ────────────────────────────────

@pytest.fixture(scope="module")
def p1():
    return ocena(PERSONY["P1_MAMA_UOP_81_5"])


def test_p1_zasilek_macierzynski_81_5(p1):
    m = sw(p1, "ZASILEK_MACIERZYNSKI_MATKA")
    assert m.status == "przysluguje"
    w = m.wyliczenie
    assert w.podstawa_wymiaru == 6040.30            # 7000 × (1 − 13,71%)
    assert w.kwota_miesieczna == 4922.84            # × 81,5%
    assert w.szczegoly["wybrany_wariant"] == "81,5%"
    assert (w.okresy[0].od, w.okresy[0].do, w.okresy[0].dni) == (date(2026, 11, 10), date(2027, 3, 29), 140)
    assert w.kwota_laczna == 22972.60               # 140 dni × 164,09 zł


def test_p1_rodzicielski_matki_32_tyg_i_plan_poprawny(p1):
    r = sw(p1, "ZASILEK_URLOP_RODZICIELSKI").wyliczenie
    assert r.okresy[0].dni == 224 and r.okresy[0].procent == 81.5
    assert p1.walidacja_planu == []


def test_p1_wnioski_u_pracodawcy_i_status_zlozenia(p1):
    assert {"URLOP-MAC-ROD", "URLOP-ROD"} <= set(kody(p1, "pracodawca"))
    mac = next(w for w in p1.wnioski.pracodawca if w.kod == "URLOP-MAC-ROD")
    assert mac.zlozony is True
    assert "800PLUS" in kody(p1, "zus")
    assert {"ZGLOSZENIE-URODZENIA", "ODPIS-AKTU"} <= set(kody(p1, "usc"))
    assert sw(p1, "BECIKOWE").status == "nie_przysluguje"  # dochód 4166,67 zł/os. > 1922 zł


def test_p1_plan_bledny_przy_10_tyg_dla_ojca():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["plan"]["czesci_urlopu_rodzicielskiego"][0]["do"] = "2027-11-15"  # matka sięga po tydzień ojca
    bledy = {(b.id, b.poziom) for b in ocena(profil).walidacja_planu}
    assert ("rod_nieprzenoszalne", "blad") in bledy


def test_plan_drugiego_rodzica_uwzglednia_prace_i_nie_stosuje_81_5_do_ojca():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["plan"]["czesci_urlopu_rodzicielskiego"][1]["wymiar_pracy_w_trakcie"] = 0.5
    profil["drugi_rodzic"]["ubezpieczenie"] = {
        "chorobowe": "obowiazkowe",
        "data_objecia_chorobowym": "2020-01-01",
        "przychody_12_miesiecy": [
            {"rok": 2026, "miesiac": m, "podstawa_wymiaru_skladek": 5000} for m in range(1, 13)
        ],
    }

    wynik = ocena(profil)
    rodzicielski = next(
        w for w in wynik.swiadczenia_drugiego_rodzica if w.id == "ZASILEK_URLOP_RODZICIELSKI"
    ).wyliczenie
    assert [o.dni for o in rodzicielski.okresy] == [63, 31]
    assert [o.procent for o in rodzicielski.okresy] == [70.0, 70.0]
    assert rodzicielski.okresy[0].stawka_dzienna < rodzicielski.okresy[1].stawka_dzienna


def test_adopcja_uwzglednia_prace_podczas_urlopu_rodzicielskiego():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["wnioskodawca"].update(etap="adopcja_zastepcza", rola="przysposabiajacy")
    profil["dzieci"][0]["przyjete_na_wychowanie"] = {
        "rodzaj": "przysposobienie",
        "data_przyjecia": "2026-11-10",
    }
    profil["porod"] = {"data_porodu": None, "stan_dziecka": None, "liczba_dzieci": None}
    profil["plan"] = {
        "czesci_urlopu_rodzicielskiego": [
            {"rodzic": None, "od": "2027-03-30", "do": "2027-05-31", "wymiar_pracy_w_trakcie": 0.5}
        ]
    }

    rodzicielski = sw(ocena(profil), "ZASILEK_ADOPCJA_ZASTEPCZA").wyliczenie
    okresy = [o for o in rodzicielski.okresy if o.nazwa.startswith("Urlop rodzicielski")]
    assert [o.dni for o in okresy] == [63, 224]
    assert [o.procent for o in okresy] == [70.0, 70.0]
    wydluzenie = next(o for o in rodzicielski.okresy if o.nazwa.startswith("Wydłużenie urlopu"))
    assert wydluzenie.dni == 31 and wydluzenie.procent == 70.0
    assert okresy[0].stawka_dzienna < okresy[1].stawka_dzienna
    assert rodzicielski.szczegoly["rodzicielski_wydluzenie_dni"] == 31


def test_ulga_na_start_nie_daje_dobrowolnego_chorobowego_ani_blednego_ryzyka():
    assert Ubezpieczenie.model_validate({"tytul": "ulga_na_start"}).chorobowe == "brak"
    with pytest.raises(ValidationError):
        Ubezpieczenie.model_validate({"tytul": "ulga_na_start", "chorobowe": "dobrowolne"})

    profil = copy.deepcopy(PERSONY["P2_JDG_DLUG"])
    profil["ubezpieczenie"].update(tytul="ulga_na_start", chorobowe="brak")
    wynik = ocena(profil)
    assert "R_BRAK_DOBROWOLNEGO" not in {r.id for r in wynik.ryzyka}


def test_swiadczenie_rodzicielskie_nie_jest_dostepne_w_ciazy():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["wnioskodawca"]["etap"] = "w_ciazy"
    profil["ciaza"]["w_ciazy"] = True
    profil["porod"].update(data_porodu=None, stan_dziecka=None)

    assert "SWIADCZENIE_RODZICIELSKIE" not in {w.id for w in ocena(profil).swiadczenia}


def test_tydzien_ciazy_w_pierwszym_trymestrze_jest_poprawny():
    assert Porod(tydzien_ciazy=12).tydzien_ciazy == 12


# ── Persona 2: JDG, zadłużenie, podwyższona podstawa ──────────────────────────

@pytest.fixture(scope="module")
def p2():
    return ocena(PERSONY["P2_JDG_DLUG"])


def test_p2_radar_ryzyk(p2):
    ids = {r.id for r in p2.ryzyka}
    assert {"R_ZADLUZENIE_JDG", "R_ZMIANA_PODSTAWY", "R_BRAK_OCHRONY"} <= ids
    assert next(r for r in p2.ryzyka if r.id == "R_ZADLUZENIE_JDG").wnioski == ["POG"]


def test_p2_zam_i_pog_bezposrednio_do_zus(p2):
    assert {"ZAM", "ZAS-53", "POG"} <= set(kody(p2, "zus"))
    assert kody(p2, "pracodawca") == []
    assert p2.wyl["platnik_wyplaca_zasilki"] is False


def test_p2_podstawa_jdg_i_chorobowy_100_bez_wynagrodzenia_od_pracodawcy(p2):
    ch = sw(p2, "ZASILEK_CHOROBOWY_CIAZA").wyliczenie
    assert ch.podstawa_wymiaru == 6321.61            # śr. (6 × 5652 + 6 × 9000) × 0,8629
    assert [o.wyplaca for o in ch.okresy] == ["ZUS"]
    assert ch.szczegoly["dni_pracodawca"] == 0 and ch.szczegoly["dni_zasilku"] == 29


# ── Persona 3: ojciec UoP, matka studentka ────────────────────────────────────

@pytest.fixture(scope="module")
def p3():
    return ocena(PERSONY["P3_OJCIEC_MATKA_STUDENTKA"])


def test_p3_rodzicielski_i_ojcowski_dla_ojca(p3):
    rod = sw(p3, "ZASILEK_URLOP_RODZICIELSKI")
    assert rod.status == "przysluguje" and rod.wyliczenie.okresy[0].procent == 70.0
    assert sw(p3, "ZASILEK_URLOP_OJCOWSKI").wyliczenie.kwota_laczna == 2818.76  # 14 × 201,34 zł
    assert {"URLOP-ROD", "URLOP-OJC"} <= set(kody(p3, "pracodawca"))


def test_p3_sr7_dla_matki_studentki(p3):
    assert sw(p3, "SWIADCZENIE_RODZICIELSKIE").status == "nie_przysluguje"  # ojciec ma prawo do zasiłku
    assert [w.id for w in p3.swiadczenia_drugiego_rodzica] == ["SWIADCZENIE_RODZICIELSKIE"]
    sr7 = next(w for w in p3.wnioski.gmina if w.kod == "SR-7")
    assert sr7.dla == "drugi_rodzic" and sr7.termin == date(2027, 1, 19)


def test_p3_ojciec_nie_przejmuje_macierzynskiego_bez_przeslanek(p3):
    assert sw(p3, "ZASILEK_MACIERZYNSKI_OJCIEC_PRZEJECIE").status == "nie_przysluguje"


def test_szczegolowe_ubezpieczenie_drugiego_rodzica_pokazuje_jego_kwote():
    profil = copy.deepcopy(PERSONY["P3_OJCIEC_MATKA_STUDENTKA"])
    profil["drugi_rodzic"]["tytul_ubezpieczenia"] = "umowa_o_prace"
    profil["drugi_rodzic"]["ubezpieczenie"] = {
        "chorobowe": "obowiazkowe",
        "data_objecia_chorobowym": "2020-01-01",
        "przychody_12_miesiecy": [
            {"rok": 2026, "miesiac": m, "podstawa_wymiaru_skladek": 5000} for m in range(1, 13)
        ],
    }

    wynik = ocena(profil)
    macierzynski = next(w for w in wynik.swiadczenia_drugiego_rodzica if w.id == "ZASILEK_MACIERZYNSKI_MATKA")
    assert macierzynski.wyliczenie.kwota_miesieczna == 4314.5
    assert any(w.id == "ZASILEK_URLOP_RODZICIELSKI" for w in wynik.swiadczenia_drugiego_rodzica)


def test_brak_podstawy_drugiego_rodzica_nie_generuje_szacunku_kwoty():
    profil = copy.deepcopy(PERSONY["P3_OJCIEC_MATKA_STUDENTKA"])
    profil["drugi_rodzic"]["tytul_ubezpieczenia"] = "umowa_o_prace"
    profil["drugi_rodzic"]["ubezpieczenie"] = {
        "chorobowe": "obowiazkowe",
        "data_objecia_chorobowym": "2020-01-01",
    }

    wynik = ocena(profil)
    macierzynski = next(w for w in wynik.swiadczenia_drugiego_rodzica if w.id == "ZASILEK_MACIERZYNSKI_MATKA")
    assert macierzynski.status == "przysluguje"
    assert macierzynski.wyliczenie.kwota_miesieczna is None
    assert macierzynski.wyliczenie.kwota_laczna is None


def test_ojciec_przejmuje_gdy_matka_bez_ubezpieczenia_podjela_prace():
    profil = copy.deepcopy(PERSONY["P3_OJCIEC_MATKA_STUDENTKA"])
    profil["matka"]["podjela_prace_min_pol_etatu"] = True
    assert sw(ocena(profil), "ZASILEK_MACIERZYNSKI_OJCIEC_PRZEJECIE").status == "przysluguje"


# ── Persona 4: wcześniak 26 tyg., 850 g ───────────────────────────────────────

@pytest.fixture(scope="module")
def p4():
    return ocena(PERSONY["P4_WCZESNIAK_26_TYG"])


def test_p4_uzupelniajacy_15_tygodni_po_macierzynskim(p4):
    assert p4.wyl["uzupelniajacy_wymiar_tyg"] == 15
    u = sw(p4, "ZASILEK_URLOP_UZUPELNIAJACY")
    assert u.status == "przysluguje"
    o = u.wyliczenie.okresy[0]
    assert (o.od, o.dni, o.procent) == (date(2027, 1, 19), 105, 100.0)
    assert "URLOP-UZUP" in kody(p4, "pracodawca")
    assert p4.walidacja_planu == []


def test_p4_rodzicielski_zaczyna_sie_po_uzupelniajacym(p4):
    assert sw(p4, "ZASILEK_URLOP_RODZICIELSKI").wyliczenie.okresy[0].od == date(2027, 5, 4)


# ── Persona 5: /jaskolka — martwe urodzenie ───────────────────────────────────

@pytest.fixture(scope="module")
def p5():
    return ocena(PERSONY["P5_JASKOLKA_MARTWE_URODZENIE"])


def test_p5_8_tygodni_zasilku_macierzynskiego(p5):
    m = sw(p5, "ZASILEK_MACIERZYNSKI_MARTWE_URODZENIE")
    assert m.status == "przysluguje" and m.sciezka_ui == "/jaskolka"
    o = m.wyliczenie.okresy[0]
    assert (o.od, o.do, o.dni, o.procent) == (date(2026, 11, 5), date(2026, 12, 30), 56, 100.0)


def test_p5_zasilek_pogrzebowy_7000_z12(p5):
    p = sw(p5, "ZASILEK_POGRZEBOWY")
    assert p.status == "przysluguje" and p.wyliczenie.kwota_jednorazowa == 7000.0
    z12 = next(w for w in p5.wnioski.zus if w.kod == "Z-12")
    assert z12.termin == date(2027, 11, 4)


def test_p5_odrzuca_becikowe_800plus_i_zwykly_macierzynski(p5):
    assert sw(p5, "BECIKOWE").status == "nie_przysluguje"
    assert sw(p5, "ZASILEK_800PLUS").status == "nie_przysluguje"
    assert sw(p5, "ZASILEK_MACIERZYNSKI_MATKA").status == "nie_przysluguje"
    assert sw(p5, "ZASILEK_URLOP_RODZICIELSKI").status == "nie_przysluguje"
    assert "SR-7" not in kody(p5, "gmina")


# ── profil częściowo pusty ────────────────────────────────────────────────────

def test_profil_czesciowo_pusty_brak_danych():
    r = ocena({"wnioskodawca": {"etap": "w_ciazy", "rola": "matka"}, "ciaza": {"w_ciazy": True}})
    ch = sw(r, "ZASILEK_CHOROBOWY_CIAZA")
    assert ch.status == "brak_danych"
    assert {"wyl.ma_ezla_kod_b", "wyl.tytul_aktywny_lub_w_oknie", "zdrowie.okres_zasilkowy_wykorzystany_dni"} <= set(ch.brakujace_zmienne)
    mac = sw(r, "ZASILEK_MACIERZYNSKI_MATKA")
    assert mac.status == "brak_danych" and "ubezpieczenie.chorobowe" in mac.brakujace_zmienne
    assert mac.wyliczenie is None and mac.wnioski == []
    assert r.ryzyka == []                                # przy braku danych ryzyk nie pokazujemy
    assert all(w.status != "przysluguje" for w in r.swiadczenia if w.typ == "zasilek_zus")
    assert "ubezpieczenie.chorobowe" in r.brakujace_zmienne


def test_null_nie_jest_rowny_false():
    """json-logic-qubit: null == false → true. Silnik musi dać brak_danych, a nie „przysługuje”."""
    ctx = {"ubezpieczenie": {"zapewniono_inne_zatrudnienie": None}}
    assert ocen({"==": [{"var": "ubezpieczenie.zapewniono_inne_zatrudnienie"}, False]}, ctx) is None
    r = ocena({"wnioskodawca": {"etap": "w_ciazy"}, "ciaza": {"w_ciazy": True},
               "ubezpieczenie": {"tytul": "umowa_o_prace", "umowa_rozwiazana_w_ciazy": True, "przyczyna_rozwiazania_umowy": "likwidacja"}})
    w = sw(r, "ZASILEK_W_WYSOKOSCI_MACIERZYNSKIEGO")
    assert w.status == "brak_danych" and w.brakujace_zmienne == ["ubezpieczenie.zapewniono_inne_zatrudnienie"]


def test_or_z_brakami_rozstrzyga_sie_gdy_jedna_galaz_prawdziwa():
    ctx = {"wnioskodawca": {"obywatelstwo": "PL", "legalny_pobyt_w_polsce": None}}
    expr = {"or": [{"==": [{"var": "wnioskodawca.obywatelstwo"}, "PL"]}, {"==": [{"var": "wnioskodawca.legalny_pobyt_w_polsce"}, True]}]}
    assert ocen(expr, ctx) is True


def test_pusty_profil_nie_rzuca_wyjatkow():
    r = ocena({})
    assert len(r.swiadczenia) == len(load_kontrakt().reguly["swiadczenia"])
    assert r.wersja_kontraktu == "1.1"


def test_etap_filtruje_swiadczenia():
    r = ocena({"wnioskodawca": {"etap": "planuje"}})
    assert {w.id for w in r.swiadczenia} == {"KARTA_DUZEJ_RODZINY", "OCHRONA_STOSUNKU_PRACY"}


def test_podwyzszenie_do_1000_zl():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["ubezpieczenie"].update(wymiar_etatu=0.25, przychody_12_miesiecy=[
        {**m, "podstawa_wymiaru_skladek": 1300} for m in profil["ubezpieczenie"]["przychody_12_miesiecy"]])
    m = sw(ocena(profil), "ZASILEK_MACIERZYNSKI_MATKA").wyliczenie
    assert m.podstawa_wymiaru == 1121.77 and m.kwota_miesieczna == 1000.0  # 1121,77 × 81,5% = 914,24 → 1000 zł
    assert any("art. 31 ust. 3a" in u for u in m.uwagi)


def test_lacznie_z_praca_wydluza_urlop():
    profil = copy.deepcopy(PERSONY["P1_MAMA_UOP_81_5"])
    profil["plan"]["czesci_urlopu_rodzicielskiego"][0]["wymiar_pracy_w_trakcie"] = 0.5
    r = sw(ocena(profil), "ZASILEK_URLOP_RODZICIELSKI").wyliczenie
    assert [o.dni for o in r.okresy] == [224, 112]                 # wydłużenie = 224 × 0,5 (art. 182¹f KP)
    assert r.okresy[0].stawka_dzienna == pytest.approx(82.05, abs=0.01)  # 4922,84 × 0,5 / 30


# ── formularz_ui.json i API ───────────────────────────────────────────────────

def test_formularz_aktualny_i_kompletny():
    gen = Path(__file__).resolve().parents[2] / "scripts" / "kontrakt" / "generuj_formularz.py"
    assert subprocess.run([sys.executable, str(gen), "--check"]).returncode == 0, "uruchom generuj_formularz.py"
    f = json.loads((DATA / "formularz_ui.json").read_text(encoding="utf-8"))
    k = load_kontrakt()
    wejscia = {z["klucz"] for z in k.zmienne["zmienne"] if not z["klucz"].startswith("wyl.")}
    assert {p["klucz"] for p in f["pytania"]} == wejscia
    assert {r["id"] for r in f["ranking_swiadczen"]} == {s["id"] for s in k.reguly["swiadczenia"]}
    kroki = set(f["meta"]["kroki"])
    for p in f["pytania"]:
        assert p["krok"] in kroki and p["pytanie"] and p["podpowiedz"]
        if p["show_if"] is not None:
            ocen(p["show_if"], {})  # poprawny JSONLogic
    rozw = next(p for p in f["pytania"] if p["klucz"] == "ubezpieczenie.przyczyna_rozwiazania_umowy")
    assert rozw["show_if"] == {"==": [{"var": "ubezpieczenie.umowa_rozwiazana_w_ciazy"}, True]}


def test_api_ocena_i_endpointy_kontraktu():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.post("/api/silnik/ocena?data_oceny=2026-11-21", json=PERSONY["P4_WCZESNIAK_26_TYG"])
    assert r.status_code == 200
    body = r.json()
    assert next(s for s in body["swiadczenia"] if s["id"] == "ZASILEK_URLOP_UZUPELNIAJACY")["status"] == "przysluguje"
    assert c.post("/api/silnik/ocena", json={"tytul_ubezpieczenia": "umowa_o_prace"}).status_code == 422  # klucz v0.1
    assert c.get("/api/silnik/formularz").status_code == 200
    assert c.get("/api/zmienne").json()[0]["klucz"] == "wnioskodawca.etap"
    assert "drzewo" in c.get("/api/parametry").json()
    assert c.get("/api/wnioski/Z-15/pdf").headers["content-type"] == "application/pdf"


def test_api_ocena_odrzuca_zakresy_dat_bez_limitu():
    """Silnik rozwija e-ZLA i hospitalizację do dni — absurdalny zakres ma dać 422, a nie miliony dni."""
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    ogromny = {"od": "0001-01-01", "do": "9999-12-31"}
    assert c.post("/api/silnik/ocena", json={"zdrowie": {"ezla": [ogromny]}}).status_code == 422
    assert c.post("/api/silnik/ocena", json={"matka": {"hospitalizacja": [ogromny]}}).status_code == 422
    odwrocony = {"od": "2026-05-10", "do": "2026-05-01"}
    assert c.post("/api/silnik/ocena", json={"zdrowie": {"ezla": [odwrocony]}}).status_code == 422
    za_duzo = [{"od": "2026-05-01", "do": "2026-05-02"}] * 51
    assert c.post("/api/silnik/ocena", json={"zdrowie": {"ezla": za_duzo}}).status_code == 422
