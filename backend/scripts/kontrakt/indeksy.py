"""Indeksy odwrotne kontraktu danych (generowane, nie edytować ręcznie w JSON-ach):

- `zmienne_uzytkownika.json` → `zmienne[].uzywane_w_regulach` (świadczenia i ryzyka używające zmiennej),
- `katalog_wnioskow_pdf.json` → `wnioski[].swiadczenia` i `wnioski[].ryzyka` (kto wskazuje dany wniosek).

Użycie (z katalogu backend/):  .venv/bin/python scripts/kontrakt/indeksy.py [--check]
`--check` tylko sprawdza zgodność (kod wyjścia 1 przy rozjeździe) — używane w testach.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "app" / "data"


def vars_of(expr, acc: set[str]) -> set[str]:
    """Wszystkie ścieżki `{"var": ...}` w wyrażeniu JSONLogic."""
    if isinstance(expr, dict):
        for k, v in expr.items():
            if k == "var":
                acc.add(v if isinstance(v, str) else v[0])
            else:
                vars_of(v, acc)
    elif isinstance(expr, list):
        for v in expr:
            vars_of(v, acc)
    return acc


def owning_key(path: str, known: set[str]) -> str | None:
    """`ubezpieczenie.zadluzenie_skladkowe.kwota` → `ubezpieczenie.zadluzenie_skladkowe` (najdłuższy znany klucz)."""
    parts = path.split(".")
    for n in range(len(parts), 0, -1):
        cand = ".".join(parts[:n])
        if cand in known:
            return cand
    return None


def compute(reguly: dict, zmienne: dict, katalog: dict) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
    known = {z["klucz"] for z in zmienne["zmienne"]}
    use: dict[str, set[str]] = {}

    def add(paths: set[str], owner: str) -> None:
        for p in paths:
            key = owning_key(p, known)
            if key:
                use.setdefault(key, set()).add(owner)

    for s in reguly["swiadczenia"]:
        for w in s["warunki"]:
            add(set(w.get("zmienne", [])) | vars_of(w["wyrazenie"], set()), s["id"])
        for i in s.get("informacje", []):
            add(set(i.get("zmienne", [])) | vars_of(i.get("warunek"), set()), s["id"])
        for w in s.get("wnioski", []):
            add(vars_of(w.get("warunek"), set()), s["id"])
    for r in reguly["ryzyka"]:
        add(vars_of(r["warunek"], set()), r["id"])

    by_code: dict[str, dict[str, set[str]]] = {}
    for s in reguly["swiadczenia"]:
        for w in s.get("wnioski", []):
            by_code.setdefault(w["kod"], {"swiadczenia": set(), "ryzyka": set()})["swiadczenia"].add(s["id"])
    for r in reguly["ryzyka"]:
        for kod in r.get("wnioski", []):
            by_code.setdefault(kod, {"swiadczenia": set(), "ryzyka": set()})["ryzyka"].add(r["id"])
    return (
        {k: sorted(v) for k, v in use.items()},
        {k: {kk: sorted(vv) for kk, vv in v.items()} for k, v in by_code.items()},
    )


def apply(reguly: dict, zmienne: dict, katalog: dict) -> list[str]:
    """Nadpisuje indeksy w obiektach; zwraca listę opisów zmian."""
    use, by_code = compute(reguly, zmienne, katalog)
    changes: list[str] = []
    for z in zmienne["zmienne"]:
        new = use.get(z["klucz"], [])
        old = z.get("uzywane_w_regulach") or []
        if sorted(old) != new:
            changes.append(f"zmienne {z['klucz']}: {old} -> {new}")
        if new:
            z["uzywane_w_regulach"] = new
        else:
            z.pop("uzywane_w_regulach", None)
    for w in katalog["wnioski"]:
        idx = by_code.get(w["kod"], {"swiadczenia": [], "ryzyka": []})
        for field in ("swiadczenia", "ryzyka"):
            new, old = idx[field], w.get(field) or []
            if sorted(old) != new:
                changes.append(f"katalog {w['kod']}.{field}: {old} -> {new}")
            if new:
                w[field] = new
            else:
                w.pop(field, None)
    return changes


def load() -> tuple[dict, dict, dict]:
    return tuple(json.loads((DATA / n).read_text(encoding="utf-8")) for n in (
        "reguly_uprawnien.json", "zmienne_uzytkownika.json", "katalog_wnioskow_pdf.json"))  # type: ignore[return-value]


COMPACT_KEYS = {"wyrazenie", "warunek"}  # wyrażenia JSONLogic w reguly_uprawnien.json trzymamy w jednej linii


def _dump_reguly(o, ind: int = 0, key: str | None = None) -> str:
    sp = "  "
    if key in COMPACT_KEYS:
        return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = [f"{sp * (ind + 1)}{json.dumps(k, ensure_ascii=False)}: {_dump_reguly(v, ind + 1, k)}" for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + sp * ind + "}"
    if isinstance(o, list):
        if not o:
            return "[]"
        return "[\n" + ",\n".join(f"{sp * (ind + 1)}{_dump_reguly(v, ind + 1)}" for v in o) + "\n" + sp * ind + "]"
    return json.dumps(o, ensure_ascii=False)


def dump(path: Path, obj: dict) -> None:
    """Zapis w formacie identycznym z repozytorium (reguły: wyrażenia JSONLogic w jednej linii)."""
    text = _dump_reguly(obj) if path.name == "reguly_uprawnien.json" else json.dumps(obj, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    reguly, zmienne, katalog = load()
    changes = apply(reguly, zmienne, katalog)
    if "--check" in sys.argv:
        for c in changes:
            print(c)
        return 1 if changes else 0
    dump(DATA / "zmienne_uzytkownika.json", zmienne)
    dump(DATA / "katalog_wnioskow_pdf.json", katalog)
    print("\n".join(changes) or "Indeksy aktualne.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
