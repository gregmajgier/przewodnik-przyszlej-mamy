"""Umowy z e-teczki pracodawcy: lista per rodzic, PDF, dodanie do umów (onboarding) i widoczność dla asystenta AI."""

import asyncio
import io
import json
from datetime import date, timedelta

from conftest import login
from pypdf import PdfReader

from app.ai.tools import ToolContext
from app.mcp_server import McpClient
from app.security import Principal

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"


def _pdf_text(content: bytes) -> str:
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(io.BytesIO(content)).pages)


def test_each_parent_sees_only_own_documents(client):
    anna = client.get("/api/contracts/documents", headers=login(client, ANNA)).json()
    piotr = client.get("/api/contracts/documents", headers=login(client, PIOTR)).json()
    assert [(d["kind"], d["employer_name"]) for d in anna] == [
        ("employment", "Krakowskie Centrum Usług Wspólnych Sp. z o.o."),
        ("mandate", "Fundacja Rodzinny Kraków"),
    ]
    assert [(d["kind"], d["employer_name"]) for d in piotr] == [
        ("employment", "Małopolska Hurtownia Budowlana S.A."),
        ("mandate", "Akademia BHP Partner Sp. z o.o."),
    ]
    assert anna[0]["indefinite"] is True and anna[0]["fte"] == 1.0
    assert anna[1]["indefinite"] is False and anna[1]["end_date"] and anna[1]["voluntary_sickness"] is True
    assert anna[0]["contract_id"] is None
    assert anna[0]["filename"].endswith(".pdf")


def test_document_pdf_is_real_pdf_with_contract_text(client):
    h = login(client, ANNA)
    doc = client.get("/api/contracts/documents", headers=h).json()[0]
    r = client.get(f"/api/contracts/documents/{doc['id']}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    text = _pdf_text(r.content)
    assert "UMOWA O PRACĘ" in text
    assert "Anna Nowak" in text and "Specjalistka ds. kadr i płac" in text


def test_cannot_open_other_parents_document(client):
    piotr_doc = client.get("/api/contracts/documents", headers=login(client, PIOTR)).json()[0]
    h = login(client, ANNA)
    assert client.get(f"/api/contracts/documents/{piotr_doc['id']}/pdf", headers=h).status_code == 404
    assert client.post(f"/api/contracts/documents/{piotr_doc['id']}/import", headers=h).status_code == 404


def test_import_creates_confirmed_contract_once(client, store):
    h = login(client, ANNA)
    doc = client.get("/api/contracts/documents", headers=h).json()[0]
    r = client.post(f"/api/contracts/documents/{doc['id']}/import", headers=h)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["confirmed"] is True and c["user_id"] == "user-nowak-anna"
    assert c["source_doc_id"] == doc["id"] and c["filename"] == doc["filename"]
    assert c["position"] == "Specjalistka ds. kadr i płac" and c["fte"] == 1.0

    again = client.post(f"/api/contracts/documents/{doc['id']}/import", headers=h).json()
    assert again["id"] == c["id"]
    assert [x["id"] for x in client.get("/api/contracts", headers=h).json()] == [c["id"]]
    assert client.get("/api/contracts/documents", headers=h).json()[0]["contract_id"] == c["id"]

    # ten sam płatnik co w ZUS -> profil bez duplikatu ubezpieczenia
    insurance = store._data["profiles"]["user-nowak-anna"]["insurance"]
    assert len(insurance) == 1 and insurance[0]["contribution_base"] == 7850.0


def test_partner_sees_contract_but_not_document(client):
    anna = login(client, ANNA)
    code = client.post("/api/families", headers=anna).json()["family"]["invite_code"]
    piotr = login(client, PIOTR)
    req = client.post("/api/families/join", json={"code": code}, headers=piotr).json()
    client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=anna)
    doc = client.get("/api/contracts/documents", headers=anna).json()[0]
    client.post(f"/api/contracts/documents/{doc['id']}/import", headers=anna)

    seen = [c for c in client.get("/api/contracts", headers=piotr).json() if c["user_id"] == "user-nowak-anna"]
    assert len(seen) == 1
    assert seen[0]["filename"] is None and seen[0]["source_doc_id"] is None
    assert seen[0]["employer_name"] == "Krakowskie Centrum Usług Wspólnych Sp. z o.o."


def test_ai_agent_sees_imported_contract_without_salary(client, store):
    h = login(client, ANNA)
    family_id = client.post("/api/families", json={}, headers=h).json()["family"]["id"]
    doc = client.get("/api/contracts/documents", headers=h).json()[0]
    client.post(f"/api/contracts/documents/{doc['id']}/import", headers=h)

    ctx = ToolContext(Principal("user-nowak-anna", "parent", family_id, None), store, date(2026, 11, 21))
    out = asyncio.run(McpClient(ctx).call("profil_rodziny", {}))
    payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
    me = next(p for p in payload["family"] and payload["parents"] if p["is_you"])
    assert me["contracts"] == [
        {
            "kind": "employment",
            "employer_name": "Krakowskie Centrum Usług Wspólnych Sp. z o.o.",
            "position": "Specjalistka ds. kadr i płac",
            "fte": 1.0,
            "start_date": me["contracts"][0]["start_date"],
            "indefinite": True,
            "document": doc["filename"],
        }
    ]
    assert "7850" not in out and "gross_monthly" not in out


def test_mandate_pdf_and_import_without_false_risk(client):
    h = login(client, ANNA)
    client.post("/api/families", json={}, headers=h)
    due = (date.today() + timedelta(days=60)).isoformat()
    client.post("/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=h)
    mandate = client.get("/api/contracts/documents", headers=h).json()[1]
    text = _pdf_text(client.get(f"/api/contracts/documents/{mandate['id']}/pdf", headers=h).content)
    assert "UMOWA ZLECENIA" in text and "Zleceniobiorc" in text and "dobrowolnym ubezpieczeniem chorobowym" in text

    for d in client.get("/api/contracts/documents", headers=h).json():
        assert client.post(f"/api/contracts/documents/{d['id']}/import", headers=h).status_code == 200
    kinds = sorted(c["kind"] for c in client.get("/api/contracts", headers=h).json())
    assert kinds == ["employment", "mandate"]
    # zlecenie z dobrowolnym chorobowym -> brak ostrzeżenia o zasiłku macierzyńskim
    assert client.get("/api/risks", headers=h).json() == []


def test_ai_agent_can_quote_own_contract_clauses_without_salary(client, store):
    h = login(client, ANNA)
    family_id = client.post("/api/families", json={}, headers=h).json()["family"]["id"]
    for d in client.get("/api/contracts/documents", headers=h).json():
        client.post(f"/api/contracts/documents/{d['id']}/import", headers=h)

    tools = {t.name for t in asyncio.run(McpClient(_ctx(store, "user-nowak-anna", family_id)).list_tools())}
    assert "tresc_umowy" in tools
    out = asyncio.run(McpClient(_ctx(store, "user-nowak-anna", family_id)).call("tresc_umowy", {}))
    payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
    titles = [c["title"] for c in payload["contracts"]]
    assert titles == ["Umowa o pracę na czas nieokreślony", "Umowa zlecenia"]
    uop = payload["contracts"][0]
    headings = [p["heading"] for p in uop["paragraphs"]]
    assert "§ 5. Uprawnienia rodzicielskie" in headings
    assert not any("Wynagrodzenie" in x for x in headings)
    assert "7 850" not in out and "7 850" not in out and "1 200" not in out
    assert "dobrowolnym ubezpieczeniem chorobowym" in out


def test_ai_agent_does_not_read_partners_contract_text(client, store):
    anna = login(client, ANNA)
    code = client.post("/api/families", headers=anna).json()["family"]["invite_code"]
    piotr = login(client, PIOTR)
    req = client.post("/api/families/join", json={"code": code}, headers=piotr).json()
    client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=anna)
    for d in client.get("/api/contracts/documents", headers=anna).json():
        client.post(f"/api/contracts/documents/{d['id']}/import", headers=anna)

    family_id = client.get("/api/families/me", headers=piotr).json()["family"]["id"]
    out = asyncio.run(McpClient(_ctx(store, "user-nowak-piotr", family_id)).call("tresc_umowy", {}))
    assert "Krakowskie Centrum" not in out and "Fundacja" not in out
    assert "nie dodał jeszcze umów" in out


def _ctx(store, user_id, family_id):
    return ToolContext(Principal(user_id, "parent", family_id, None), store, date(2026, 11, 21))
