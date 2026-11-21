"""Wyszukiwanie w sieci dla czatu: dostawcy (Brave/Serper), ranking domen urzędowych.

Zasady: błąd dostawcy nigdy nie przerywa czatu (zwracamy pustą listę); zapytań ani wyników nie logujemy
(mogą zawierać dane rodziny) — tylko typ błędu.
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

_TIMEOUT = 8.0
_MAX_SNIPPET = 400
_MAX_QUERY = 300


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


class WebSearch(Protocol):
    async def search(self, query: str, k: int = 5) -> list[WebResult]: ...


# Domeny urzędowe: gov.pl i subdomeny (m.in. powiatowe urzędy pracy: *.praca.gov.pl), BIP, ZUS,
# strony urzędów gmin/miast/starostw (um.*, ug.*, starostwo.*, pup.*, mops.*, gops.*).
_OFFICIAL_HOST_RE = re.compile(
    r"(^|\.)(gov\.pl|zus\.pl|sejm\.pl|nfz\.gov\.pl)$"
    r"|^(bip|um|ug|ugm|urzad|starostwo|pup|mops|gops|mosir)\."
    r"|(^|\.)bip\.[a-z0-9.-]+$"
)


def is_official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host or host.endswith((".edu.pl", ".com.pl")):  # np. ug.edu.pl to uczelnia, nie urząd gminy
        return False
    return bool(_OFFICIAL_HOST_RE.search(host))


def rank_official(results: list[WebResult]) -> list[WebResult]:
    """Domeny urzędowe najpierw; kolejność wewnątrz każdej klasy bez zmian (sort stabilny)."""
    return sorted(results, key=lambda r: 0 if is_official(r.url) else 1)


def _clean(text: str | None, limit: int) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()[:limit]


def _to_result(title: str | None, url: str | None, snippet: str | None) -> WebResult | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    return WebResult(title=_clean(title, 200) or url, url=url, snippet=_clean(snippet, _MAX_SNIPPET))


class NoWebSearch:
    async def search(self, query: str, k: int = 5) -> list[WebResult]:
        return []


class BraveSearch:
    URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key = api_key
        self._transport = transport

    async def search(self, query: str, k: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                r = await client.get(
                    self.URL,
                    params={"q": query[:_MAX_QUERY], "count": min(max(k * 2, k), 20), "country": "PL", "search_lang": "pl"},
                    headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
                )
                r.raise_for_status()
                items = r.json().get("web", {}).get("results", [])
        except (httpx.HTTPError, ValueError, AttributeError) as e:
            logger.warning("Brave Search: %s", type(e).__name__)
            return []
        out = [_to_result(i.get("title"), i.get("url"), i.get("description")) for i in items if isinstance(i, dict)]
        return [r for r in out if r is not None]


class SerperSearch:
    URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key = api_key
        self._transport = transport

    async def search(self, query: str, k: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                r = await client.post(
                    self.URL,
                    json={"q": query[:_MAX_QUERY], "num": min(max(k * 2, k), 20), "gl": "pl", "hl": "pl"},
                    headers={"X-API-KEY": self._key},
                )
                r.raise_for_status()
                items = r.json().get("organic", [])
        except (httpx.HTTPError, ValueError, AttributeError) as e:
            logger.warning("Serper: %s", type(e).__name__)
            return []
        out = [_to_result(i.get("title"), i.get("link"), i.get("snippet")) for i in items if isinstance(i, dict)]
        return [r for r in out if r is not None]


def get_web_search() -> WebSearch:
    """Dostawca wg `WEB_SEARCH_PROVIDER` (`none`|`brave`|`serper`); bez klucza zawsze `none`."""
    provider = settings.web_search_provider.strip().lower()
    key = settings.web_search_api_key
    if provider == "brave" and key:
        return BraveSearch(key)
    if provider == "serper" and key:
        return SerperSearch(key)
    return NoWebSearch()


async def search_ranked(search: WebSearch, query: str, k: int = 5) -> list[WebResult]:
    """Wyniki z rankingiem urzędowych domen, obcięte do `k`."""
    return rank_official(await search.search(query, k))[:k]
