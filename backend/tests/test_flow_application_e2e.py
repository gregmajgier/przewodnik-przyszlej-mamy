"""Scenariusz ręczny Anny przez API: świadczenia → rekomendowana kolejność → urlop u pracodawcy
(draft → odpowiedzi → podgląd → podpis → wysyłka → mail w `sent`) → ZAM przez agenta w makiecie portalu.

Bez podmiany poczty i modelu: działa domyślny `SimMailProvider` i `DemoLLM` (tak jak w demo offline).
"""

import asyncio
from datetime import date, timedelta
from io import BytesIO

from conftest import login
from pypdf import PdfReader


def test_anna_flow_from_benefits_to_sent_application(client, store):
    today = date.today()
    h = login(client, "persona-nowak-anna")
    assert client.post("/api/families", json={}, headers=h).status_code == 201
    for body in (
        {"name": "Maja", "birth_date": (today - timedelta(days=7 * 365 + 90)).isoformat()},
        {"name": "Dziecko w drodze", "due_date": (today + timedelta(days=60)).isoformat()},
    ):
        assert client.post("/api/families/me/children", json=body, headers=h).status_code == 201
    unborn = next(c for c in client.get("/api/families/me/children", headers=h).json() if c["status"] == "expected")

    # 1. Świadczenia z planu 03 wskazują, co przysługuje (macierzyński pasuje przed porodem)
    benefits = {x["benefit"]["id"]: x["match"]["status"] for x in client.get("/api/benefits", headers=h).json()}
    assert "fits" in benefits.values()

    # 2. Rekomendowana kolejność dla pracownicy: najpierw urlop u pracodawcy, potem ZAM
    plan = client.get("/api/applications/forms", headers=h).json()["recommended_flow"]
    assert plan == ["URLOP-MAC-ROD", "ZAM"]

    # 3. Urlop: szkic → brakuje adresu kadr → odpowiedź → podgląd PDF → podpis → wysyłka
    draft = client.post("/api/applications", json={"form_code": plan[0], "child_id": unborn["id"]}, headers=h).json()
    assert draft["status"] == "needs_input" and draft["values"]["employer_name"]
    assert [m["field_id"] for m in draft["missing"]] == ["employer_email"]
    r = client.post(f"/api/applications/{draft['id']}/answers", json={"answers": {"employer_email": "kadry@kcuw.example.pl"}}, headers=h)
    assert r.json()["status"] == "draft"

    preview = client.get(f"/api/applications/{draft['id']}/pdf", headers=h)
    text = " ".join("".join(p.extract_text() for p in PdfReader(BytesIO(preview.content)).pages).split())  # zawijanie linii
    assert "Dziecko w drodze" in text and "Krakowskie Centrum Usług Wspólnych" in text

    assert client.post(f"/api/applications/{draft['id']}/sign", headers=h).json()["status"] == "ready"
    sent = client.post(f"/api/applications/{draft['id']}/submit", headers=h).json()
    assert sent["status"] == "sent" and sent["thread_id"]

    # 4. Mail trafił do folderu „wysłane” symulowanej skrzynki rodziny, z załącznikiem PDF
    (message,) = asyncio.run(store.find("mail_messages", family_id=sent["family_id"]))
    assert message["folder"] == "sent" and message["to_addr"] == "kadry@kcuw.example.pl"
    assert message["thread_id"] == sent["thread_id"] and message["attachments"][0]["filename"] == "URLOP-MAC-ROD.pdf"

    # 5. ZAM: agent w makiecie portalu → plan z profilu (bez braków) → zatwierdzenie → wysłane
    zam = client.post("/api/applications", json={"form_code": "ZAM", "child_id": unborn["id"]}, headers=h).json()
    assert zam["channel"] == "portal_agent"
    zam = client.post(
        f"/api/applications/{zam['id']}/answers", json={"answers": {"street": "Floriańska", "house_no": "12"}}, headers=h
    ).json()
    agent = client.post(f"/api/applications/{zam['id']}/agent-plan", headers=h).json()
    assert agent["blocked"] == [] and {s["field_id"] for s in agent["steps"]} >= {"pesel", "street", "house_no"}
    done = client.post(f"/api/applications/{zam['id']}/portal-submitted", headers=h).json()
    assert done["status"] == "sent"

    # 6. Lista wniosków rodziny pokazuje oba złożone, a poczta nie dostała drugiej wiadomości (ZAM idzie portalem)
    statuses = {a["form_code"]: a["status"] for a in client.get("/api/applications", headers=h).json()}
    assert statuses == {"URLOP-MAC-ROD": "sent", "ZAM": "sent"}
    assert len(asyncio.run(store.find("mail_messages"))) == 1
