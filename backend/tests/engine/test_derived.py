"""Zmienne wyliczane wyl.* — przypadki brzegowe z przepisów."""

from datetime import date, timedelta

import pytest

from app.engine.derived import (
    WYL_KEYS,
    compute_derived_variables,
    data_z_pesel,
    oblicz_podstawe_wymiaru,
    pesel_poprawny,
)
from app.engine.kontrakt import load_kontrakt
from app.engine.schemas import UserProfile

PARAMS = load_kontrakt().params
DZIS = date(2026, 11, 21)


def pesel(base10: str) -> str:
    wagi = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    return base10 + str((10 - sum(int(c) * w for c, w in zip(base10, wagi)) % 10) % 10)


def wyl(data: dict, dzis: date = DZIS) -> dict:
    return compute_derived_variables(UserProfile.model_validate(data), PARAMS, dzis)


def miesiace(kwota: float, n: int = 12, rok: int = 2025, **kw) -> list[dict]:
    return [{"rok": rok, "miesiac": m, "podstawa_wymiaru_skladek": kwota, "dni_przepracowane": 20,
             "dni_do_przepracowania": 20, **kw} for m in range(1, n + 1)]


# ── PESEL ─────────────────────────────────────────────────────────────────────


def test_pesel_stulecie_1900_kobieta():
    p = pesel("9203151236")  # 10. cyfra 6 → K
    w = wyl({"wnioskodawca": {"pesel": p}})
    assert w["data_urodzenia_wnioskodawcy"] == date(1992, 3, 15)
    assert w["plec_wnioskodawcy"] == "K"
    assert w["wiek_wnioskodawcy_lat"] == 34


def test_pesel_stulecie_2000_mezczyzna():
    p = pesel("0422291235")  # miesiąc 22 → luty 2004 (przestępny), 10. cyfra 5 → M
    w = wyl({"wnioskodawca": {"pesel": p}})
    assert w["data_urodzenia_wnioskodawcy"] == date(2004, 2, 29)
    assert w["plec_wnioskodawcy"] == "M"


def test_pesel_bledna_suma_kontrolna_daje_brak_danych():
    p = pesel("9203151236")
    zly = p[:10] + str((int(p[10]) + 1) % 10)
    assert not pesel_poprawny(zly)
    assert wyl({"wnioskodawca": {"pesel": zly}})["data_urodzenia_wnioskodawcy"] is None


def test_pesel_inne_stulecia():
    assert data_z_pesel("85810100000") == date(1885, 1, 1)
    assert data_z_pesel("01410100000") == date(2101, 1, 1)
    assert data_z_pesel("92133100000") is None  # miesiąc 13


# ── okres wyczekiwania (art. 4) ───────────────────────────────────────────────


def _wycz(okresy, ezla_od, **ub):
    return wyl({"ubezpieczenie": {"okresy": okresy, **ub}, "zdrowie": {"ezla": [{"od": ezla_od, "do": "2026-12-31", "kod_B": True}]}})[
        "spelnia_okres_wyczekiwania"]


def test_wyczekiwanie_obowiazkowe_30_dni_granica():
    ok = [{"od": "2026-01-01", "do": None, "chorobowe": "obowiazkowe", "tytul": "umowa_o_prace"}]
    assert _wycz(ok, "2026-01-31") is True   # 30 dni ubezpieczenia przed niezdolnością
    assert _wycz(ok, "2026-01-30") is False  # 29 dni


def test_wyczekiwanie_dobrowolne_90_dni():
    ok = [{"od": "2026-01-01", "do": None, "chorobowe": "dobrowolne", "tytul": "umowa_zlecenia"}]
    assert _wycz(ok, "2026-04-01") is True   # 90 dni
    assert _wycz(ok, "2026-03-31") is False


def test_wyczekiwanie_przerwa_do_30_dni_laczy_okresy():
    ok = [{"od": "2025-12-01", "do": "2025-12-20", "chorobowe": "obowiazkowe"},
          {"od": "2026-01-20", "do": None, "chorobowe": "obowiazkowe"}]  # przerwa 30 dni
    assert _wycz(ok, "2026-01-30") is True   # 20 + 10 dni
    ok[1]["od"] = "2026-01-21"  # przerwa 31 dni — ciągłość przerwana
    assert _wycz(ok, "2026-01-31") is False


def test_wyczekiwanie_10_lat_obowiazkowego_bez_wyczekiwania():
    ok = [{"od": "2010-01-01", "do": "2025-12-31", "chorobowe": "obowiazkowe"},
          {"od": "2026-11-01", "do": None, "chorobowe": "obowiazkowe"}]
    assert _wycz(ok, "2026-11-05") is True


def test_wyczekiwanie_bez_ezla_brak_danych():
    assert wyl({"ubezpieczenie": {"okresy": []}})["spelnia_okres_wyczekiwania"] is None


# ── podstawa wymiaru (art. 36–49) ─────────────────────────────────────────────


def _podst(**ub):
    return oblicz_podstawe_wymiaru(UserProfile.model_validate({"ubezpieczenie": ub}), PARAMS)


def test_podstawa_srednia_12_miesiecy_minus_13_71():
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=1.0, przychody_12_miesiecy=miesiace(6000))
    assert float(p.wartosc) == 5177.40  # 6000 × 0,8629


def test_podstawa_miesiac_niepelny_uzupelniony_proporcjonalnie():
    m = miesiace(6000)
    m[0].update(podstawa_wymiaru_skladek=3000, dni_przepracowane=10, dni_do_przepracowania=20)
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=1.0, przychody_12_miesiecy=m)
    assert p.miesiace[0]["status"] == "uzupełniony (10/20 dni)"
    assert float(p.wartosc) == 5177.40


def test_podstawa_miesiac_ponizej_polowy_wylaczony():
    m = miesiace(6000)
    m[0].update(podstawa_wymiaru_skladek=100, dni_przepracowane=9, dni_do_przepracowania=20)
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=1.0, przychody_12_miesiecy=m)
    assert p.miesiace[0]["status"].startswith("wyłączony")
    assert float(p.wartosc) == 5177.40


def test_podstawa_dziedziczona_przy_przerwie_ponizej_miesiaca():
    p = _podst(tytul="umowa_o_prace", przerwa_od_poprzedniego_zasilku_dni=10, podstawa_poprzedniego_zasilku=4321.5,
               przychody_12_miesiecy=miesiace(9000))
    assert float(p.wartosc) == 4321.50 and "art. 43" in p.metoda
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=1.0, przerwa_od_poprzedniego_zasilku_dni=45,
               podstawa_poprzedniego_zasilku=4321.5, przychody_12_miesiecy=miesiace(6000))
    assert float(p.wartosc) == 5177.40


def test_podstawa_minimalna_pelny_etat():
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=1.0, przychody_12_miesiecy=miesiace(3000))
    assert float(p.wartosc) == 4147.10  # 4806 × 0,8629
    p = _podst(tytul="umowa_o_prace", wymiar_etatu=0.5, przychody_12_miesiecy=miesiace(3000))
    assert float(p.wartosc) == 2588.70


def test_podstawa_jdg_12_miesiecy_i_krotsze_ubezpieczenie():
    pelne = [{"rok": 2025, "miesiac": m, "kwota": 5000} for m in range(1, 13)]
    assert float(_podst(tytul="jdg", zadeklarowana_podstawa_jdg=pelne).wartosc) == 4314.50
    szesc = [{"rok": 2026, "miesiac": m, "kwota": 7652} for m in range(1, 7)]
    # art. 48a: 5652 × 0,8629 + (2000 × 0,8629) × 6/12
    assert float(_podst(tytul="jdg", zadeklarowana_podstawa_jdg=szesc).wartosc) == 5740.01
    assert float(_podst(tytul="jdg", zadeklarowana_podstawa_jdg=[]).wartosc) == 4877.11  # art. 49


def test_podstawa_dobrowolne_limit():
    p = _podst(tytul="umowa_zlecenia", chorobowe="dobrowolne", przychody_12_miesiecy=miesiace(30000))
    assert float(p.wartosc) == 20321.30  # 23 550 × 0,8629


def test_podstawa_brak_danych():
    assert _podst(tytul="umowa_o_prace").wartosc is None


# ── urlop uzupełniający (art. 180² KP) ────────────────────────────────────────


def _uzup(tydzien, masa, hosp_dni, start_dzien=0):
    porod = date(2026, 9, 1)
    hosp = None if hosp_dni is None else [{"od": str(porod + timedelta(days=start_dzien)),
                                           "do": str(porod + timedelta(days=start_dzien + hosp_dni - 1))}]
    return wyl({"porod": {"data_porodu": str(porod), "tydzien_ciazy": tydzien, "liczba_dzieci": 1},
                "dzieci": [{"data_urodzenia": str(porod), "masa_urodzeniowa_g": masa, "hospitalizacja": hosp}]})[
        "uzupelniajacy_wymiar_tyg"]


def test_uzupelniajacy_wczesniak_26_tyg_850g_15_tygodni():
    assert _uzup(26, 850, 120) == 15


def test_uzupelniajacy_tydzien_za_tydzien_pobytu():
    assert _uzup(26, 850, 20) == 3   # 20 dni → 3 tyg. (w górę)
    assert _uzup(35, 2100, 10) == 2  # pkt 2: limit 8
    assert _uzup(35, 2100, 90) == 8


def test_uzupelniajacy_po_37_tyg_tylko_od_5_dnia():
    assert _uzup(39, 3400, 3, start_dzien=6) == 1
    assert _uzup(39, 3400, 3, start_dzien=0) == 0


def test_uzupelniajacy_masa_do_1000g_przy_pozniejszym_tygodniu():
    assert _uzup(32, 1000, 60) == 9   # ≤ 1000 g → kategoria 15 tyg.


def test_uzupelniajacy_brak_danych():
    assert _uzup(26, 850, None) is None  # wiadomo, że limit 15, ale nie wiadomo, ile w szpitalu
    assert wyl({"ciaza": {"w_ciazy": True}})["uzupelniajacy_wymiar_tyg"] is None


# ── art. 177 § 3 KP i ubezpieczenie w dniu porodu ─────────────────────────────

CIAZA = {"w_ciazy": True, "przewidywana_data_porodu": "2027-03-01"}  # początek ≈ 2026-05-25, 3. mies. → 2026-08-25


def _umowa(rodzaj, koniec, **extra):
    return wyl({"wnioskodawca": {"etap": "w_ciazy"}, "ciaza": CIAZA,
                "ubezpieczenie": {"tytul": "umowa_o_prace", "chorobowe": "obowiazkowe", "rodzaj_umowy_o_prace": rodzaj,
                                  "data_konca_umowy": koniec,
                                  "okresy": [{"od": "2024-01-01", "do": None, "chorobowe": "obowiazkowe"}], **extra}})


def test_umowa_terminowa_przedluzona_do_porodu():
    w = _umowa("czas_okreslony", "2026-10-31")
    assert w["data_konca_3_miesiaca_ciazy"] == date(2026, 8, 25)
    assert w["umowa_przedluzona_do_porodu"] is True
    assert w["ubezpieczony_w_dniu_porodu"] is True
    assert w["ubezpieczenie_ustalo_przed_porodem"] is False


def test_umowa_konczaca_sie_przed_uplywem_3_miesiaca_nie_przedluza_sie():
    w = _umowa("czas_okreslony", "2026-08-20")
    assert w["umowa_przedluzona_do_porodu"] is False
    assert w["ubezpieczony_w_dniu_porodu"] is False
    assert w["ubezpieczenie_ustalo_przed_porodem"] is True


@pytest.mark.parametrize("rodzaj", ["zastepstwo", "okres_probny_do_1_mies", "czas_nieokreslony"])
def test_umowy_bez_przedluzenia(rodzaj):
    assert _umowa(rodzaj, "2026-10-31")["umowa_przedluzona_do_porodu"] is False


def test_okres_probny_powyzej_miesiaca_przedluzony():
    assert _umowa("okres_probny_powyzej_1_mies", "2026-10-31")["umowa_przedluzona_do_porodu"] is True


def test_umowa_konczaca_sie_po_porodzie_nie_wymaga_przedluzenia():
    assert _umowa("czas_okreslony", "2027-06-30")["umowa_przedluzona_do_porodu"] is False


def test_umowa_nieznany_rodzaj_brak_danych():
    assert _umowa(None, "2026-10-31")["umowa_przedluzona_do_porodu"] is None


# ── podwyższenie do świadczenia rodzicielskiego (art. 31 ust. 3a) ──────────────


def _podw(podstawa, wniosek815):
    return wyl({"ubezpieczenie": {"tytul": "umowa_o_prace", "przerwa_od_poprzedniego_zasilku_dni": 0,
                                  "podstawa_poprzedniego_zasilku": podstawa},
                "plan": {"wniosek_81_5": {"czy": wniosek815}}})["przysluguje_podwyzszenie_do_sr"]


def test_podwyzszenie_do_1000_zl():
    assert _podw(1200, False) is True   # 70% = 840 zł
    assert _podw(1200, True) is True    # 81,5% = 978 zł
    assert _podw(1300, True) is False   # 81,5% = 1059,50 zł
    assert _podw(1300, False) is True   # rodzicielski 70% = 910 zł
    assert _podw(2000, False) is False


# ── dzieci i świadczenia rodzinne ─────────────────────────────────────────────


def test_martwe_urodzenie_nie_liczy_sie_do_800plus():
    w = wyl({"porod": {"data_porodu": "2026-11-01", "stan_dziecka": "martwe"},
             "dzieci": [{"data_urodzenia": "2026-11-01", "pobyt_w_polsce": True}]})
    assert w["liczba_dzieci_do_800plus"] == 0


def test_800plus_pewne_niepewne():
    dz = [{"data_urodzenia": "2020-01-01", "pobyt_w_polsce": None}]
    assert wyl({"dzieci": dz})["liczba_dzieci_do_800plus"] is None
    dz.append({"data_urodzenia": "2022-01-01", "pobyt_w_polsce": True})
    assert wyl({"dzieci": dz})["liczba_dzieci_do_800plus"] == 1
    dz.append({"data_urodzenia": "2007-11-20", "pobyt_w_polsce": True})  # skończyło 18 lat
    assert wyl({"dzieci": dz})["liczba_dzieci_do_800plus"] == 1


def test_okno_urlopu_ojcowskiego_12_miesiecy():
    assert wyl({"porod": {"data_porodu": "2025-11-22"}})["dziecko_w_oknie_urlopu_ojcowskiego"] is True
    assert wyl({"porod": {"data_porodu": "2025-11-21"}})["dziecko_w_oknie_urlopu_ojcowskiego"] is False


def test_rodzicielski_do_konca_roku_6_lat_i_przysposobienie_14():
    assert wyl({"porod": {"data_porodu": "2020-01-15"}})["dziecko_w_wieku_urlopu_rodzicielskiego"] is True
    assert wyl({"porod": {"data_porodu": "2019-12-31"}})["dziecko_w_wieku_urlopu_rodzicielskiego"] is False
    adop = {"wnioskodawca": {"etap": "adopcja_zastepcza"},
            "dzieci": [{"data_urodzenia": "2015-01-01", "przyjete_na_wychowanie": {"rodzaj": "przysposobienie",
                        "data_przyjecia": "2026-10-01", "data_uprawomocnienia": "2026-10-15"}}]}
    w = wyl(adop)
    assert w["dziecko_w_wieku_urlopu_rodzicielskiego"] is True
    assert w["dziecko_przyjete_w_limicie_wieku"] is True
    assert w["dziecko_w_oknie_urlopu_ojcowskiego"] is True


def test_rodzina_zastepcza_limit_7_lub_10_lat():
    dz = {"data_urodzenia": "2018-06-01", "przyjete_na_wychowanie": {"rodzaj": "rodzina_zastepcza_niezawodowa"}}
    assert wyl({"dzieci": [dz]})["dziecko_przyjete_w_limicie_wieku"] is False
    assert wyl({"dzieci": [{**dz, "odroczony_obowiazek_szkolny": True}]})["dziecko_przyjete_w_limicie_wieku"] is True


def test_dochod_na_osobe():
    w = wyl({"rodzina": {"sklad": [{}, {}, {}], "dochod_rok_bazowy": {"dochody_opodatkowane": 60000,
                                                                       "dochody_nieopodatkowane": 1200,
                                                                       "dochody_utracone": 3600}}})
    assert w["dochod_na_osobe"] == 1600.0


def test_aktywny_rodzic_tryby():
    dz = [{"data_urodzenia": "2025-06-01", "placowka_opieki": {"rodzaj": "zlobek"}}]
    w = wyl({"dzieci": dz, "ubezpieczenie": {"tytul": "umowa_o_prace"}, "drugi_rodzic": {"aktywny_zawodowo": True}})
    assert w["ma_dziecko_12_35_mies"] and w["ma_dziecko_w_zlobku"] and w["oboje_rodzice_aktywni_zawodowo"]
    assert w["rodzic_aktywny_w_domu"] is False


def test_matka_hospitalizowana_w_oknie_po_8_tyg():
    base = {"porod": {"data_porodu": "2026-09-01", "liczba_dzieci": 1}}
    assert wyl({**base, "matka": {"hospitalizacja": [{"od": "2026-10-30", "do": "2026-11-05"}]}})["matka_hospitalizowana"] is True
    assert wyl({**base, "matka": {"hospitalizacja": [{"od": "2026-09-01", "do": "2026-09-05"}]}})["matka_hospitalizowana"] is False


def test_po_ustaniu_ubezpieczenia_okno_14_dni_i_30_dni_niezdolnosci():
    base = {"ubezpieczenie": {"data_ustania": "2026-10-01", "chorobowe": "obowiazkowe"}}
    ok = wyl({**base, "zdrowie": {"ezla": [{"od": "2026-10-10", "do": "2026-11-20", "kod_B": True}]}})
    assert ok["w_okresie_po_ustaniu_ubezpieczenia"] is True and ok["tytul_aktywny_lub_w_oknie"] is True
    krotka = wyl({**base, "zdrowie": {"ezla": [{"od": "2026-10-10", "do": "2026-10-20", "kod_B": True}]}})
    assert krotka["w_okresie_po_ustaniu_ubezpieczenia"] is False
    za_pozno = wyl({**base, "zdrowie": {"ezla": [{"od": "2026-10-20", "do": "2026-12-20", "kod_B": True}]}})
    assert za_pozno["w_okresie_po_ustaniu_ubezpieczenia"] is False


def test_platnik_wyplaca_powyzej_20():
    assert wyl({"ubezpieczenie": {"tytul": "umowa_o_prace", "platnik": {"liczba_ubezpieczonych_chorobowo": 21}}})[
        "platnik_wyplaca_zasilki"] is True
    assert wyl({"ubezpieczenie": {"tytul": "umowa_o_prace", "platnik": {"liczba_ubezpieczonych_chorobowo": 20}}})[
        "platnik_wyplaca_zasilki"] is False
    assert wyl({"ubezpieczenie": {"tytul": "jdg"}})["platnik_wyplaca_zasilki"] is False


def test_termin_81_5():
    assert wyl({"porod": {"data_porodu": "2026-11-10"}})["dni_do_konca_terminu_81_5"] == 10
    assert wyl({"porod": {"data_porodu": "2026-10-01"}})["dni_do_konca_terminu_81_5"] == -30


def test_brak_prawa_do_zasilku_macierzynskiego():
    assert wyl({"ubezpieczenie": {"tytul": "student"}})["brak_prawa_do_zasilku_macierzynskiego"] is True
    assert wyl({})["brak_prawa_do_zasilku_macierzynskiego"] is None


def test_pusty_profil_wszystkie_klucze_bez_wyjatkow():
    w = wyl({})
    assert set(w) == set(WYL_KEYS)
    for k in ("pracownik", "data_odniesienia_porodu", "ubezpieczony_w_dniu_porodu", "podstawa_wymiaru_zasilku",
              "dochod_na_osobe", "liczba_dzieci_do_800plus", "spelnia_okres_wyczekiwania", "uzupelniajacy_wymiar_tyg"):
        assert w[k] is None, k
