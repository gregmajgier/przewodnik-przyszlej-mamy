"""Indeks przepisów: wyszukiwanie BM25 po fragmentach (artykułach) oficjalnych aktów prawnych.

Dane powstają ze skryptu `scripts/build_laws_index.py` (API ELI Sejmu) i leżą w `app/data/laws/*.json`.
Wyszukiwarka jest własna (bez nowych zależności): normalizacja polskich znaków, prosty stemming
prefiksowy (pierwsze 5 znaków) i BM25.
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

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ", "0123456789abcdefghijklmnoprstuvwxyz")
_STOPWORDS = frozenset(
    "i w z o a na do dla po od za u nie sie jest lub albo oraz ze czy to ten ta te przez ktory ktora ktore "
    "jak co mi mnie moje moja mam ma sa byc bylo".split()
)
_CONTINUATION_RE = re.compile(r"^\(ciąg dalszy art\.[^)]*\)\s*")
_ARTICLE_RE = re.compile(r"\bart(?:ykul|\.)?\s*(\d+[a-z]?)\b")


class LawChunk(BaseModel):
    id: str
    act: str
    act_short: str
    article: str  # np. „Art. 180”
    text: str
    url: str


class LawIndex(Protocol):
    def search(self, query: str, k: int = 5) -> list[LawChunk]: ...


def _fold(text: str) -> str:
    """Małe litery, bez ogonków (także ł), indeksy górne jako zwykłe znaki."""
    text = text.translate(_SUPERSCRIPTS).lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9]+", _fold(text)):
        if tok in _STOPWORDS or (len(tok) < 2 and not tok.isdigit()):
            continue
        tokens.append(tok[:STEM_LEN])
    return tokens


def _article_key(article: str) -> str:
    return _fold(article).replace("art.", "").replace(" ", "")


class LocalLawIndex:
    """BM25 po fragmentach; bez wyników, gdy zapytanie nie ma żadnego pasującego terminu."""

    K1 = 1.5
    B = 0.4

    def __init__(self, chunks: list[LawChunk]) -> None:
        self.chunks = list(chunks)
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        df: Counter[str] = Counter()
        for c in self.chunks:
            terms = tokenize(_CONTINUATION_RE.sub("", c.text))
            tf = Counter(terms)
            self._tf.append(tf)
            self._len.append(len(terms))
            df.update(tf.keys())
        n = max(1, len(self.chunks))
        self._avg = (sum(self._len) / n) or 1.0
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._article_keys = [_article_key(c.article) for c in self.chunks]

    def search(self, query: str, k: int = 5) -> list[LawChunk]:
        terms = tokenize(query or "")
        if not terms or k <= 0:
            return []
        wanted_articles = set(_ARTICLE_RE.findall(_fold(query)))
        scored: list[tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if not f:
                    continue
                denom = f + self.K1 * (1 - self.B + self.B * self._len[i] / self._avg)
                score += self._idf.get(t, 0.0) * f * (self.K1 + 1) / denom
            if score <= 0:
                continue
            if self._article_keys[i] in wanted_articles:
                score *= 3  # zapytanie wprost o numer artykułu
            scored.append((score, i))
        scored.sort(key=lambda s: (-s[0], s[1]))  # remis: kolejność w indeksie (stabilnie)
        return [self.chunks[i] for _, i in scored[:k]]


@lru_cache(maxsize=1)
def load_default_index() -> LocalLawIndex:
    chunks: list[LawChunk] = []
    for path in sorted(LAWS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks.extend(LawChunk.model_validate(c) for c in data["chunks"])
    return LocalLawIndex(chunks)
