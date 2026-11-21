"""Buduje lokalny indeks przepisów (`backend/app/data/laws/*.json`) z API Sejmu (ELI).

Dla każdego aktu z listy `ACTS` skrypt:
1. znajduje aktualny tekst jednolity (obwieszczenie Marszałka Sejmu) przez `…/eli/acts/search`
   (a gdy wyszukiwanie zawiedzie — używa przypiętego adresu `fallback`),
2. pobiera PDF (`…/text.pdf` — dla najnowszych tekstów HTML bywa niedostępny),
3. czyści nagłówki/stopki stron, dzieli tekst po „Art. N.” i zapisuje JSON z fragmentami (chunkami).

Użycie (z katalogu `backend/`, wymaga sieci):

    .venv/bin/python scripts/build_laws_index.py            # wszystkie akty
    .venv/bin/python scripts/build_laws_index.py kp zasilkowa

Gdy sieć jest niedostępna, nie nadpisuje istniejących plików — zostają dane już zacommitowane.
Uwaga: to skrót do wyszukiwania pomocniczego, nie porada prawna; użytkownik zawsze dostaje link do aktu.
"""

from __future__ import annotations

import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from pypdf import PdfReader

API = "https://api.sejm.gov.pl/eli"
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "laws"


@dataclass(frozen=True)
class Act:
    key: str
    short: str  # krótka nazwa do cytowania, np. „Kodeks pracy”
    title_phrase: str  # fragment tytułu obwieszczenia o tekście jednolitym
    fallback: str  # przypięty adres ELI tekstu jednolitego (stan na 2026-11-21)
    divisions: tuple[str, ...] = ()  # jeśli niepusto: tylko artykuły z tych działów (nagłówek „DZIAŁ …”)
    art_range: tuple[int, int] | None = None  # jeśli ustawione: tylko artykuły o numerze bazowym w zakresie


ACTS: tuple[Act, ...] = (
    Act(
        "kp",
        "Kodeks pracy",
        "Kodeks pracy",
        "DU/2026/1245",
        divisions=("DZIAŁ ÓSMY",),  # uprawnienia pracowników związane z rodzicielstwem
    ),
    Act(
        "zasilkowa",
        "ustawa zasiłkowa",
        "ustawy o świadczeniach pieniężnych z ubezpieczenia społecznego w razie choroby i macierzyństwa",
        "DU/2026/854",
    ),
    Act(
        "rodzinne",
        "ustawa o świadczeniach rodzinnych",
        "ustawy o świadczeniach rodzinnych",
        "DU/2026/1240",
    ),
    Act(
        "800plus",
        "ustawa o pomocy państwa w wychowywaniu dzieci (800+)",
        "ustawy o pomocy państwa w wychowywaniu dzieci",
        "DU/2026/508",
    ),
    Act(
        "oswiatowe",
        "Prawo oświatowe (rekrutacja)",
        "Prawo oświatowe",
        "DU/2026/820",
        art_range=(130, 170),  # rozdział o przyjmowaniu do publicznych przedszkoli i szkół
    ),
    Act(
        "zlobki",
        "ustawa o opiece nad dziećmi w wieku do lat 3",
        "ustawy o opiece nad dziećmi w wieku do lat 3",
        "DU/2025/798",
    ),
    Act(
        "zazyciem",
        "ustawa „Za życiem”",
        "wsparciu kobiet w ciąży i rodzin",
        "DU/2024/1829",
    ),
    Act(
        "kdr",
        "ustawa o Karcie Dużej Rodziny",
        "ustawy o Karcie Dużej Rodziny",
        "DU/2024/1512",
    ),
)

_HEADER_RE = re.compile(r"^Dziennik Ustaw\s*[–-]\s*\d+\s*[–-]\s*Poz\.\s*\d+\s*$")
_ART_RE = re.compile(r"^Art\.\s+(\d+(?:\[\d+\])?[a-z]{0,2})\.\s*(.*)$")
_DIVISION_RE = re.compile(r"^DZIAŁ\s+[A-ZĄĆĘŁŃÓŚŹŻ ]+$")
_FOOTNOTE_RE = re.compile(
    r"^\d{1,3}\)\s+(Niniejsza ustawa|Zmiany tekstu jednolitego|Dane dotyczące ogłoszenia|Zmiany wymienionej ustawy)"
)


_PL = "A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ"
_WORD_RE = re.compile(rf"[{_PL}]+")
# PDF Sejmu wstawia czasem spację przed polskim znakiem w środku wyrazu („macierzy ńskiego”).
_SPLIT_SURE_RE = re.compile(rf"(?<=[{_PL}]) ([ąęń])(?=[{_PL}])")  # żaden polski wyraz nie zaczyna się od ą/ę/ń
_SPLIT_TRAIL_RE = re.compile(rf"(?<=[{_PL}]) ([ąćęłńóśźż])(?![{_PL}])")  # samotny znak diakrytyczny po wyrazie
_SPLIT_MAYBE_RE = re.compile(rf"([{_PL}]+) ([ćłóśźż][{_PL}]*)")  # niejednoznaczne: sprawdzamy słownikiem


_FUNCTION_WORDS = frozenset(
    "i u w z o a do na po za ze od lub oraz że dla przy nad pod bez przez albo jak czy to się nie ich jego jej są był".split()
)


def build_vocab(texts: list[str]) -> set[str]:
    """Wszystkie prefiksy (4–12 znaków) wyrazów korpusu — do rozstrzygania niejednoznacznych podziałów."""
    vocab: set[str] = set()
    for text in texts:
        for word in _WORD_RE.findall(text):
            word = word.lower()
            vocab.update(word[:n] for n in range(4, min(len(word), 12) + 1))
    return vocab


def repair_diacritics(text: str, vocab: set[str]) -> str:
    text = _SPLIT_SURE_RE.sub(r"", text)
    text = _SPLIT_TRAIL_RE.sub(r"", text)

    def maybe(m: re.Match[str]) -> str:
        head, tail = m.group(1), m.group(2)
        if head.lower() in _FUNCTION_WORDS:
            return m.group(0)  # „do świadczenia”, „w życie” — to dwa wyrazy
        joined = (head + tail).lower()
        # łączymy, gdy złożony początek (głowa + 3 znaki) jest początkiem jakiegoś wyrazu w korpusie
        if joined[: len(head) + 3] in vocab:
            return head + tail
        return m.group(0)

    return _SPLIT_MAYBE_RE.sub(maybe, text)


def repair_directory(directory: Path = OUT_DIR) -> None:
    """Naprawia podziały wyrazów we wszystkich plikach (słownik z całego korpusu). Idempotentne."""
    files = sorted(directory.glob("*.json"))
    datas = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    vocab = build_vocab([c["text"] for d in datas for c in d["chunks"]])
    for f, d in zip(files, datas):
        for c in d["chunks"]:
            c["text"] = repair_diacritics(c["text"], vocab)
        f.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def resolve_eli(client: httpx.Client, act: Act) -> str:
    """Zwraca adres ELI (np. `DU/2026/1245`) aktualnego tekstu jednolitego; przy błędzie — `fallback`."""
    try:
        r = client.get(
            f"{API}/acts/search",
            params={
                "title": act.title_phrase,
                "publisher": "DU",
                "type": "Obwieszczenie",
                "limit": 10,
                "sortBy": "announcementDate",
                "sortDir": "desc",
            },
        )
        r.raise_for_status()
        for item in r.json().get("items", []):
            title = item.get("title", "")
            if (
                item.get("status") == "obowiązujący"
                and item.get("textPDF")
                and "jednolitego tekstu" in title
                and act.title_phrase in title
            ):
                return f"{item['publisher']}/{item['year']}/{item['pos']}"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        print(f"  ! wyszukiwanie ELI nie powiodło się ({type(e).__name__}), używam {act.fallback}")
    return act.fallback


def fetch_pdf_text(client: httpx.Client, eli: str) -> str:
    r = client.get(f"{API}/acts/{eli}/text.pdf", follow_redirects=True, timeout=180)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def clean_lines(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or _HEADER_RE.match(line) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
            continue
        if _FOOTNOTE_RE.match(line):
            continue
        lines.append(line)
    return lines


def _join(lines: list[str]) -> str:
    out = ""
    for line in lines:
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line  # dzielenie wyrazu na końcu wiersza
        else:
            out = f"{out} {line}" if out else line
    return re.sub(r"\s+", " ", out).strip()


def base_number(article: str) -> int:
    return int(re.match(r"\d+", article).group())


def split_articles(lines: list[str], act: Act) -> list[tuple[str, str]]:
    """Zwraca listę `(numer artykułu, tekst)` zgodnie z filtrami aktu (działy / zakres numerów)."""
    # Obwieszczenie zaczyna się od preambuły (wykaz zmian) — właściwy tekst ustawy zaczyna się od „Art. 1.”.
    start = next((i for i, line in enumerate(lines) if re.match(r"^Art\.\s+1\.", line)), 0)
    lines = lines[start:]
    division = ""
    current: tuple[str, list[str], str] | None = None  # (artykuł, wiersze, dział)
    found: list[tuple[str, list[str], str]] = []
    for line in lines:
        if _DIVISION_RE.match(line):
            division = line
            current = None
            continue
        m = _ART_RE.match(line)
        if m:
            current = (m.group(1), [f"Art. {m.group(1)}. {m.group(2)}".strip()], division)
            found.append(current)
            continue
        if current is not None:
            current[1].append(line)
    result = []
    seen: set[str] = set()
    for article, body, div in found:
        if act.divisions and div not in act.divisions:
            continue
        if act.art_range and not act.art_range[0] <= base_number(article) <= act.art_range[1]:
            continue
        if article in seen:  # powtórzenia (np. spis treści / przepisy zmieniające) — zostaje pierwsze wystąpienie
            continue
        seen.add(article)
        text = _join(body)
        if len(text) > 40:
            result.append((article, text))
    return result


def isap_url(eli: str) -> str:
    publisher, year, pos = eli.split("/")
    return f"https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=W{publisher}{year}{int(pos):07d}"


def build(client: httpx.Client, act: Act) -> dict:
    eli = resolve_eli(client, act)
    print(f"{act.key}: {eli}")
    lines = clean_lines(fetch_pdf_text(client, eli))
    articles = split_articles(lines, act)
    if not articles:
        raise RuntimeError(f"{act.key}: nie znaleziono artykułów (zmiana formatu PDF?)")
    url = isap_url(eli)
    chunks = [
        {
            "id": f"{act.key}-art-{article}",
            "act": act.short,
            "act_short": act.short,
            "article": f"Art. {article}",
            "text": text,
            "url": url,
        }
        for article, text in articles
    ]
    print(f"  {len(chunks)} artykułów")
    return {"key": act.key, "act": act.short, "eli": eli, "url": url, "retrieved": date.today().isoformat(), "chunks": chunks}


def main(keys: list[str]) -> int:
    selected = [a for a in ACTS if not keys or a.key in keys]
    if not selected:
        print(f"Nieznane akty: {keys}. Dostępne: {[a.key for a in ACTS]}")
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status = 0
    with httpx.Client(timeout=60, headers={"User-Agent": "mrodzina-laws-index/1.0"}) as client:
        for act in selected:
            try:
                data = build(client, act)
            except (httpx.HTTPError, RuntimeError) as e:
                print(f"  ! {act.key}: {type(e).__name__}: {e} — plik bez zmian")
                status = 1
                continue
            (OUT_DIR / f"{act.key}.json").write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
    repair_directory()
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
