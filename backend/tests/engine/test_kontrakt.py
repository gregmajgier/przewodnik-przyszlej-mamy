"""Spójność kontraktu v1.1: modele Pydantic ↔ zmienne_uzytkownika.json, odwołania w regułach, indeksy."""

import sys
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.engine import schemas
from app.engine.derived import WYL_KEYS
from app.engine.kontrakt import load_kontrakt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "kontrakt"))
import indeksy  # noqa: E402


@pytest.fixture(scope="module")
def k():
    return load_kontrakt()


def _model_of(annotation):
    """Wyciąga klasę modelu z `X | None` i `list[X] | None`."""
    for arg in typing.get_args(annotation) or (annotation,):
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return arg
        inner = _model_of(arg) if typing.get_args(arg) else None
        if inner:
            return inner
    return None


def _literal_values(annotation) -> set | None:
    for arg in typing.get_args(annotation) or (annotation,):
        if typing.get_origin(arg) is typing.Literal:
            return set(typing.get_args(arg))
    return None


def _wejsciowe(k):
    return [z for z in k.zmienne["zmienne"] if not z["klucz"].startswith(("wyl.", "param."))]


def test_kazda_zmienna_wejsciowa_jest_w_modelu(k):
    for z in _wejsciowe(k):
        ns, _, pole = z["klucz"].partition(".")
        top = schemas.UserProfile.model_fields[ns]
        if not pole:
            assert ns in ("dzieci", "wnioski_zlozone"), z["klucz"]
            continue
        model = _model_of(top.annotation)
        assert pole in model.model_fields, f"brak pola {z['klucz']} w {model.__name__}"


def test_kazde_pole_modelu_jest_w_kontrakcie(k):
    klucze = {z["klucz"] for z in _wejsciowe(k)}
    for ns, f in schemas.UserProfile.model_fields.items():
        model = _model_of(f.annotation)
        if ns in ("dzieci", "wnioski_zlozone"):
            assert ns in klucze
            continue
        for pole in model.model_fields:
            assert f"{ns}.{pole}" in klucze, f"{ns}.{pole} nie ma w zmienne_uzytkownika.json"


def test_pola_obiektow_zgodne_z_kontraktem(k):
    for z in _wejsciowe(k):
        if "pola" not in z:
            continue
        ns, _, pole = z["klucz"].partition(".")
        if pole:
            model = _model_of(_model_of(schemas.UserProfile.model_fields[ns].annotation).model_fields[pole].annotation)
        else:
            model = _model_of(schemas.UserProfile.model_fields[ns].annotation)
        assert {p["nazwa"] for p in z["pola"]} == set(model.model_fields), z["klucz"]


def test_enumy_zgodne_z_kontraktem(k):
    for z in _wejsciowe(k):
        if "enum" not in z:
            continue
        ns, _, pole = z["klucz"].partition(".")
        ann = _model_of(schemas.UserProfile.model_fields[ns].annotation).model_fields[pole].annotation
        assert _literal_values(ann) == set(z["enum"]), z["klucz"]


def test_lista_zmiennych_wyliczanych_kompletna(k):
    wyl = {z["klucz"][4:] for z in k.zmienne["zmienne"] if z["klucz"].startswith("wyl.")}
    assert set(WYL_KEYS) == wyl


def test_brak_dawnych_kluczy_v01():
    with pytest.raises(Exception):
        schemas.UserProfile.model_validate({"tytul_ubezpieczenia": "umowa_o_prace"})


def test_indeksy_aktualne():
    assert indeksy.apply(*indeksy.load()) == []


def test_odwolania_w_regulach_istnieja(k):
    znane = {z["klucz"] for z in k.zmienne["zmienne"]}

    def param_ok(path):
        node = k.params
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return True

    kody = {w["kod"] for w in k.katalog["wnioski"]}
    for s in k.reguly["swiadczenia"]:
        wyrazenia = [w["wyrazenie"] for w in s["warunki"]] + [i["warunek"] for i in s.get("informacje", [])]
        wyrazenia += [w["warunek"] for w in s["wnioski"]]
        nazwy = set().union(*(set(w["zmienne"]) for w in s["warunki"]))
        for e in wyrazenia:
            nazwy |= indeksy.vars_of(e, set())
        for v in nazwy:
            assert param_ok(v[6:]) if v.startswith("param.") else indeksy.owning_key(v, znane), (s["id"], v)
        for p in s["wynik"]["parametry"]:
            assert param_ok(p), (s["id"], p)
        assert {w["kod"] for w in s["wnioski"]} <= kody, s["id"]
    for r in k.reguly["ryzyka"]:
        assert set(r.get("wnioski", [])) <= kody


def test_parametry_lista_i_drzewo_zgodne(k):
    for p in k.reguly["parametry"]:
        node = k.params
        for part in p["sciezka"].split("."):
            node = node[part]
        assert node == p["wartosc"], p["sciezka"]


def test_zmiany_z_kroku_1(k):
    sw = {s["id"]: s for s in k.reguly["swiadczenia"]}
    assert sw["SWIADCZENIE_REHABILITACYJNE"]["do_weryfikacji"] is False
    assert k.params["zasilek"]["rehabilitacyjny_max_dni"] == 360
    assert k.params["zasilek"]["podwyzszenie_do_swiadczenia_rodzicielskiego_zl"] == 1000
    assert sw["ZASILEK_OPIEKUNCZY"]["wnioski"][0]["kod"] == "Z-15"
    assert sw["ZASILEK_POGRZEBOWY"]["wnioski"][0]["kod"] == "Z-12"
    assert sw["ZASILEK_POGRZEBOWY"]["sciezka_ui"] == "/jaskolka"
    w3 = next(w for w in sw["ZASILEK_MACIERZYNSKI_OJCIEC_PRZEJECIE"]["warunki"] if w["id"].endswith("w3"))
    assert "matka.podjela_prace_min_pol_etatu" in w3["zmienne"]
    kody = {w["kod"] for w in k.katalog["wnioski"]}
    assert {"Z-15", "Z-12", "POG"} <= kody
