import httpx

from app.config import settings
from app.services.web_search import (
    BraveSearch,
    NoWebSearch,
    SerperSearch,
    WebResult,
    get_web_search,
    is_official,
    rank_official,
    search_ranked,
)


def _r(url: str, title: str = "t") -> WebResult:
    return WebResult(title=title, url=url, snippet="")


def test_rank_official_prefers_gov_pl_and_bip():
    results = [
        _r("https://blog.example.com/urlop"),
        _r("https://www.zus.pl/swiadczenia"),
        _r("https://forum.gazeta.pl/x"),
        _r("https://bip.krakow.pl/zasilek"),
        _r("https://www.gov.pl/web/rodzina"),
        _r("https://pup.krakow.pl/oferta"),
        _r("https://ug.edu.pl/studia"),
    ]
    ranked = [r.url for r in rank_official(results)]
    assert set(ranked[:4]) == {
        "https://www.zus.pl/swiadczenia",
        "https://bip.krakow.pl/zasilek",
        "https://www.gov.pl/web/rodzina",
        "https://pup.krakow.pl/oferta",
    }
    assert ranked[4:] == ["https://blog.example.com/urlop", "https://forum.gazeta.pl/x", "https://ug.edu.pl/studia"]


def test_rank_is_stable_within_class():
    results = [_r(f"https://a{i}.example.com/") for i in range(3)] + [_r("https://x.gov.pl/1"), _r("https://y.gov.pl/2")]
    ranked = [r.url for r in rank_official(results)]
    assert ranked == ["https://x.gov.pl/1", "https://y.gov.pl/2", "https://a0.example.com/", "https://a1.example.com/", "https://a2.example.com/"]


def test_is_official_rejects_lookalikes():
    assert not is_official("https://evilgov.pl/x")
    assert not is_official("https://gov.pl.evil.com/x")
    assert not is_official("not a url")
    assert is_official("https://krakow.praca.gov.pl/")


async def test_none_provider_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "web_search_provider", "none")
    ws = get_web_search()
    assert isinstance(ws, NoWebSearch)
    assert await ws.search("urlop") == []


def test_provider_without_key_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(settings, "web_search_provider", "brave")
    monkeypatch.setattr(settings, "web_search_api_key", "")
    assert isinstance(get_web_search(), NoWebSearch)
    monkeypatch.setattr(settings, "web_search_api_key", "k")
    assert isinstance(get_web_search(), BraveSearch)
    monkeypatch.setattr(settings, "web_search_provider", "serper")
    assert isinstance(get_web_search(), SerperSearch)


async def test_brave_parses_results_and_sends_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers["X-Subscription-Token"]
        seen["q"] = request.url.params["q"]
        return httpx.Response(
            200,
            json={"web": {"results": [
                {"title": "<b>ZUS</b> zasiłek", "url": "https://www.zus.pl/a", "description": "Opis <em>x</em>"},
                {"title": "bez url", "description": "x"},
                {"title": "ftp", "url": "ftp://x/y"},
            ]}},
        )

    results = await BraveSearch("secret", transport=httpx.MockTransport(handler)).search("zasiłek macierzyński")
    assert seen == {"token": "secret", "q": "zasiłek macierzyński"}
    assert [r.url for r in results] == ["https://www.zus.pl/a"]
    assert results[0].title == "ZUS zasiłek" and results[0].snippet == "Opis x"


async def test_serper_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "k"
        return httpx.Response(200, json={"organic": [{"title": "Gov", "link": "https://www.gov.pl/x", "snippet": "s"}]})

    results = await SerperSearch("k", transport=httpx.MockTransport(handler)).search("q")
    assert [(r.title, r.url, r.snippet) for r in results] == [("Gov", "https://www.gov.pl/x", "s")]


async def test_provider_http_error_returns_empty_not_raise():
    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="err")

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    for handler in (boom, broken, garbage):
        transport = httpx.MockTransport(handler)
        assert await BraveSearch("k", transport=transport).search("q") == []
        assert await SerperSearch("k", transport=transport).search("q") == []


async def test_search_ranked_orders_and_limits():
    class Fake:
        async def search(self, query: str, k: int = 5):
            return [_r("https://a.com/"), _r("https://x.gov.pl/"), _r("https://b.com/")]

    out = await search_ranked(Fake(), "q", 2)
    assert [r.url for r in out] == ["https://x.gov.pl/", "https://a.com/"]

