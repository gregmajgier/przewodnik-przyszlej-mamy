"""Wyszukiwanie w sieci dla informacji lokalnych i bieżących (czat, narzędzie `szukaj_w_sieci`).

Dostawca z `WEB_SEARCH_PROVIDER` (`none` | `brave` | `serper`), klucz w `WEB_SEARCH_API_KEY`. Domyślnie `none`
— czat wtedy uczciwie mówi, że nie ma dostępu do wyszukiwarki. Błąd dostawcy nigdy nie jest wyjątkiem: zwracamy
pustą listę (czat odpowie bez sieci). Nie logujemy zapytań (mogą zawierać dane rodziny).
"""

from __future__ import annotations

import logging
import re
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger("mrodzina.web_search")

TIMEOUT_S = 10.0
MAX_TITLE = 200
MAX_SNIPPET = 400

# Poddomeny/etykiety typowe dla jednostek publicznych (urząd miasta/gminy, BIP, PUP, ośrodki pomocy).
_OFFICIAL_LABELS = frozenset("bip um umig ug ugm starostwo pup mops mopr gops ops gok powiat urzad".split())
_OFFICIAL_SUFFIXES = ("gov.pl", "zus.pl")


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearch(Protocol):
    async def search(self, query: str, k: int = 5) -> list[WebResult]: ...


def is_official(url: str) -> bool:
    """Czy domena wygląda na urzędową: *.gov.pl, zus.pl, BIP, urząd miasta/gminy (um., ug.), PUP, OPS."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not host:
        return False
    for suffix in _OFFICIAL_SUFFIXES:
        if host == suffix or host.endswith("." + suffix):
            return True
    labels = host.split(".")
    if len(labels) < 3:  # sama „domena.pl” nie jest dowodem urzędowości
        return False
    return any(label in _OFFICIAL_LABELS for label in labels[:-2])


def rank_official(results: list[WebResult]) -> list[WebResult]:
    """Domeny urzędowe najpierw; kolejność wewnątrz klasy bez zmian (sortowanie stabilne)."""
    return sorted(results, key=lambda r: 0 if is_official(r.url) else 1)


_TAG_RE = re.compile(r"<[^>]*>")


def _clean(text: object, limit: int) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", str(text or ""))).strip()[:limit]


def _result(title: object, url: object, snippet: object) -> WebResult | None:
    url = str(url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return WebResult(title=_clean(title, MAX_TITLE), url=url, snippet=_clean(snippet, MAX_SNIPPET))


class NoneSearch:
    async def search(self, query: str, k: int = 5) -> list[WebResult]:
        return []


class _HttpSearch:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client

    async def _request(self, client: httpx.AsyncClient, query: str, k: int) -> list[tuple[object, object, object]]:
        raise NotImplementedError

    async def search(self, query: str, k: int = 5) -> list[WebResult]:
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_S)
        try:
            # pobieramy więcej, by ranking domen urzędowych miał z czego wybierać
            rows = await self._request(client, query, max(k * 2, 10))
            results = [r for r in (_result(*row) for row in rows) if r is not None]
        except Exception as e:  # noqa: BLE001 - sieć/JSON/schemat: nigdy nie przerywamy rozmowy; logujemy tylko typ
            logger.warning("Web search (%s) nie powiódł się: %s", type(self).__name__, type(e).__name__)
            return []
        finally:
            if self._client is None:
                await client.aclose()
        return rank_official(results)[:k]


class BraveSearch(_HttpSearch):
    URL = "https://api.search.brave.com/res/v1/web/search"

    async def _request(self, client: httpx.AsyncClient, query: str, k: int) -> list[tuple[object, object, object]]:
        resp = await client.get(
            self.URL,
            params={"q": query, "count": min(k, 20), "country": "pl", "search_lang": "pl"},
            headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        items = resp.json().get("web", {}).get("results", [])
        return [(i.get("title"), i.get("url"), i.get("description")) for i in items]


class SerperSearch(_HttpSearch):
    URL = "https://google.serper.dev/search"

    async def _request(self, client: httpx.AsyncClient, query: str, k: int) -> list[tuple[object, object, object]]:
        resp = await client.post(
            self.URL,
            json={"q": query, "gl": "pl", "hl": "pl", "num": min(k, 20)},
            headers={"X-API-KEY": self._key},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        items = resp.json().get("organic", [])
        return [(i.get("title"), i.get("link"), i.get("snippet")) for i in items]


def get_web_search() -> WebSearch:
    provider = settings.web_search_provider.strip().lower()
    key = settings.web_search_api_key
    if provider == "brave" and key:
        return BraveSearch(key)
    if provider == "serper" and key:
        return SerperSearch(key)
    return NoneSearch()
