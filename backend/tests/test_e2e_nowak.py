"""Scenariusz end-to-end rodziny Nowaków — czytaj jak dokumentację produktu.

Pokrywa cały produkt: logowanie personą, rodzina i dzieci z danych ZUS, dołączenie drugiego rodzica, analiza
świadczeń (pytanie zmienia status), skan i zatwierdzenie umowy z ostrzeżeniami o ryzyku, wniosek urlopowy do
pracodawcy z odpowiedziami testowymi (status, kalendarz, powiadomienia), świadczenie opublikowane przez
urzędnika Krakowa, czat z cytatem artykułu oraz tryb jaskółki (zgłoszenie, drugi rodzic bez powiadomienia,
anulowane szkice, wyciszony kalendarz, cofnięcie).
"""

import asyncio
import json
from pathlib import Path

from conftest import login, login_official, send_application

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

    # 3. Piotr dołącza kodem i od razu jest w rodzinie (kod to zgoda Anny)
    piotr = login(client, PIOTR)
    join = client.post("/api/families/join", json={"code": family["invite_code"]}, headers=piotr)
    assert join.status_code == 201
    members = client.get("/api/families/me", headers=piotr).json()["members"]
    assert [m["name"] for m in members] == ["Anna Nowak", "Piotr Nowak"]
    assert len(client.get("/api/families/me/children", headers=piotr).json()) == 3  # oboje widzą dzieci

    # 3a. Analiza: dopasowania z pytaniem „może”; odpowiedź zmienia status na „przysługuje”
    analysis = client.get("/api/analysis", headers=anna).json()
    assert analysis["totals"]["fits"] > 0 and analysis["steps"]
    matches = client.get("/api/benefits", headers=piotr).json()  # partner widzi to samo
    maybe = next(m for m in matches if m["match"]["status"] == "maybe" and m["match"]["questions"])
    answer = client.post(
        f"/api/benefits/{maybe['benefit']['id']}/answers",
        json={"condition_id": maybe["match"]["questions"][0]["condition_id"], "answer": True},
        headers=anna,
    )
    assert answer.status_code == 200 and answer.json()["match"]["status"] != "maybe"

    # 3b. Umowa: Anna wgrywa przykładową umowę (tryb demo), zatwierdza odczyt; ostrzeżenia są wspólne dla rodziny
    sample = Path(__file__).parents[1] / "app" / "seed" / "sample_umowa_anna_nowak.pdf"
    scan = client.post(
        "/api/contracts/scan", files={"file": ("umowa.pdf", sample.read_bytes(), "application/pdf")}, headers=anna
    )
    assert scan.status_code == 200, scan.text
    confirmed = client.post(f"/api/contracts/{scan.json()['draft_id']}/confirm", json=scan.json()["draft"], headers=anna)
    assert confirmed.status_code == 200, confirmed.text
    assert client.get("/api/risks", headers=anna).json() == client.get("/api/risks", headers=piotr).json()

    # 3c. Wniosek o urlop: kreator → podpis → wysyłka do pracodawcy; odpowiedzi testowe zmieniają status
    sent = send_application(client, anna)
    assert sent["status"] == "sent" and sent["thread_id"]
    replies = client.post("/api/mail/simulate-replies", headers=piotr).json()  # robi to któreś z rodziców
    assert replies["status_changes"] >= 1
    assert client.get(f"/api/applications/{sent['id']}", headers=piotr).json()["status"] == "accepted"
    calendar = client.get("/api/calendar", headers=piotr).json()
    entry = next(e for e in calendar if e["source_ref"] == f"application:{sent['id']}")
    assert entry["status"] == "accepted" and entry["actor_name"] == "Anna Nowak"
    notifications_before_loss = len(client.get("/api/notifications", headers=piotr).json())
    assert notifications_before_loss >= 1

    # 3d. Urzędnik Krakowa publikuje świadczenie; rodzina z Krakowa je widzi, wcześniej nie
    official = login_official(client, "urzednik.krakow@mrodzina.local")
    local = client.post(
        "/api/official/benefits",
        json={"name": "Dopłata do żłobka w Krakowie", "description": "Dopłata dla rodziców.", "amount_text": "500 zł / mies."},
        headers=official,
    ).json()
    assert local["id"] not in {m["benefit"]["id"] for m in client.get("/api/benefits", headers=anna).json()}
    assert client.post(f"/api/official/benefits/{local['id']}/publish", headers=official).status_code == 200
    assert local["id"] in {m["benefit"]["id"] for m in client.get("/api/benefits", headers=anna).json()}

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

    # 5. Anna ma w toku dwa szkice: o dziecko w drodze (ZAM) i o Maję (KDR)
    drafted = children["Dziecko w drodze"]["id"]
    zam = client.post("/api/applications", json={"form_code": "ZAM", "child_id": drafted}, headers=anna)
    kdr = client.post("/api/applications", json={"form_code": "KDR", "child_id": children["Maja"]["id"]}, headers=anna)
    assert zam.status_code == 201 and kdr.status_code == 201, (zam.text, kdr.text)
    zam_id, kdr_id = zam.json()["id"], kdr.json()["id"]
    calendar_before = client.get("/api/calendar", headers=piotr).json()
    assert any(e["child_id"] == drafted for e in calendar_before)

    # 6. Zdarzyła się strata ciąży. Anna jedną spokojną opcją zgłasza poronienie — bez pól i potwierdzeń
    assert client.get("/api/me/mode", headers=piotr).json()["mode"] == "normal"
    r = client.post(f"/api/families/me/children/{drafted}/situation", json={"kind": "poronienie"}, headers=anna)
    assert r.status_code == 200 and r.json()["name"] == "Dziecko w drodze"  # imię zostaje w profilu

    # 7. Piotr przy następnym wejściu widzi ten sam tryb — bez żadnego powiadomienia
    mode = client.get("/api/me/mode", headers=piotr).json()
    assert mode["mode"] == "jaskolka" and mode["child_id"] == drafted and mode["undo_until"]
    assert len(client.get("/api/notifications", headers=piotr).json()) == notifications_before_loss

    # 8. Szkic o to dziecko anulowano po cichu; szkic dla Mai został
    apps = {a["id"]: a for a in asyncio.run(store.find("applications", family_id=family["id"]))}
    assert apps[zam_id]["status"] == "cancelled" and apps[kdr_id]["status"] != "cancelled"
    assert apps[sent["id"]]["status"] == "accepted"  # wysłanych nie ruszamy

    # 8a. Kalendarz: terminy o utracone dziecko znikają; świadczenia o stracie są na liście „Dla Was”
    calendar = client.get("/api/calendar", headers=piotr).json()
    assert not [e for e in calendar if e["child_id"] == drafted and e["kind"] in ("deadline", "child")]
    benefits = client.get("/api/benefits", headers=piotr).json()
    assert any("loss_support" in m["benefit"]["tags"] for m in benefits)

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
    assert apps[zam_id]["status"] == "cancelled"
    assert [e for e in client.get("/api/calendar", headers=anna).json() if e["child_id"] == drafted]  # terminy wracają


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
