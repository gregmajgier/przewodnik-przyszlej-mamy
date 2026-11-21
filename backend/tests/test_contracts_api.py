import asyncio
import importlib
import logging
from datetime import date, timedelta

import pytest
from conftest import login

from app.ai.llm import FakeLLM, LLMError, Usage, LLMResult, get_llm
from app.ai.tools import ToolContext, call_tool
from app.config import settings
from app.models.contract import ContractDraft
from app.security import Principal

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"
TEXT = "Umowa zlecenie zawarta w Krakowie pomiędzy Studio Foto s.c. a zleceniobiorcą".encode()

MANDATE = ContractDraft(
    kind="mandate",
    employer_name="Studio Foto s.c.",
    employer_address="ul. Długa 1, Kraków",
    position="Fotograf",
    gross_monthly=4000.0,
    start_date=date(2026, 1, 1),
    indefinite=True,
)
EMPLOYMENT = ContractDraft(
    kind="employment",
    employer_name="Nowy Pracodawca Sp. z o.o.",
    fte=0.5,
    gross_monthly=3500.0,
    start_date=date(2025, 5, 1),
    indefinite=True,
)


@pytest.fixture
def fake(client):
    f = FakeLLM()
    client.app.dependency_overrides[get_llm] = lambda: f
    yield f
    client.app.dependency_overrides.clear()


def _family(client, h, *, expected=True):
    assert client.post("/api/families", json={}, headers=h).status_code == 201
    if expected:
        due = (date.today() + timedelta(days=60)).isoformat()
        r = client.post("/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=h)
        assert r.status_code == 201


def _scan(client, h, content=TEXT, name="umowa.txt", ctype="text/plain"):
    return client.post("/api/contracts/scan", files={"file": (name, content, ctype)}, headers=h)


def _scan_ok(client, h, fake, draft=MANDATE):
    fake.script(draft)
    r = _scan(client, h)
    assert r.status_code == 200, r.text
    return r.json()


def _join_partner(client, ha, hp):
    code = client.get("/api/families/me", headers=ha).json()["family"]["invite_code"]
    req = client.post("/api/families/join", json={"code": code}, headers=hp).json()
    assert client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha).status_code == 200


def _budget_used(store):
    docs = asyncio.run(store.find("ai_usage"))
    return sum(d["tokens"] for d in docs)


def test_scan_returns_draft_and_saves_unconfirmed(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    body = _scan_ok(client, h, fake)
    assert body["filename"] == "umowa.txt"
    assert body["draft"]["employer_name"] == "Studio Foto s.c."
    assert "voluntary_sickness" in body["draft"]["missing"]
    doc = asyncio.run(store.get("contracts", body["draft_id"]))
    assert doc["confirmed"] is False
    assert client.get("/api/contracts", headers=h).json() == []  # szkic nie jest jeszcze na liście


def test_scan_requires_parent_and_login(client, fake):
    assert _scan(client, {}).status_code == 401


def test_scan_requires_family(client, fake):
    h = login(client, ANNA)
    fake.script(MANDATE)
    r = _scan(client, h)
    assert r.status_code == 409
    assert fake.calls == []


def test_scan_requires_ai_guard_limit_429(client, fake, monkeypatch):
    h = login(client, ANNA)
    _family(client, h)
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    fake.script(MANDATE, MANDATE)
    assert _scan(client, h).status_code == 200
    r = _scan(client, h)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert len(fake.calls) == 1


def test_scan_rejects_too_large_413(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    big = b"Umowa " + b"a" * (5 * 1024 * 1024)
    r = _scan(client, h, big)
    assert r.status_code == 413
    assert fake.calls == []
    assert _budget_used(store) == 0  # rezerwacja zwrócona


def test_scan_rejects_huge_content_length_before_parsing(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    r = client.post(
        "/api/contracts/scan",
        content=b"x",
        headers={**h, "content-type": "multipart/form-data; boundary=x", "content-length": str(50 * 1024 * 1024)},
    )
    assert r.status_code in (413, 400)  # serwer testowy może odciąć wcześniej; liczy się brak wywołania LLM
    assert fake.calls == []


@pytest.mark.parametrize(
    "content,ctype",
    [
        (b"MZ\x90\x00" + b"\x00" * 100, "application/pdf"),  # exe udające PDF
        (b"%PDF-1.4 abcdefghijklmnopqrstuvwxyz", "image/png"),  # nagłówek != typ
        (b"GIF89a" + b"\x00" * 50, "image/gif"),
    ],
)
def test_scan_rejects_bad_files_415(client, fake, content, ctype):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(MANDATE)
    assert _scan(client, h, content, "umowa.pdf", ctype).status_code == 415
    assert fake.calls == []


def test_scan_unreadable_returns_422_and_saves_nothing(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(ContractDraft())
    r = _scan(client, h)
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Nie udało się odczytać umowy")
    assert asyncio.run(store.find("contracts")) == []


def test_scan_llm_failure_returns_503_and_releases_budget(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(LLMError("Asystent AI jest chwilowo niedostępny. Spróbuj ponownie za chwilę."))
    r = _scan(client, h)
    assert r.status_code == 503
    assert _budget_used(store) == 0


def test_scan_settles_real_token_usage(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(LLMResult(text=MANDATE.model_dump_json(), usage=Usage(prompt_tokens=700, completion_tokens=100)))
    assert _scan(client, h).status_code == 200
    assert _budget_used(store) == 800


def test_scan_does_not_log_contract_content(client, fake, caplog):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(MANDATE)
    with caplog.at_level(logging.DEBUG):
        _scan(client, h, name="Jan Kowalski umowa.txt")
    assert "Studio Foto" not in caplog.text and "Kowalski" not in caplog.text


def test_filename_is_sanitised(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    fake.script(MANDATE)
    r = _scan(client, h, name="..\\..\\etc/passwd.txt")
    assert r.json()["filename"] == "passwd.txt"


def test_confirm_requires_required_fields_422(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    scan = _scan_ok(client, h, fake)
    bad = {**scan["draft"], "employer_name": None, "start_date": None}
    r = client.post(f"/api/contracts/{scan['draft_id']}/confirm", json=bad, headers=h)
    assert r.status_code == 422
    assert "nazwa pracodawcy" in r.json()["detail"] and "data rozpoczęcia" in r.json()["detail"]
    nofte = {**scan["draft"], "gross_monthly": None, "fte": None}
    assert client.post(f"/api/contracts/{scan['draft_id']}/confirm", json=nofte, headers=h).status_code == 422


def test_confirm_rejects_end_before_start(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    scan = _scan_ok(client, h, fake)
    bad = {**scan["draft"], "end_date": "2025-01-01", "indefinite": False}
    assert client.post(f"/api/contracts/{scan['draft_id']}/confirm", json=bad, headers=h).status_code == 422


def test_confirm_saves_and_lists(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    scan = _scan_ok(client, h, fake)
    r = client.post(
        f"/api/contracts/{scan['draft_id']}/confirm", json={**scan["draft"], "voluntary_sickness": True}, headers=h
    )
    assert r.status_code == 200 and r.json()["confirmed"] is True
    listed = client.get("/api/contracts", headers=h).json()
    assert [c["employer_name"] for c in listed] == ["Studio Foto s.c."]
    assert listed[0]["filename"] == "umowa.txt"
    again = client.post(f"/api/contracts/{scan['draft_id']}/confirm", json=scan["draft"], headers=h)
    assert again.status_code == 409


def test_confirm_updates_profile_insurance(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    scan = _scan_ok(client, h, fake)
    client.post(f"/api/contracts/{scan['draft_id']}/confirm", json={**scan["draft"], "voluntary_sickness": False}, headers=h)
    ins = client.get("/api/profile/me", headers=h).json()["insurance"]
    mandate = [i for i in ins if i["kind"] == "mandate"]
    assert len(mandate) == 1
    assert mandate[0]["payer"] == "Studio Foto s.c." and mandate[0]["contribution_base"] == 4000.0
    assert mandate[0]["voluntary_sickness"] is False
    assert any(i["kind"] == "employment" for i in ins)  # wpis z ZUS został


def test_confirm_merges_with_matching_zus_entry(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    same = ContractDraft(
        kind="employment",
        employer_name="krakowskie centrum usług wspólnych sp. z o.o.",
        fte=1.0,
        gross_monthly=9999.0,
        start_date=date(2021, 11, 21),
        indefinite=True,
    )
    scan = _scan_ok(client, h, fake, same)
    client.post(f"/api/contracts/{scan['draft_id']}/confirm", json=scan["draft"], headers=h)
    ins = client.get("/api/profile/me", headers=h).json()["insurance"]
    assert len(ins) == 1 and ins[0]["contribution_base"] == 7850.0  # dane ZUS nadrzędne


def test_limit_5_contracts_409(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    for _ in range(5):
        _scan_ok(client, h, fake, EMPLOYMENT)
    fake.script(EMPLOYMENT)
    r = _scan(client, h)
    assert r.status_code == 409
    assert "5" in r.json()["detail"]
    assert len(fake.calls) == 5


def test_delete_draft_frees_slot(client, fake):
    h = login(client, ANNA)
    _family(client, h)
    ids = [_scan_ok(client, h, fake, EMPLOYMENT)["draft_id"] for _ in range(5)]
    assert client.delete(f"/api/contracts/{ids[0]}", headers=h).status_code == 204
    _scan_ok(client, h, fake, EMPLOYMENT)


def test_other_family_forbidden(client, fake):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    _family(client, ha)
    _family(client, hp, expected=False)
    scan = _scan_ok(client, ha, fake)
    cid = scan["draft_id"]
    assert client.post(f"/api/contracts/{cid}/confirm", json=scan["draft"], headers=hp).status_code == 403
    assert client.delete(f"/api/contracts/{cid}", headers=hp).status_code == 403
    assert client.delete("/api/contracts/nie-ma", headers=hp).status_code == 404


def test_officials_cannot_use_contracts(client, fake):
    from conftest import login_official

    h = login_official(client, "urzednik.krakow@mrodzina.local")
    assert client.get("/api/contracts", headers=h).status_code == 403
    assert client.get("/api/risks", headers=h).status_code == 403


def test_partner_sees_confirmed_data_not_file(client, fake):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    _family(client, ha)
    _join_partner(client, ha, hp)
    scan = _scan_ok(client, ha, fake)
    cid = scan["draft_id"]
    # szkic nie jest widoczny dla partnera, nie może go też zatwierdzić ani usunąć
    assert client.get("/api/contracts", headers=hp).json() == []
    assert client.post(f"/api/contracts/{cid}/confirm", json=scan["draft"], headers=hp).status_code == 403
    client.post(f"/api/contracts/{cid}/confirm", json={**scan["draft"], "voluntary_sickness": True}, headers=ha)
    seen = client.get("/api/contracts", headers=hp).json()
    assert len(seen) == 1 and seen[0]["employer_name"] == "Studio Foto s.c."
    assert seen[0]["filename"] is None
    assert client.delete(f"/api/contracts/{cid}", headers=hp).status_code == 403


def test_risks_endpoint_uses_contracts_and_zus(client, fake, store):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    _family(client, ha)
    _join_partner(client, ha, hp)
    assert client.get("/api/risks", headers=ha).json() == []
    # zlecenie Anny bez chorobowego -> ryzyko wysokie
    scan = _scan_ok(client, ha, fake)
    client.post(f"/api/contracts/{scan['draft_id']}/confirm", json={**scan["draft"], "voluntary_sickness": False}, headers=ha)
    # zadłużenie JDG Piotra z "ZUS"
    doc = asyncio.run(store.get("profiles", "user-nowak-piotr"))
    doc["insurance"][0]["kind"] = "jdg"
    doc["contribution_debt"] = {"amount": 1500.0, "since": "2026-05-01"}
    asyncio.run(store.put("profiles", doc))
    for h in (ha, hp):
        risks = client.get("/api/risks", headers=h).json()
        assert {(r["user_id"], r["severity"]) for r in risks} == {
            ("user-nowak-anna", "high"),
            ("user-nowak-piotr", "high"),
        }
        assert all(r["action"] and r["explanation"] for r in risks)
    # po usunięciu umowy ryzyko Anny znika
    client.delete(f"/api/contracts/{scan['draft_id']}", headers=ha)
    users = {r["user_id"] for r in client.get("/api/risks", headers=ha).json()}
    assert users == {"user-nowak-piotr"}


def test_risks_isolated_between_families(client, fake):
    ha, hp = login(client, ANNA), login(client, PIOTR)
    _family(client, ha)
    _family(client, hp, expected=False)
    scan = _scan_ok(client, ha, fake)
    client.post(f"/api/contracts/{scan['draft_id']}/confirm", json={**scan["draft"], "voluntary_sickness": False}, headers=ha)
    assert len(client.get("/api/risks", headers=ha).json()) == 1
    assert client.get("/api/risks", headers=hp).json() == []


async def test_mcp_tool_ryzyka(client, fake, store):
    h = login(client, ANNA)
    _family(client, h)
    scan = _scan_ok(client, h, fake)
    client.post(f"/api/contracts/{scan['draft_id']}/confirm", json={**scan["draft"], "voluntary_sickness": False}, headers=h)
    me = client.get("/api/families/me", headers=h).json()
    from app.ai import tools as reg
    import app.tools.contracts as mod

    reg._REGISTRY.pop("ryzyka", None)
    importlib.reload(mod)
    ctx = ToolContext(Principal("user-nowak-anna", "parent", me["family"]["id"]), store, date.today())
    out = await call_tool("ryzyka", {}, ctx)
    assert [r["severity"] for r in out] == ["high"]
    other = ToolContext(Principal("user-nowak-piotr", "parent", None), store, date.today())
    assert await call_tool("ryzyka", {}, other) == []
