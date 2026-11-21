"""Scenariusz end-to-end rodziny Nowaków — czytaj jak dokumentację produktu.

Pokrywa wszystko, co jest dziś w tej gałęzi: logowanie personą, rodzina i dzieci z danych ZUS, dołączenie
drugiego rodzica, czat z cytatem artykułu oraz tryb jaskółki (zgłoszenie, drugi rodzic bez powiadomienia,
anulowane szkice, cofnięcie). Kroki zależne od planów 03/04/08/09 (analiza, umowy, wnioski, poczta, kalendarz,
panel urzędnika) opisuje `test_e2e_steps_blocked_on_other_plans` — do włączenia po scaleniu tych planów.
"""

import asyncio
import json

import pytest
from conftest import login, login_official

from app.ai.llm import FakeLLM, LLMResult, ToolCall, get_llm

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


def sse_events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        head, data = block.split("\n", 1)
        out.append((head.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_nowak_family_journey(client, store):
    # 1. Anna loguje się „mObywatelem”; dane z ZUS powstają przy pierwszym logowaniu (dzieci znane z systemów)
    anna = login(client, ANNA)
    me = client.get("/api/me", headers=anna).json()
    assert me["name"] == "Anna Nowak" and me["family_id"] is None
    profile = client.get("/api/profile", headers=anna).json()["members"][0]
    assert [k["name"] for k in profile["known_children"]] == ["Maja", "Antek", "Dziecko w drodze"]

    # 2. Zakłada rodzinę i przenosi dzieci z danych ZUS na karty dzieci
    family = client.post("/api/families", json={}, headers=anna).json()["family"]
    children = {}
    for kid in profile["known_children"]:
        body = {"name": kid["name"], "birth_date": kid["birth_date"], "due_date": kid["due_date"]}
        r = client.post("/api/families/me/children", json=body, headers=anna)
        assert r.status_code == 201, r.text
        children[kid["name"]] = r.json()
    assert children["Dziecko w drodze"]["status"] == "expected" and children["Maja"]["status"] == "born"

    # 3. Piotr dołącza kodem; Anna akceptuje prośbę
    piotr = login(client, PIOTR)
    join = client.post("/api/families/join", json={"code": family["invite_code"]}, headers=piotr)
    assert join.status_code == 201
    accepted = client.post(f"/api/families/me/join-requests/{join.json()['id']}/accept", headers=anna)
    assert [m["name"] for m in accepted.json()["members"]] == ["Anna Nowak", "Piotr Nowak"]
    assert len(client.get("/api/families/me/children", headers=piotr).json()) == 3  # oboje widzą dzieci

    # 4. Czat: model woła narzędzie przepisów i odpowiada z cytatem artykułu; źródło jest linkiem do aktu
    llm = FakeLLM().script(
        LLMResult(tool_calls=[ToolCall(id="t1", name="szukaj_w_przepisach", arguments={"query": "urlop macierzyński wymiar tygodni"})]),
        LLMResult(text="Urlop macierzyński po urodzeniu jednego dziecka trwa 20 tygodni (Kodeks pracy, art. 180)."),
    )
    client.app.dependency_overrides[get_llm] = lambda: llm
    try:
        chat = client.post("/api/chat", json={"message": "Ile trwa urlop macierzyński?"}, headers=anna)
    finally:
        client.app.dependency_overrides.pop(get_llm, None)
    events = sse_events(chat.text)
    answer = "".join(d["text"] for k, d in events if k == "token")
    assert "art. 180" in answer
    sources = next(d for k, d in events if k == "sources")["sources"]
    assert sources[0]["title"] == "Kodeks pracy, Art. 180" and sources[0]["url"].startswith("https://isap.sejm.gov.pl/")

    # 5. Anna ma w toku szkic wniosku o dziecko w drodze (tworzy go plan 08; tu wstawiony wprost do bazy)
    drafted = children["Dziecko w drodze"]["id"]
    for doc in (
        {"id": "app-draft", "family_id": family["id"], "child_id": drafted, "status": "draft", "form_code": "ZAM"},
        {"id": "app-maja", "family_id": family["id"], "child_id": children["Maja"]["id"], "status": "draft", "form_code": "KDR"},
    ):
        asyncio.run(store.put("applications", doc))

    # 6. Zdarzyła się strata ciąży. Anna jedną spokojną opcją zgłasza poronienie — bez pól i potwierdzeń
    assert client.get("/api/me/mode", headers=piotr).json()["mode"] == "normal"
    r = client.post(f"/api/families/me/children/{drafted}/situation", json={"kind": "poronienie"}, headers=anna)
    assert r.status_code == 200 and r.json()["name"] == "Dziecko w drodze"  # imię zostaje w profilu

    # 7. Piotr przy następnym wejściu widzi ten sam tryb — bez żadnego powiadomienia
    mode = client.get("/api/me/mode", headers=piotr).json()
    assert mode["mode"] == "jaskolka" and mode["child_id"] == drafted and mode["undo_until"]
    assert store._data.get("notifications", {}) == {}

    # 8. Szkic o to dziecko anulowano po cichu; szkic dla Mai został
    apps = {a["id"]: a for a in asyncio.run(store.find("applications", family_id=family["id"]))}
    assert apps["app-draft"]["status"] == "cancelled" and apps["app-maja"]["status"] == "draft"

    # 9. Czat zna sytuację rodziny (narzędzie profil_rodziny), ale nie wymyśla świadczeń o utraconym dziecku
    llm = FakeLLM().script(
        LLMResult(tool_calls=[ToolCall(id="t2", name="profil_rodziny", arguments={})]),
        LLMResult(text="Jestem z Wami. Chcesz, żebym wskazała, jak wrócić do pracy?"),
    )
    client.app.dependency_overrides[get_llm] = lambda: llm
    try:
        client.post("/api/chat", json={"message": "Co teraz?"}, headers=piotr)
    finally:
        client.app.dependency_overrides.pop(get_llm, None)
    profile_result = next(m.content for m in llm.calls[-1].messages if m.role == "tool")
    assert '"situation": "loss"' in profile_result and "poronienie" in profile_result

    # 10. Zgłoszenie przez pomyłkę? Cofnięcie w oknie: tryb znika, anulowany szkic nie wraca
    undone = client.delete(f"/api/families/me/children/{drafted}/situation", headers=piotr)
    assert undone.status_code == 200 and undone.json()["situation"] is None
    assert client.get("/api/me/mode", headers=anna).json()["mode"] == "normal"
    apps = {a["id"]: a for a in asyncio.run(store.find("applications", family_id=family["id"]))}
    assert apps["app-draft"]["status"] == "cancelled"


def test_nowak_ciezka_choroba_does_not_enter_mode(client, store):
    """„Za życiem”: oznaczenie dodaje świadczenia, ale nie przełącza w tryb jaskółki."""
    anna = login(client, ANNA)
    client.post("/api/families", json={}, headers=anna)
    child = client.post("/api/families/me/children", json={"name": "Antek", "birth_date": "2023-08-01"}, headers=anna).json()
    r = client.patch(f"/api/families/me/children/{child['id']}/serious-illness", json={"value": True}, headers=anna)
    assert r.json()["serious_illness"] is True
    assert client.get("/api/me/mode", headers=anna).json()["mode"] == "normal"


def test_official_cannot_use_family_endpoints(client):
    official = login_official(client, "urzednik.krakow@mrodzina.local")
    assert client.get("/api/me/mode", headers=official).status_code == 403
    assert client.post("/api/chat", json={"message": "cześć"}, headers=official).status_code == 403


@pytest.mark.skip(
    reason=(
        "Czeka na plany 03 (analiza/świadczenia/panel), 04 (umowy, ryzyka), 08 (wnioski), 09 (poczta, kalendarz) i 07 "
        "(panel urzędnika). Kroki do dopisania w test_nowak_family_journey: /api/analysis (maybe + pytanie), wgranie i "
        "zatwierdzenie umowy (DemoLLM), /api/risks, wniosek urlopowy → submit → symulowane odpowiedzi → status i "
        "kalendarz, publikacja świadczenia przez urzędnika Krakowa widoczna dla Nowaków, a w kroku straty — "
        "ukrycie świadczeń o dziecku i wyciszenie terminów w /api/calendar."
    )
)
def test_e2e_steps_blocked_on_other_plans():
    raise AssertionError("do uzupełnienia po scaleniu planów 03/04/07/08/09")
