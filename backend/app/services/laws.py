"""Lokalny indeks przepisów: BM25 własnej implementacji (bez nowych zależności).

Normalizacja pod język polski: małe litery, bez ogonków (ł → l), tokeny alfanumeryczne i prosty stemming
prefiksowy (pierwsze 5 znaków), dzięki czemu „macierzyński”, „macierzyńskiego” i „macierzyństwo” się spotykają.
Dane pochodzą z `app/data/laws/*.json` (wynik `scripts/build_laws_index.py`).
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

LAWS_DIR = Path(__file__).resolve().parent.parent / "data" / "laws"
STEM_LEN = 5
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {"i", "w", "z", "na", "do", "o", "po", "za", "ze", "sie", "nie", "oraz", "lub", "albo", "jak", "co", "ile", "czy", "jest", "to", "dla", "od", "przez", "przy", "ktory", "ktora", "ktore"}
)


class LawChunk(BaseModel):
    id: str
    act: str
    act_short: str
    article: str
    text: str
    url: str


class LawIndex(Protocol):
    def search(self, query: str, k: int = 5) -> list[LawChunk]: ...


def normalize(text: str) -> str:
    text = text.lower().replace("ł", "l")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Tokeny po normalizacji i obcięciu do prefiksu; pomija słowa funkcyjne."""
    tokens = []
    for tok in _TOKEN_RE.findall(normalize(text)):
        if tok in _STOPWORDS:
            continue
        tokens.append(tok[:STEM_LEN])
    return tokens


class LocalLawIndex:
    """BM25 (k1=1.5, b=0.75) po fragmentach przepisów. Wynik: najlepsze `k` fragmentów, bez zerowych."""

    K1 = 1.5
    B = 0.75

    def __init__(self, chunks: list[LawChunk]) -> None:
        self.chunks = list(chunks)
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        df: Counter[str] = Counter()
        for chunk in self.chunks:
            # numer artykułu też jest wyszukiwalny („art 180”)
            tokens = tokenize(f"{chunk.article} {chunk.text}")
            counts = Counter(tokens)
            self._tf.append(counts)
            self._len.append(len(tokens))
            df.update(counts.keys())
        n = len(self.chunks)
        self._avg = (sum(self._len) / n) if n else 0.0
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @property
    def acts(self) -> set[str]:
        return {c.act_short for c in self.chunks}

    def search(self, query: str, k: int = 5) -> list[LawChunk]:
        terms = tokenize(query)
        if not terms or not self.chunks or k <= 0:
            return []
        scored: list[tuple[float, int]] = []
        for i, counts in enumerate(self._tf):
            norm = 1 - self.B + self.B * (self._len[i] / self._avg if self._avg else 1)
            score = 0.0
            for term in terms:
                tf = counts.get(term)
                if not tf:
                    continue
                score += self._idf[term] * tf * (self.K1 + 1) / (tf + self.K1 * norm)
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda s: (-s[0], s[1]))  # stabilnie: remis -> kolejność w indeksie
        return [self.chunks[i] for _, i in scored[:k]]


def load_chunks(directory: Path = LAWS_DIR) -> list[LawChunk]:
    chunks: list[LawChunk] = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks.extend(LawChunk.model_validate(c) for c in data["chunks"])
    return chunks


@lru_cache(maxsize=1)
def load_default_index() -> LocalLawIndex:
    return LocalLawIndex(load_chunks())
