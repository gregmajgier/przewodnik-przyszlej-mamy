"""Modele danych silnika uprawnień (kontrakt v1.1).

Wejście (`UserProfile`) odpowiada 1:1 przestrzeniom nazw z `app/data/zmienne_uzytkownika.json`:
wnioskodawca, ubezpieczenie, zdrowie, ciaza, porod, dzieci, matka, drugi_rodzic, rodzina, plan,
wnioski_zlozone. Przestrzenie `wyl` (wyliczane) i `param` (parametry) dokłada silnik — nie przychodzą z API.

Zasada braku danych: każde pole ma domyślnie `None` (= „nie wiemy”). Zmienna `None` użyta w warunku
daje status `brak_danych`, a nie `nie_przysluguje`. Pusta lista (`[]`) znaczy „wiemy, że nic nie ma”,
`None` — „nie wiemy”.

Modele mają `extra="forbid"`: dawne płaskie klucze z v0.1 (np. `tytul_ubezpieczenia`) są odrzucane
zamiast po cichu ignorowane.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Silnik rozwija okresy e-ZLA i hospitalizacji do pojedynczych dni, więc wejście z API ma twarde limity:
# bez nich jeden zakres 0001-01-01 – 9999-12-31 to miliony dni na żądanie.
MAX_ZAKRES_DNI = 3 * 366
MAX_POZYCJI = 50


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ZakresDat(_Model):
    """Zakres od–do rozwijany przez silnik dzień po dniu: od ≤ do i najwyżej `MAX_ZAKRES_DNI`."""

    od: date | None = None
    do: date | None = None

    @model_validator(mode="after")
    def _zakres(self):
        if self.od is not None and self.do is not None:
            if self.do < self.od:
                raise ValueError("data „do” jest wcześniejsza niż „od”")
            if (self.do - self.od).days > MAX_ZAKRES_DNI:
                raise ValueError(f"zakres dat dłuższy niż {MAX_ZAKRES_DNI} dni")
        return self


# ─────────────────────────────── enumy (z zmienne_uzytkownika.json) ───────────────────────────────

Etap = Literal["planuje", "w_ciazy", "po_porodzie", "adopcja_zastepcza"]
Rola = Literal["matka", "ojciec", "przysposabiajacy", "rodzina_zastepcza_niezawodowa", "rodzina_zastepcza_zawodowa", "inna"]
StanCywilny = Literal["panna_kawaler", "malzenstwo", "rozwod", "separacja", "wdowa_wdowiec"]
TytulUbezpieczenia = Literal[
    "umowa_o_prace", "umowa_zlecenia", "jdg", "wspolpraca_jdg", "ulga_na_start", "umowa_o_dzielo", "duchowny",
    "marynarz", "sluzba_mundurowa", "krus", "bezrobotna_z_zasilkiem", "bezrobotna_bez_zasilku", "student", "brak",
]
Chorobowe = Literal["obowiazkowe", "dobrowolne", "brak"]
PrzyczynaRozwiazania = Literal["upadlosc", "likwidacja", "smierc_pracodawcy", "naruszenie_przepisow", "inna"]
RodzajUmowyOPrace = Literal[
    "czas_nieokreslony", "czas_okreslony", "okres_probny_powyzej_1_mies", "okres_probny_do_1_mies", "zastepstwo",
]
StanDziecka = Literal["zywe", "martwe", "zgon_do_8_tyg", "zgon_po_8_tyg"]
StanMatki = Literal["zyje", "zmarla", "porzucila_dziecko"]
RodzajPrzyjecia = Literal["przysposobienie", "rodzina_zastepcza_niezawodowa"]
Rodzic = Literal["matka", "ojciec"]


# ─────────────────────────────── obiekty pomocnicze ───────────────────────────────


class Okres(_ZakresDat):
    pass


class DokumentTozsamosci(_Model):
    rodzaj: str | None = None
    seria: str | None = None
    numer: str | None = None


class AdresZamieszkania(_Model):
    ulica: str | None = None
    nr_domu: str | None = None
    nr_lokalu: str | None = None
    kod_pocztowy: str | None = None
    miejscowosc: str | None = None
    gmina: str | None = None
    teryt_gminy: str | None = Field(default=None, pattern=r"^\d{7}$")
    powiat: str | None = None
    wojewodztwo: str | None = None
    kraj: str | None = None  # ISO 3166-1 alfa-2, np. "PL"


class AdresKorespondencyjny(_Model):
    ulica: str | None = None
    nr_domu: str | None = None
    nr_lokalu: str | None = None
    kod_pocztowy: str | None = None
    miejscowosc: str | None = None
    kraj: str | None = None


# ─────────────────────────────── przestrzenie nazw ───────────────────────────────


class Wnioskodawca(_Model):
    etap: Etap | None = None
    rola: Rola | None = None
    imie: str | None = None
    drugie_imie: str | None = None
    nazwisko: str | None = None
    nazwisko_rodowe: str | None = None
    pesel: str | None = Field(default=None, pattern=r"^\d{11}$")
    dokument_tozsamosci: DokumentTozsamosci | None = None
    obywatelstwo: str | None = None
    legalny_pobyt_w_polsce: bool | None = None
    status_ukr: bool | None = None
    aktywnosc_zawodowa_ukr: bool | None = None
    adres_zamieszkania: AdresZamieszkania | None = None
    adres_korespondencyjny: AdresKorespondencyjny | None = None
    telefon: str | None = None
    email: str | None = None
    adres_e_doreczen: str | None = None
    numer_rachunku: str | None = None
    wlasciciel_rachunku: str | None = None
    stan_cywilny: StanCywilny | None = None


class OkresUbezpieczenia(_Model):
    od: date | None = None
    do: date | None = None  # None = trwa
    tytul: str | None = None
    chorobowe: str | None = None  # obowiazkowe | dobrowolne | brak
    platnik_nip: str | None = None


class Platnik(_Model):
    nazwa: str | None = None
    nip: str | None = None
    regon: str | None = None
    adres: str | None = None
    liczba_ubezpieczonych_chorobowo: int | None = Field(default=None, ge=0)


class PrzychodMiesieczny(_Model):
    rok: int | None = None
    miesiac: int | None = Field(default=None, ge=1, le=12)
    podstawa_wymiaru_skladek: float | None = Field(default=None, ge=0)
    skladniki_zmienne: float | None = Field(default=None, ge=0)
    wynagrodzenie_chorobowe: float | None = Field(default=None, ge=0)
    dni_przepracowane: int | None = Field(default=None, ge=0)
    dni_do_przepracowania: int | None = Field(default=None, ge=0)


class PodstawaJdg(_Model):
    rok: int | None = None
    miesiac: int | None = Field(default=None, ge=1, le=12)
    kwota: float | None = Field(default=None, ge=0)


class ZmianaPodstawy(_Model):
    czy: bool | None = None
    data: date | None = None
    kwota_przed: float | None = None
    kwota_po: float | None = None


class ZmianaWarunkow(_Model):
    czy: bool | None = None
    data: date | None = None
    opis: str | None = None


class Zadluzenie(_Model):
    kwota: float | None = Field(default=None, ge=0)
    na_dzien: date | None = None


class Ubezpieczenie(_Model):
    tytul: TytulUbezpieczenia | None = None
    chorobowe: Chorobowe | None = None
    data_objecia_chorobowym: date | None = None
    okresy: list[OkresUbezpieczenia] | None = Field(default=None, max_length=MAX_POZYCJI)
    data_ustania: date | None = None
    umowa_rozwiazana_w_ciazy: bool | None = None
    przyczyna_rozwiazania_umowy: PrzyczynaRozwiazania | None = None
    prawomocny_wyrok_naruszenie_przepisow: bool | None = None
    zapewniono_inne_zatrudnienie: bool | None = None
    platnik: Platnik | None = None
    wymiar_etatu: float | None = Field(default=None, gt=0, le=1)
    rodzaj_umowy_o_prace: RodzajUmowyOPrace | None = None
    data_konca_umowy: date | None = None
    dni_wynagrodzenia_chorobowego_w_roku: int | None = Field(default=None, ge=0)
    przychody_12_miesiecy: list[PrzychodMiesieczny] | None = Field(default=None, max_length=MAX_POZYCJI)
    przerwa_od_poprzedniego_zasilku_dni: int | None = Field(default=None, ge=0)
    podstawa_poprzedniego_zasilku: float | None = Field(default=None, ge=0)
    zadeklarowana_podstawa_jdg: list[PodstawaJdg] | None = Field(default=None, max_length=MAX_POZYCJI)
    zmiana_podstawy_w_ciazy: ZmianaPodstawy | None = None
    zmiana_warunkow_zatrudnienia_w_ciazy: ZmianaWarunkow | None = None
    zadluzenie_skladkowe: Zadluzenie | None = None
    pobiera_emeryture_rente: bool | None = None
    zlozyla_wniosek_emerytura_renta: bool | None = None


class Ezla(_ZakresDat):
    seria_numer: str | None = None
    kod_B: bool | None = None  # noqa: N815 - nazwa z kontraktu


class Zdrowie(_Model):
    ezla: list[Ezla] | None = Field(default=None, max_length=MAX_POZYCJI)
    okres_zasilkowy_wykorzystany_dni: int | None = Field(default=None, ge=0)
    nadal_niezdolna_do_pracy: bool | None = None
    rokowania_odzyskania_zdolnosci: bool | None = None
    data_wyczerpania_zasilku: date | None = None
    zasilek_opiekunczy_wykorzystany_dni: int | None = Field(default=None, ge=0)


class Ciaza(_Model):
    w_ciazy: bool | None = None
    przewidywana_data_porodu: date | None = None
    opieka_medyczna_od_10_tyg: bool | None = None


class Porod(_Model):
    data_porodu: date | None = None
    stan_dziecka: StanDziecka | None = "zywe"  # domyślna z kontraktu: przed porodem przyjmujemy „zywe”
    data_zgonu_dziecka: date | None = None
    liczba_dzieci: int | None = Field(default=None, ge=1, le=10)
    tydzien_ciazy: int | None = Field(default=None, ge=20, le=45)


class Niepelnosprawnosc(_Model):
    orzeczenie: str | None = None
    stopien: str | None = None


class PrzyjecieNaWychowanie(_Model):
    rodzaj: RodzajPrzyjecia | None = None
    data_przyjecia: date | None = None
    data_wystapienia_do_sadu: date | None = None
    data_uprawomocnienia: date | None = None


class PlacowkaOpieki(_Model):
    rodzaj: str | None = None
    data_rozpoczecia: date | None = None
    oplata_miesieczna: float | None = Field(default=None, ge=0)


class Dziecko(_Model):
    imie: str | None = None
    nazwisko: str | None = None
    pesel: str | None = Field(default=None, pattern=r"^\d{11}$")
    data_urodzenia: date | None = None
    masa_urodzeniowa_g: int | None = Field(default=None, ge=200, le=7000)
    hospitalizacja: list[Okres] | None = Field(default=None, max_length=MAX_POZYCJI)
    zaswiadczenie_za_zyciem: bool | None = None
    niepelnosprawnosc: Niepelnosprawnosc | None = None
    przyjete_na_wychowanie: PrzyjecieNaWychowanie | None = None
    odroczony_obowiazek_szkolny: bool | None = None
    placowka_opieki: PlacowkaOpieki | None = None
    uczy_sie: bool | None = None
    na_utrzymaniu: bool | None = None
    w_pieczy_instytucjonalnej: bool | None = None
    pobyt_w_polsce: bool | None = None


class Matka(_Model):
    stan: StanMatki | None = None
    ubezpieczona_w_dniu_porodu: bool | None = None
    wykorzystala_14_tyg: bool | None = None
    data_konca_urlopu_macierzynskiego: date | None = None
    pobiera_zasilek_8_tyg_po_porodzie: bool | None = None
    hospitalizacja: list[Okres] | None = Field(default=None, max_length=MAX_POZYCJI)
    orzeczenie_niezdolnosci_do_samodzielnej_egzystencji: bool | None = None
    podjela_prace_min_pol_etatu: bool | None = None


class DaneDrugiegoRodzica(_Model):
    imie: str | None = None
    nazwisko: str | None = None
    pesel: str | None = Field(default=None, pattern=r"^\d{11}$")
    adres: str | None = None
    obywatelstwo: str | None = None


class PlatnikDrugiegoRodzica(_Model):
    nazwa: str | None = None
    nip: str | None = None
    adres: str | None = None


class DrugiRodzic(_Model):
    dane: DaneDrugiegoRodzica | None = None
    tytul_ubezpieczenia: TytulUbezpieczenia | None = None
    platnik: PlatnikDrugiegoRodzica | None = None
    aktywny_zawodowo: bool | None = None


class CzlonekRodziny(_Model):
    imie: str | None = None
    nazwisko: str | None = None
    pesel: str | None = Field(default=None, pattern=r"^\d{11}$")
    pokrewienstwo: str | None = None
    data_urodzenia: date | None = None


class DochodRodziny(_Model):
    rok: int | None = None
    dochody_opodatkowane: float | None = None
    dochody_nieopodatkowane: float | None = None
    dochody_utracone: float | None = None
    dochody_uzyskane: float | None = None


class InneSwiadczenie(_Model):
    rodzaj: str | None = None
    instytucja: str | None = None
    od: date | None = None


class Rodzina(_Model):
    sklad: list[CzlonekRodziny] | None = Field(default=None, max_length=MAX_POZYCJI)
    dochod_rok_bazowy: DochodRodziny | None = None
    samotne_wychowywanie: bool | None = None
    uznanie_ojcostwa: bool | None = None
    wspolne_gospodarstwo_domowe: bool | None = None
    opieka_naprzemienna: bool | None = None
    inne_pobierane_swiadczenia: list[InneSwiadczenie] | None = Field(default=None, max_length=MAX_POZYCJI)
    swiadczenie_za_granica: bool | None = None
    poniesiono_koszty_pogrzebu: bool | None = None


class PlanUrlopuMacierzynskiego(_Model):
    od: date | None = None
    do: date | None = None
    tygodnie_przed_porodem: int | None = Field(default=None, ge=0)


class Wniosek815(_Model):
    czy: bool | None = None
    data_zlozenia: date | None = None


class Rezygnacja(_Model):
    czy: bool | None = None
    data: date | None = None


class CzescRodzicielskiego(_Model):
    rodzic: Rodzic | None = None
    od: date | None = None
    do: date | None = None
    wymiar_pracy_w_trakcie: float | None = Field(default=None, ge=0, le=1)


class UrlopUzupelniajacy(_Model):
    wymiar_tyg: int | None = Field(default=None, ge=0)
    od: date | None = None
    do: date | None = None
    rodzic: Rodzic | None = None


class Plan(_Model):
    urlop_macierzynski: PlanUrlopuMacierzynskiego | None = None
    wniosek_81_5: Wniosek815 | None = None
    rezygnacja_z_macierzynskiego_po_14_tyg: Rezygnacja | None = None
    czesci_urlopu_rodzicielskiego: list[CzescRodzicielskiego] | None = Field(default=None, max_length=MAX_POZYCJI)
    urlop_uzupelniajacy: UrlopUzupelniajacy | None = None
    czesci_urlopu_ojcowskiego: list[Okres] | None = Field(default=None, max_length=MAX_POZYCJI)
    data_zlozenia_wniosku_u_pracodawcy: date | None = None


class WniosekZlozony(_Model):
    kod: str | None = None
    data_zlozenia: date | None = None
    status: str | None = None


class UserProfile(_Model):
    """Pełny profil użytkownika (wejście silnika). Brak przestrzeni = pusta przestrzeń (same `None`)."""

    wnioskodawca: Wnioskodawca = Field(default_factory=Wnioskodawca)
    ubezpieczenie: Ubezpieczenie = Field(default_factory=Ubezpieczenie)
    zdrowie: Zdrowie = Field(default_factory=Zdrowie)
    ciaza: Ciaza = Field(default_factory=Ciaza)
    porod: Porod = Field(default_factory=Porod)
    dzieci: list[Dziecko] | None = Field(default=None, max_length=MAX_POZYCJI)
    matka: Matka = Field(default_factory=Matka)
    drugi_rodzic: DrugiRodzic = Field(default_factory=DrugiRodzic)
    rodzina: Rodzina = Field(default_factory=Rodzina)
    plan: Plan = Field(default_factory=Plan)
    wnioski_zlozone: list[WniosekZlozony] | None = Field(default=None, max_length=MAX_POZYCJI)

    def kontekst(self) -> dict[str, Any]:
        """Słownik do JSONLogic (daty jako ISO, `None` zostaje `None`). Bez `wyl` i `param`."""
        return self.model_dump(mode="json")


# ─────────────────────────────── odpowiedź API ───────────────────────────────

Status = Literal["przysluguje", "nie_przysluguje", "brak_danych"]
InstytucjaGrupa = Literal["pracodawca", "zus", "gmina", "usc"]


class OkresSwiadczenia(_Model):
    """Fragment wyliczenia: np. „urlop macierzyński 100%” albo „wynagrodzenie chorobowe (pracodawca)”."""

    nazwa: str
    od: date | None = None
    do: date | None = None
    dni: int | None = None
    tygodnie: float | None = None
    procent: float | None = None
    stawka_dzienna: float | None = None
    kwota: float | None = None
    wyplaca: str | None = None  # np. "pracodawca", "ZUS"


class Wyliczenie(_Model):
    funkcja: str
    kwota_miesieczna: float | None = None
    kwota_jednorazowa: float | None = None
    kwota_laczna: float | None = None
    stawka_dzienna: float | None = None
    podstawa_wymiaru: float | None = None
    okresy: list[OkresSwiadczenia] = Field(default_factory=list)
    szczegoly: dict[str, Any] = Field(default_factory=dict)
    uwagi: list[str] = Field(default_factory=list)
    brakujace_dane: list[str] = Field(default_factory=list)


class WynikSwiadczenia(_Model):
    id: str
    nazwa: str
    typ: str
    instytucja: str
    status: Status
    przyczyny: list[str] = Field(default_factory=list)  # przyczyny_braku_uprawnien niespełnionych warunków
    niespelnione_warunki: list[str] = Field(default_factory=list)
    brakujace_zmienne: list[str] = Field(default_factory=list)
    informacje: list[str] = Field(default_factory=list)
    wyliczenie: Wyliczenie | None = None
    wnioski: list[str] = Field(default_factory=list)  # kody z katalogu
    do_weryfikacji: bool = False
    sciezka_ui: str | None = None


class AktywneRyzyko(_Model):
    id: str
    nazwa: str
    poziom: str
    komunikat: str
    dotyczy: list[str] = Field(default_factory=list)
    wnioski: list[str] = Field(default_factory=list)
    podstawa: str | None = None


class WymaganyWniosek(_Model):
    kod: str
    nazwa: str
    grupa: InstytucjaGrupa
    instytucja: str
    tryb_aplikacji: str | None = None
    tylko_elektronicznie: bool = False
    wysylka: list[str] = Field(default_factory=list)
    swiadczenia: list[str] = Field(default_factory=list)
    ryzyka: list[str] = Field(default_factory=list)
    termin: date | None = None
    termin_opis: str | None = None
    zlozony: bool = False
    dla: Literal["wnioskodawca", "drugi_rodzic"] = "wnioskodawca"


class WymaganeWnioski(_Model):
    pracodawca: list[WymaganyWniosek] = Field(default_factory=list)
    zus: list[WymaganyWniosek] = Field(default_factory=list)
    gmina: list[WymaganyWniosek] = Field(default_factory=list)
    usc: list[WymaganyWniosek] = Field(default_factory=list)


class DataGraniczna(_Model):
    data: date
    rodzaj: Literal["zlozenie_wniosku", "wygasniecie_prawa", "plan", "ostrzezenie"]
    opis: str
    kod_wniosku: str | None = None
    swiadczenie: str | None = None
    po_terminie: bool = False


class BladPlanu(_Model):
    id: str  # id z walidacje_planu
    poziom: Literal["blad", "ostrzezenie"]
    komunikat: str
    data: date | None = None


class EvaluationResponse(_Model):
    data_oceny: date
    wersja_kontraktu: str
    swiadczenia: list[WynikSwiadczenia]
    swiadczenia_drugiego_rodzica: list[WynikSwiadczenia] = Field(default_factory=list)  # np. SR-7 dla matki bez ubezpieczenia
    ryzyka: list[AktywneRyzyko] = Field(default_factory=list)
    wnioski: WymaganeWnioski = Field(default_factory=WymaganeWnioski)
    kalendarz: list[DataGraniczna] = Field(default_factory=list)
    walidacja_planu: list[BladPlanu] = Field(default_factory=list)
    brakujace_zmienne: list[str] = Field(default_factory=list)  # suma braków ze wszystkich świadczeń
    wyl: dict[str, Any] = Field(default_factory=dict)  # zmienne wyliczane (przejrzystość dla UI i testów)
