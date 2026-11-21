import httpx

from app.config import settings
from app.services import web_search as ws
from app.services.web_search import (
    BraveSearch,
    NoneSearch,
    SerperSearch,
    WebResult,
    get_web_search,
    is_official,
    rank_official,
)


def r(url: str, title: str = "t") -> WebResult:
    return WebResult(title=title, url=url, snippet="s")


def test_rank_official_prefers_gov_pl_and_bip():
    results = [
        r("https://blog.example.com/przedszkola"),
        r("https://um.krakow.pl/rekrutacja"),  # urząd miasta (poddomena um.)
        r("https://bip.krakow.pl/rekrutacja"),
        r("https://www.zus.pl/swiadczenia/macierzynski"),
        r("https://www.gov.pl/web/rodzina"),
        r("https://pup.krakow.pl/bon"),
    ]
    ranked = [x.url for x in rank_official(results)]
    official = {
        "https://um.krakow.pl/rekrutacja",
        "https://bip.krakow.pl/rekrutacja",
        "https://www.zus.pl/swiadczenia/macierzynski",
        "https://www.gov.pl/web/rodzina",
        "https://pup.krakow.pl/bon",
    }
    assert set(ranked[:5]) == official
    assert ranked[5:] == ["https://blog.example.com/przedszkola"]


def test_rank_is_stable_within_class():
    results = [
        r("https://a.example.com/1"),
        r("https://www.gov.pl/2"),
        r("https://b.example.com/3"),
        r("https://bip.x.pl/4"),
        r("https://c.example.com/5"),
    ]
    assert [x.url for x in rank_official(results)] == [
        "https://www.gov.pl/2",
        "https://bip.x.pl/4",
        "https://a.example.com/1",
        "https://b.example.com/3",
        "https://c.example.com/5",
    ]


def test_is_official_rejects_lookalike_domains():
    assert is_official("https://malopolska.gov.pl/x")
    assert is_official("https://sub.bip.gmina.pl/x")
    assert not is_official("https://gov.pl.evil.com/x")
    assert not is_official("https://evilgov.pl/x")
    assert not is_official("https://notzus.pl/x")
    assert not is_official("javascript:alert(1)")
    assert not is_official("not a url")


async def test_none_provider_returns_empty():
    assert await NoneSearch().search("żłobek Kraków") == []


def test_get_web_search_none_by_default(monkeypatch):
    monkeypatch.setattr(settings, "web_search_provider", "none")
    assert isinstance(get_web_search(), NoneSearch)
    monkeypatch.setattr(settings, "web_search_provider", "brave")
    monkeypatch.setattr(settings, "web_search_api_key", "")
    assert isinstance(get_web_search(), NoneSearch)  # bez klucza nie udajemy, że szukamy
    monkeypatch.setattr(settings, "web_search_api_key", "k")
    assert isinstance(get_web_search(), BraveSearch)
    monkeypatch.setattr(settings, "web_search_provider", "serper")
    assert isinstance(get_web_search(), SerperSearch)
    monkeypatch.setattr(settings, "web_search_provider", "nieznany")
    assert isinstance(get_web_search(), NoneSearch)


async def test_brave_parses_results_and_ranks_official():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("x-subscription-token")
        seen["q"] = request.url.params.get("q")
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "Blog <b>żłobki</b>", "url": "https://blog.example.com/z", "description": "x " * 500},
                        {"title": "BIP", "url": "https://bip.krakow.pl/z", "description": "Nabór do żłobków"},
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    results = await BraveSearch("sekret", client=client).search("nabór żłobek Kraków", k=5)
    assert seen == {"token": "sekret", "q": "nabór żłobek Kraków"}
    assert [x.url for x in results] == ["https://bip.krakow.pl/z", "https://blog.example.com/z"]
    assert "<b>" not in results[1].title
    assert len(results[1].snippet) <= 400


async def test_serper_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "k"
        return httpx.Response(
            200, json={"organic": [{"title": "ZUS", "link": "https://www.zus.pl/a", "snippet": "Zasiłek"}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    results = await SerperSearch("k", client=client).search("zasiłek")
    assert results == [WebResult(title="ZUS", url="https://www.zus.pl/a", snippet="Zasiłek")]


async def test_provider_http_error_returns_empty_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await BraveSearch("k", client=client).search("x") == []
    assert await SerperSearch("k", client=client).search("x") == []


async def test_provider_network_error_and_bad_json_return_empty():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>nie json</html>")

    assert await BraveSearch("k", client=httpx.AsyncClient(transport=httpx.MockTransport(boom))).search("x") == []
    assert await BraveSearch("k", client=httpx.AsyncClient(transport=httpx.MockTransport(bad))).search("x") == []


async def test_results_with_unsafe_urls_are_dropped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "x", "url": "javascript:alert(1)", "description": "d"},
                        {"title": "ok", "url": "https://www.gov.pl/a", "description": "d"},
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert [x.url for x in await BraveSearch("k", client=client).search("x")] == ["https://www.gov.pl/a"]


def test_module_exposes_protocol_names():
    assert hasattr(ws, "WebSearch")
