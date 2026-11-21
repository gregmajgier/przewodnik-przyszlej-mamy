#!/usr/bin/env python
"""Buduje indeks przepisów (backend/app/data/laws/*.json) z oficjalnego API Sejmu (ELI).

Użycie (z katalogu backend/):
    .venv/bin/pip install pdfplumber            # tylko do budowy indeksu, nie do działania aplikacji
    .venv/bin/python scripts/build_laws_index.py [--discover] [--only kp,zasilkowa] [--cache DIR]

Dla każdego aktu skrypt:
  1. sprawdza w API ELI (https://api.sejm.gov.pl/eli/acts/DU/{rok}/{poz}), czy przypięte obwieszczenie
     o tekście jednolitym jest nadal obowiązujące (`--discover` wybiera najnowsze obowiązujące z wyszukiwarki),
  2. pobiera tekst (HTML, a gdy API go nie udostępnia — PDF `text.pdf`; dla aktualnych obwieszczeń
     API zwykle ma tylko PDF),
  3. dzieli go na artykuły („Art. N.”), odrzuca przypisy, nagłówki stron i brzmienia, które dopiero wejdą
     w życie (tekst jednolity drukuje obok siebie brzmienie obecne i przyszłe),
  4. zapisuje JSON z fragmentami (`LawChunk`) i metadanymi źródła.

Nie wymyślamy treści: wszystko pochodzi z pobranego tekstu. Wynik trzeba zacommitować; po każdej zmianie
przepisów uruchom skrypt ponownie.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://api.sejm.gov.pl/eli"
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "laws"
MAX_CHUNK_CHARS = 2400

# key, nazwa, skrót, zapytanie do wyszukiwarki, przypięte (rok, pozycja) obwieszczenia, filtr nagłówków (regex)
ACTS = [
    {
        "key": "kp",
        "act": "Kodeks pracy",
        "short": "KP",
        "query": "Kodeks pracy",
        "pinned": (2026, 1245),
        # dział VIII: uprawnienia pracowników związane z rodzicielstwem
        "headings": r"^DZIAŁ ÓSMY$",
    },
    {
        "key": "zasilkowa",
        "act": "Ustawa o świadczeniach pieniężnych z ubezpieczenia społecznego w razie choroby i macierzyństwa (zasiłkowa)",
        "short": "ustawa zasiłkowa",
        "query": "ustawy o świadczeniach pieniężnych z ubezpieczenia społecznego w razie choroby i macierzyństwa",
        "pinned": (2026, 854),
    },
    {
        "key": "swiadczenia-rodzinne",
        "act": "Ustawa o świadczeniach rodzinnych",
        "short": "ustawa o świadczeniach rodzinnych",
        "query": "ustawy o świadczeniach rodzinnych",
        "pinned": (2026, 1240),
    },
    {
        "key": "800plus",
        "act": "Ustawa o pomocy państwa w wychowywaniu dzieci (800+)",
        "short": "ustawa 800+",
        "query": "ustawy o pomocy państwa w wychowywaniu dzieci",
        "pinned": (2026, 508),
    },
    {
        "key": "prawo-oswiatowe",
        "act": "Prawo oświatowe (rekrutacja i obowiązek przedszkolny)",
        "short": "Prawo oświatowe",
        "query": "ustawy - Prawo oświatowe",
        "pinned": (2026, 820),
        # rozdz. 2: wychowanie przedszkolne i obowiązek szkolny; rozdz. 6: zasady rekrutacji do przedszkoli i szkół
        "headings": r"(?i)^rozdział (2|6)$",
    },
    {
        "key": "zlobki",
        "act": "Ustawa o opiece nad dziećmi w wieku do lat 3",
        "short": "ustawa żłobkowa",
        "query": "ustawy o opiece nad dziećmi w wieku do lat 3",
        "pinned": (2025, 798),
    },
    {
        "key": "za-zyciem",
        "act": "Ustawa o wsparciu kobiet w ciąży i rodzin „Za życiem”",
        "short": "ustawa „Za życiem”",
        "query": "ustawy o wsparciu kobiet w ciąży i rodzin",
        "pinned": (2024, 1829),
    },
    {
        "key": "kdr",
        "act": "Ustawa o Karcie Dużej Rodziny",
        "short": "ustawa o Karcie Dużej Rodziny",
        "query": "ustawy o Karcie Dużej Rodziny",
        "pinned": (2024, 1512),
    },
]

SUPERSCRIPT = str.maketrans("0123456789abcdefghijklmnoprstuvwxyz", "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")
UNSUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ", "0123456789abcdefghijklmnoprstuvwxyz")
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
    "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
FUTURE_RE = re.compile(r"wejd(?:zie|ą) w życie\s+z dniem\s+(\d{1,2})\s+(\w+)\s+(\d{4})")
OBSOLETE_RE = re.compile(r"obowiązuje do wejścia w życie zmiany, o której mowa w odnośniku\s+(\d+)")
MARK_OPEN, MARK_CLOSE = "", ""  # znaczniki odnośników do przypisów (prywatny obszar Unicode)
SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ"
ART_RE = re.compile(rf"^Art\.\s*(\d+[{SUP}]*[a-z]{{0,3}}[{SUP}]*)\s*\.\s*(.*)$", re.S)
UNIT_START_RE = re.compile(rf"^(Art\.\s|§\s*\d|\d+[a-z]{{0,3}}[{SUP}]*\.\s|\d+[a-z]{{0,3}}\)\s|[a-z]{{1,2}}\)\s|[-–‒]\s)")
HEADING_START_RE = re.compile(r"^(DZIAŁ|Dział|ROZDZIAŁ|Rozdział|Oddział|ODDZIAŁ)\b")


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mrodzina-laws-index/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 - stały host api.sejm.gov.pl
        return r.read()


def get_json(path: str, **params) -> dict:
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    return json.loads(http_get(f"{API}{path}{query}"))


def resolve_act(spec: dict, discover: bool) -> dict:
    """Zwraca metadane obwieszczenia z tekstem jednolitym (obowiązującego)."""
    year, pos = spec["pinned"]
    meta = get_json(f"/acts/DU/{year}/{pos}")
    if discover or meta.get("status") != "obowiązujący":
        found = get_json(
            "/acts/search",
            title=f"jednolitego tekstu {spec['query']}",
            publisher="DU",
            type="Obwieszczenie",
            limit=10,
        )
        current = [a for a in found["items"] if a.get("status") == "obowiązujący"]
        if not current:
            raise SystemExit(f"Brak obowiązującego tekstu jednolitego dla: {spec['act']}")
        current.sort(key=lambda a: (a["year"], a["pos"]), reverse=True)
        meta = current[0]
        print(f"  przypięty tekst nieaktualny/--discover: używam {meta['year']}/{meta['pos']}", file=sys.stderr)
    return meta


# --- ekstrakcja z PDF --------------------------------------------------------------------------


def _superscript_text(run: list[dict]) -> str:
    out = []
    for c in run:
        t = c["text"]
        if t in "[]":  # część aktów drukuje indeks górny jako „[1]”
            continue
        out.append(t.translate(SUPERSCRIPT) if t.strip() else "")
    return "".join(out)


def _prepare_chars(page, today: date) -> dict[str, bool]:
    """Przygotowuje znaki strony do zbudowania tekstu: usuwa ciała przypisów i nagłówki, zamienia indeksy
    górne na cyfry unikodowe, a odnośniki do przypisów na znaczniki. Zwraca {numer przypisu: przyszłe?}."""
    chars = page.chars
    footnotes: dict[int, list[str]] = {}
    current_fn: int | None = None
    # 1) ciała przypisów (rozmiar ~9 pkt, odnośnik 6 pkt) — zbieramy tekst, by ocenić przyszłe brzmienia
    fn_lines: dict[float, list[dict]] = {}
    for c in chars:
        if 8.0 <= c["size"] < 9.5 or c["size"] < 6.3:
            fn_lines.setdefault(round(c["top"]), []).append(c)
    for top in sorted(fn_lines):
        line = "".join(c["text"] for c in sorted(fn_lines[top], key=lambda c: c["x0"]))
        m = re.match(r"^(\d{1,3})\)(.*)$", line.strip())
        if m:
            current_fn = int(m.group(1))
            footnotes[current_fn] = [m.group(2)]
        elif current_fn is not None:
            footnotes[current_fn].append(line)
    # Tekst jednolity drukuje obok siebie brzmienie dotychczasowe i nowe. Odrzucamy: (a) brzmienia, które
    # dopiero wejdą w życie („wejdzie w życie z dniem D”, D > dziś) oraz (b) brzmienia przestarzałe
    # („w tym brzmieniu obowiązuje do wejścia w życie zmiany, o której mowa w odnośniku K”, gdy zmiana K już weszła).
    texts = {n: re.sub(r"\s+", " ", " ".join(parts)).strip() for n, parts in footnotes.items()}
    dates: dict[int, date] = {}
    for n, text in texts.items():
        found = [
            date(int(y), MONTHS[mon], int(d)) for d, mon, y in FUTURE_RE.findall(text) if mon in MONTHS
        ]
        if found:
            dates[n] = found[-1]
    future: dict[str, bool] = {}
    for n, text in texts.items():
        flagged = n in dates and dates[n] > today
        m = OBSOLETE_RE.search(text)
        if m and int(m.group(1)) in texts:
            k = int(m.group(1))
            # zmiana K już weszła w życie: albo ma datę <= dziś, albo przypis nie zapowiada przyszłej daty
            if not (k in dates and dates[k] > today):
                flagged = True
        future[str(n)] = flagged
    # 2) zmiany w znakach głównego tekstu
    i = 0
    n_chars = len(chars)
    while i < n_chars:
        c = chars[i]
        size = c["size"]
        if size >= 9.5:
            i += 1
            continue
        if 8.0 <= size < 9.5 or size < 6.3:
            c["text"] = ""  # przypis/nagłówek — usuwane
            i += 1
            continue
        # indeks górny (≈6,5 pkt): zbierz ciągły przebieg
        j = i
        while j < n_chars and 6.3 <= chars[j]["size"] < 8.0:
            j += 1
        run = chars[i:j]
        joined = "".join(r["text"] for r in run)
        if joined.endswith(")"):
            num = joined[:-1].strip()
            run[0]["text"] = f"{MARK_OPEN}{num}{MARK_CLOSE}"
            for r in run[1:]:
                r["text"] = ""
        else:
            text = _superscript_text(run)
            run[0]["text"] = text
            for r in run[1:]:
                r["text"] = ""
        i = j
    return future


def pdf_lines(pdf_bytes: bytes, today: date) -> list[dict]:
    """Lista linii: {text, x0, x1, bold, future, width}. Odrzuca przypisy i nagłówki stron."""
    import pdfplumber

    lines: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            future = _prepare_chars(page, today)
            body = page.filter(lambda o: o.get("object_type") != "char" or o.get("text") != "")
            for ln in body.extract_text_lines(x_tolerance=1.5, y_tolerance=4, return_chars=True):
                text = ln["text"]
                if re.match(r"^Dziennik Ustaw\s+–\s+\d+\s+–\s+Poz\.", text.strip()):
                    continue
                letters = [c for c in ln["chars"] if c["text"].isalpha()]
                bold = (sum("Bold" in c["fontname"] for c in letters) / len(letters)) if letters else 0.0
                has_future = any(future.get(n, False) for n in re.findall(f"{MARK_OPEN}(\\d+){MARK_CLOSE}", text))
                text = re.sub(f"{MARK_OPEN}\\d+{MARK_CLOSE}", "", text)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    lines.append(
                        {"text": text, "x0": ln["x0"], "x1": ln["x1"], "bold": bold, "future": has_future,
                         "width": float(page.width)}
                    )
    return lines


def _is_heading(line: dict) -> bool:
    centred = abs((line["x0"] + line["x1"]) / 2 - line["width"] / 2) < 20 and line["x0"] > 110
    return centred and (line["bold"] > 0.9 or bool(HEADING_START_RE.match(line["text"])))


# Oficjalny PDF drukuje w tych miejscach wyrazy bez odstępu (nie jest to błąd ekstrakcji).
GLUED = {"niewięcej": "nie więcej", "niepóźniej": "nie później"}


def _join(parts: list[str]) -> str:
    out = ""
    for p in parts:
        if out.endswith("-") and out[-2:-1].isalpha() and p[:1].islower():
            out = out[:-1] + p  # dzielenie wyrazu na końcu wiersza
        else:
            out = f"{out} {p}" if out else p
    for glued, fixed in GLUED.items():
        out = out.replace(glued, fixed)
    return out


def articles_from_lines(lines: list[dict], heading_filter: str | None) -> list[dict]:
    """Dzieli linie na artykuły. Zwraca [{article, text, headings}] z pominięciem brzmień przyszłych."""
    heading_re = re.compile(heading_filter) if heading_filter else None
    path: list[str] = []  # bieżące nagłówki (dział, rozdział, tytuł)
    current: dict | None = None
    units: list[dict] = []  # akapity bieżącego artykułu: {parts, future}
    result: list[dict] = []

    def close_article() -> None:
        nonlocal current, units
        if current is not None:
            kept = [u for u in units if not u["future"]]
            body = "\n".join(_join(u["parts"]) for u in kept).strip()
            if body and not re.fullmatch(r"\(?(uchylony|uchylona)\)?\.?", body.strip()):
                result.append({"article": current["article"], "text": f"Art. {current['article']}. {body}",
                               "headings": list(current["headings"])})
        current, units = None, []

    started = False  # pomijamy treść obwieszczenia przed „USTAWA …”
    after_heading = False  # kolejne pogrubione linie po „Rozdział N” to jego tytuł (także niewyśrodkowane)
    title_open = False
    for line in lines:
        text = line["text"]
        if not started:
            if re.match(r"^USTAWA\b", text):
                started = True
            continue
        is_title = after_heading and line["bold"] > 0.9 and not text.startswith("Art.")
        if _is_heading(line) or is_title:
            close_article()
            if HEADING_START_RE.match(text):
                rank = {"DZIAŁ": 0, "ROZDZIAŁ": 1, "ODDZIAŁ": 2}[text.split()[0].upper()]
                path = path[:rank] + [text]  # nowy nagłówek ucina niższe poziomy
                title_open = True
            elif title_open and path:
                path[-1] = f"{path[-1]} > {text}" if ">" not in path[-1] else f"{path[-1]} {text}"
            after_heading = True
            continue
        after_heading = False
        title_open = False
        m = ART_RE.match(text) if text.startswith("Art.") else None
        if m and line["x0"] < 100:
            close_article()
            allowed = heading_re is None or any(heading_re.search(h.split(" > ")[0]) for h in path)
            if allowed:
                current = {"article": m.group(1).replace(" ", ""), "headings": path[:]}
                units = [{"parts": [m.group(2)] if m.group(2) else [], "future": line["future"]}]
            continue
        if current is None:
            continue
        if UNIT_START_RE.match(text) and line["x0"] > 60:
            units.append({"parts": [text], "future": line["future"]})
        else:
            if line["future"]:
                units[-1]["future"] = True
            units[-1]["parts"].append(text)
    close_article()
    return result


def chunk_article(art: dict, act_key: str, act: str, short: str, url: str) -> list[dict]:
    """Jeden fragment na artykuł; długie artykuły dzielone na granicach akapitów (te same `article`, kolejne id)."""
    paragraphs = art["text"].split("\n")
    pieces: list[str] = []
    buf = ""
    for p in paragraphs:
        if buf and len(buf) + len(p) + 1 > MAX_CHUNK_CHARS:
            pieces.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        pieces.append(buf)
    base = "".join(f"p{c.translate(UNSUP)}" if c in SUP else c for c in art["article"])
    out = []
    for i, piece in enumerate(pieces, 1):
        out.append(
            {
                "id": f"{act_key}-art-{base}" + (f"-{i}" if len(pieces) > 1 else ""),
                "act": act,
                "act_short": short,
                "article": f"Art. {art['article']}",
                "text": piece if i == 1 else f"(ciąg dalszy art. {art['article']}) {piece}",
                "url": url,
            }
        )
    return out


def build_act(spec: dict, discover: bool, cache: Path | None, today: date) -> dict:
    meta = resolve_act(spec, discover)
    year, pos = meta["year"], meta["pos"]
    print(f"{spec['act']}: Dz.U. {year} poz. {pos} ({meta.get('status')})", file=sys.stderr)
    cache_file = cache / f"{year}_{pos}.pdf" if cache else None
    if cache_file and cache_file.exists():
        pdf = cache_file.read_bytes()
    else:
        pdf = http_get(f"{API}/acts/DU/{year}/{pos}/text.pdf")
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(pdf)
    lines = pdf_lines(pdf, today)
    arts = articles_from_lines(lines, spec.get("headings"))
    address = meta["address"]
    url = f"https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id={address}"
    chunks: list[dict] = []
    for a in arts:
        chunks.extend(chunk_article(a, spec["key"], spec["act"], spec["short"], url))
    print(f"  artykułów: {len(arts)}, fragmentów: {len(chunks)}", file=sys.stderr)
    return {
        "act": spec["act"],
        "act_short": spec["short"],
        "source": {
            "publisher": "DU",
            "year": year,
            "pos": pos,
            "title": meta.get("title"),
            "legal_status_date": meta.get("legalStatusDate"),
            "url": url,
            "built_on": today.isoformat(),
            "origin": "api.sejm.gov.pl/eli (text.pdf)",
        },
        # tekst wyodrębniony automatycznie z PDF: przed wykorzystaniem w decyzji sprawdź w ISAP (source.url)
        "verify": True,
        "chunks": chunks,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true", help="wybierz najnowsze obowiązujące obwieszczenia")
    ap.add_argument("--only", help="lista kluczy aktów po przecinku")
    ap.add_argument("--cache", type=Path, help="katalog na pobrane PDF-y (przyspiesza ponowne uruchomienia)")
    args = ap.parse_args()
    wanted = set(args.only.split(",")) if args.only else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in ACTS:
        if wanted and spec["key"] not in wanted:
            continue
        data = build_act(spec, args.discover, args.cache, date.today())
        (OUT_DIR / f"{spec['key']}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
