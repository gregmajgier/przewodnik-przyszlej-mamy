import asyncio
from datetime import date

from conftest import login

from app.ai.tools import ToolContext
from app.mcp_server import McpClient
from app.security import Principal
from app.services import web_search

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


def _ctx(store, user_id="user-nowak-anna", family_id=None) -> ToolContext:
    return ToolContext(Principal(user_id, "parent", family_id, None), store, date(2026, 11, 21))


def _run(coro):
    return asyncio.run(coro)


def _family_with_children(client, headers, children=("Maja",)):
    fam = client.post("/api/families", json={}, headers=headers).json()["family"]
    for name in children:
        r = client.post(
            "/api/families/me/children", json={"name": name, "birth_date": "2019-03-01"}, headers=headers
        )
        assert r.status_code == 201, r.text
    return fam["id"]


def test_mcp_lists_registered_tools(store):
    tools = _run(McpClient(_ctx(store)).list_tools())
    names = {t.name for t in tools}
    assert {"profil_rodziny", "szukaj_w_przepisach", "szukaj_w_sieci"} <= names
    law = next(t for t in tools if t.name == "szukaj_w_przepisach")
    assert law.parameters["required"] == ["query"]


def test_mcp_call_profil_rodziny_has_no_pesel(client, store):
    h = login(client, ANNA)
    family_id = _family_with_children(client, h)
    out = _run(McpClient(_ctx(store, family_id=family_id)).call("profil_rodziny", {}))
    profile = store._data["profiles"]["user-nowak-anna"]
    assert profile["pesel"] not in out
    assert "pesel" not in out.lower()
    assert "contribution_base" not in out and str(int(profile["insurance"][0]["contribution_base"])) not in out
    assert "Maja" in out and "Kraków" in out


def test_mcp_call_uses_principal_family_only(client, store):
    ha = login(client, ANNA)
    family_a = _family_with_children(client, ha, ("Maja",))
    # druga rodzina: Piotr zakłada własną (osobna rodzina, osobne dzieci)
    hp = login(client, PIOTR)
    family_b = _family_with_children(client, hp, ("Zosia",))
    assert family_a != family_b
    out_a = _run(McpClient(_ctx(store, "user-nowak-anna", family_a)).call("profil_rodziny", {}))
    out_b = _run(McpClient(_ctx(store, "user-nowak-piotr", family_b)).call("profil_rodziny", {}))
    assert "Maja" in out_a and "Zosia" not in out_a
    assert "Zosia" in out_b and "Maja" not in out_b
    # tożsamości nie da się podać w argumentach modelu
    bad = _run(McpClient(_ctx(store, "user-nowak-anna", family_a)).call("profil_rodziny", {"family_id": family_b}))
    assert "Zosia" not in bad and "Błąd narzędzia" in bad


def test_mcp_profile_without_family_is_polite(store):
    out = _run(McpClient(_ctx(store)).call("profil_rodziny", {}))
    assert "nie utworzył jeszcze rodziny" in out


def test_mcp_call_invalid_args_returns_error_text(store):
    mcp = McpClient(_ctx(store))
    assert "Nieprawidłowe argumenty" in _run(mcp.call("szukaj_w_przepisach", {"query": 123}))
    assert "Nieprawidłowe argumenty" in _run(mcp.call("szukaj_w_przepisach", {}))
    assert "Nieznane narzędzie" in _run(mcp.call("nie_ma_takiego", {}))
    assert _run(mcp.call("szukaj_w_przepisach", {"query": "x" * 10, "k": 99})).startswith("Błąd narzędzia")


def test_szukaj_w_przepisach_returns_article_and_url(store):
    import json

    out = json.loads(_run(McpClient(_ctx(store)).call("szukaj_w_przepisach", {"query": "urlop macierzyński wymiar"})))
    assert out["results"]
    first = out["results"][0]
    assert first["article"].startswith("Art. ") and first["url"].startswith("https://isap.sejm.gov.pl/")
    assert first["act"] and first["text"]
    assert len(first["text"]) <= 1500


def test_szukaj_w_sieci_without_provider_is_tool_error(store):
    out = _run(McpClient(_ctx(store)).call("szukaj_w_sieci", {"query": "żłobek Kraków dofinansowanie"}))
    assert out.startswith("Błąd narzędzia szukaj_w_sieci")


def test_szukaj_w_sieci_ranks_official_first(store, monkeypatch):
    import json

    class Fake:
        async def search(self, query, k=5):
            return [
                web_search.WebResult(title="Blog", url="https://blog.example.com/x", snippet="s"),
                web_search.WebResult(title="ZUS", url="https://www.zus.pl/y", snippet="s"),
            ]

    from app.tools import chat_tools

    monkeypatch.setattr(chat_tools, "get_web_search", lambda: Fake())
    out = json.loads(_run(McpClient(_ctx(store)).call("szukaj_w_sieci", {"query": "zasiłek"})))
    assert [r["url"] for r in out["results"]] == ["https://www.zus.pl/y", "https://blog.example.com/x"]
