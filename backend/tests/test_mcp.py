import json
from datetime import date

import pytest

from app.ai.tools import ToolContext
from app.mcp_server import McpClient, build_mcp_server
from app.security import Principal
from app.services import web_search
from app.services.web_search import WebResult
from app.storage import MemoryStore

TODAY = date(2026, 11, 21)
PESEL_A = "90010112345"
PESEL_B = "85050567890"


async def make_world() -> MemoryStore:
    s = MemoryStore()
    for fam, uid, name, city, kid, born, pesel in [
        ("f-a", "u-a", "Anna Alfa", "Kraków", "Maja", "2023-11-21", PESEL_A),
        ("f-b", "u-b", "Beata Beta", "Gdańsk", "Bartek", "2020-01-02", PESEL_B),
    ]:
        await s.put("users", {"id": uid, "role": "parent", "name": name, "family_id": fam})
        await s.put("families", {"id": fam, "name": f"Rodzina {name}", "owner_id": uid, "member_ids": [uid]})
        await s.put(
            "children",
            {"id": f"c-{fam}", "family_id": fam, "name": kid, "birth_date": born, "status": "born",
             "pesel": "11111111111", "has_disability": False, "foster": False},
        )
        await s.put(
            "profiles",
            {
                "id": uid, "user_id": uid, "first_name": name.split()[0], "last_name": name.split()[1],
                "pesel": pesel, "birth_date": "1990-01-01",
                "address": {"city": city, "gmina": city, "powiat": city, "voivodeship": "X", "postal_code": "00-000"},
                "insurance": [{"kind": "employment", "payer": "Tajny Pracodawca", "contribution_base": 9999.0,
                               "since": "2020-01-01"}],
                "ezla": [], "known_children": [], "answers": {},
            },
        )
    return s


@pytest.fixture
async def world():
    return await make_world()


def ctx_for(store: MemoryStore, user_id: str, family_id: str) -> ToolContext:
    return ToolContext(principal=Principal(user_id, "parent", family_id), store=store, today=TODAY)


async def test_mcp_lists_registered_tools(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        names = {t.name for t in await mcp.list_tools()}
    assert {"profil_rodziny", "szukaj_w_przepisach", "szukaj_w_sieci"} <= names


async def test_mcp_tool_specs_carry_json_schema(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        specs = {t.name: t for t in await mcp.list_tools()}
    assert specs["szukaj_w_przepisach"].parameters["required"] == ["query"]
    assert specs["profil_rodziny"].parameters["additionalProperties"] is False


async def test_mcp_call_profil_rodziny_has_no_pesel(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        out = await mcp.call("profil_rodziny", {})
    assert PESEL_A not in out and "11111111111" not in out
    assert "pesel" not in out.lower()
    assert "9999" not in out  # podstawa składek (zarobki) też nie trafia do modelu
    assert "Tajny Pracodawca" not in out
    data = json.loads(out)
    assert data["dzieci"][0]["imie"] == "Maja"
    assert data["dzieci"][0]["wiek"] == "3 lata"
    assert data["rodzice"][0]["miasto"] == "Kraków"
    assert data["rodzice"][0]["zatrudnienie"] == ["umowa o pracę"]


async def test_mcp_call_uses_principal_family_only(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        out_a = await mcp.call("profil_rodziny", {})
        # model próbuje podać cudzą rodzinę: schemat odrzuca argument
        attack = await mcp.call("profil_rodziny", {"family_id": "f-b"})
    assert "Bartek" not in out_a and "Gdańsk" not in out_a and "Maja" in out_a
    assert "Bartek" not in attack and "Gdańsk" not in attack
    assert attack.startswith("Błąd narzędzia")
    async with McpClient(ctx_for(world, "u-b", "f-b")) as mcp:
        out_b = await mcp.call("profil_rodziny", {})
    assert "Bartek" in out_b and "Maja" not in out_b and "Kraków" not in out_b


async def test_mcp_call_without_family(world):
    await world.put("users", {"id": "u-c", "role": "parent", "name": "Cezary C"})
    async with McpClient(ctx_for(world, "u-c", None)) as mcp:
        out = await mcp.call("profil_rodziny", {})
    assert "nie ma jeszcze rodziny" in out.lower() or "brak rodziny" in out.lower()


async def test_mcp_call_invalid_args_returns_error_text(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        missing = await mcp.call("szukaj_w_przepisach", {})
        wrong_type = await mcp.call("szukaj_w_przepisach", {"query": 123})
        unknown = await mcp.call("nie_ma_takiego", {"x": 1})
    for out in (missing, wrong_type, unknown):
        assert out.startswith("Błąd narzędzia")
    assert "123" not in wrong_type  # wartości argumentów nie wracają w komunikacie


async def test_szukaj_w_przepisach_returns_article_and_url(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        out = await mcp.call("szukaj_w_przepisach", {"query": "urlop macierzyński wymiar tygodni", "limit": 3})
    data = json.loads(out)
    assert 1 <= len(data["wyniki"]) <= 3
    for hit in data["wyniki"]:
        assert hit["artykul"].startswith("Art. ")
        assert hit["url"].startswith("https://")
        assert hit["akt"] and hit["tresc"]
    assert any(h["artykul"] == "Art. 180" for h in data["wyniki"])


async def test_szukaj_w_przepisach_no_hits_says_so(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        data = json.loads(await mcp.call("szukaj_w_przepisach", {"query": "kryptowaluty blockchain"}))
    assert data["wyniki"] == [] and "nie znaleziono" in data["uwaga"].lower()


async def test_szukaj_w_sieci_without_provider_is_honest(world):
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        data = json.loads(await mcp.call("szukaj_w_sieci", {"query": "nabór do żłobków Kraków"}))
    assert data["dostepne"] is False and data["wyniki"] == []
    assert "wyszukiwark" in data["uwaga"].lower()


async def test_szukaj_w_sieci_returns_results(world, monkeypatch):
    class Fake:
        async def search(self, query: str, k: int = 5):
            return [WebResult(title="BIP Kraków", url="https://bip.krakow.pl/zlobki", snippet="Nabór od 1 marca")]

    monkeypatch.setattr(web_search, "get_web_search", lambda: Fake())
    async with McpClient(ctx_for(world, "u-a", "f-a")) as mcp:
        data = json.loads(await mcp.call("szukaj_w_sieci", {"query": "nabór żłobek"}))
    assert data["dostepne"] is True
    assert data["wyniki"][0]["url"] == "https://bip.krakow.pl/zlobki"
    assert data["wyniki"][0]["urzedowe"] is True


async def test_server_without_context_fails_closed():
    """Wywołanie narzędzia poza kontekstem użytkownika nie może zwrócić żadnych danych."""
    from mcp import Client

    async with Client(build_mcp_server()) as client:
        result = await client.call_tool("profil_rodziny", {})
    assert result.is_error
    assert "kontekst" in result.content[0].text.lower()


async def test_concurrent_clients_do_not_leak_context(world):
    import asyncio

    async def who(uid: str, fid: str) -> str:
        async with McpClient(ctx_for(world, uid, fid)) as mcp:
            await asyncio.sleep(0)
            return await mcp.call("profil_rodziny", {})

    a, b = await asyncio.gather(who("u-a", "f-a"), who("u-b", "f-b"))
    assert "Maja" in a and "Bartek" not in a
    assert "Bartek" in b and "Maja" not in b
