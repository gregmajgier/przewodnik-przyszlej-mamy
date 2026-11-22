from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ai.llm import FakeLLM, get_llm
from app.config import settings
from app.main import create_app
from app.models.contract import ContractDraft
from conftest import login

TEXT = b"UMOWA ZLECENIA\nZleceniodawca: Studio Foto\nWynagrodzenie: 3000 zl\nTekst wystarczajaco dlugi do odczytu.\n"


def draft(**kw) -> ContractDraft:
    base = dict(
        kind="mandate",
        employer_name="Studio Foto Sp. z o.o.",
        employer_address="Kraków",
        position="Fotograf",
        gross_monthly=3000,
        start_date=date(2025, 1, 1),
        indefinite=True,
        voluntary_sickness=False,
    )
    return ContractDraft(**{**base, **kw})


@pytest.fixture
def env(store):
    app = create_app(store)
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    with TestClient(app) as c:
        yield app, c, fake


def family_with_partner(c):
    anna = login(c, "persona-nowak-anna")
    code = c.post("/api/families", headers=anna).json()["family"]["invite_code"]
    piotr = login(c, "persona-nowak-piotr")
    assert c.post("/api/families/join", json={"code": code}, headers=piotr).status_code == 201
    due = (date.today() + timedelta(days=60)).isoformat()
    c.post("/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=anna)
    return anna, piotr


def scan(c, h, content=TEXT, ctype="text/plain", name="umowa.txt"):
    return c.post("/api/contracts/scan", files={"file": (name, content, ctype)}, headers=h)


def scan_and_confirm(c, fake, h, d):
    fake.script(d)
    r = scan(c, h)
    assert r.status_code == 200, r.text
    r = c.post(f"/api/contracts/{r.json()['draft_id']}/confirm", json=d.model_dump(mode="json"), headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_scan_returns_draft_and_saves_unconfirmed(env, store):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    fake.script(draft(position=None))
    r = scan(c, anna)
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "umowa.txt"
    assert body["draft"]["missing"] == ["position"]
    assert c.get("/api/contracts", headers=anna).json() == []  # szkic nie jest widoczny na liście


def test_scan_requires_ai_guard_limit_429(env, monkeypatch):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    monkeypatch.setattr(settings, "ai_user_rpm", 1)
    fake.script(draft())
    assert scan(c, anna).status_code == 200
    r = scan(c, anna)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_scan_rejects_too_large_413(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    r = scan(c, anna, content=b"a" * (5 * 1024 * 1024 + 1))
    assert r.status_code == 413
    assert fake.calls == []


def test_scan_unreadable_422_nothing_saved(env, store):
    import asyncio

    _, c, fake = env
    anna, _ = family_with_partner(c)
    r = scan(c, anna, content=b"MZ\x90\x00\x03" + b"\x00" * 50, ctype="application/pdf", name="umowa.pdf")
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Nie udało się odczytać umowy")
    assert asyncio.run(store.find("contracts")) == []


def test_confirm_requires_required_fields_422(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    fake.script(draft())
    draft_id = scan(c, anna).json()["draft_id"]
    bad = draft(employer_name=None, gross_monthly=None).model_dump(mode="json")
    r = c.post(f"/api/contracts/{draft_id}/confirm", json=bad, headers=anna)
    assert r.status_code == 422
    assert "pracodawca" in r.json()["detail"]


def test_confirm_updates_profile_insurance(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    contract = scan_and_confirm(c, fake, anna, draft())
    assert contract["confirmed"] is True
    ins = c.get("/api/profile/me", headers=anna).json()["insurance"]
    mandate = [i for i in ins if i["kind"] == "mandate"]
    assert len(mandate) == 1 and mandate[0]["payer"] == "Studio Foto Sp. z o.o."
    assert mandate[0]["voluntary_sickness"] is False
    # ponowne zatwierdzenie tej samej umowy nie duplikuje wpisu
    c.post(f"/api/contracts/{contract['id']}/confirm", json=draft(gross_monthly=3500).model_dump(mode="json"), headers=anna)
    ins = c.get("/api/profile/me", headers=anna).json()["insurance"]
    mandate = [i for i in ins if i["kind"] == "mandate"]
    assert len(mandate) == 1 and mandate[0]["contribution_base"] == 3500


def test_confirm_merges_with_existing_zus_entry(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    d = draft(kind="employment", employer_name="Krakowskie Centrum Usług Wspólnych sp. z o.o.", fte=1.0,
              gross_monthly=8000, voluntary_sickness=None)
    scan_and_confirm(c, fake, anna, d)
    ins = c.get("/api/profile/me", headers=anna).json()["insurance"]
    assert len(ins) == 1 and ins[0]["contribution_base"] == 8000


def test_limit_5_contracts_409(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    for i in range(5):
        scan_and_confirm(c, fake, anna, draft(employer_name=f"Firma {i}"))
    fake.script(draft())
    r = scan(c, anna)
    assert r.status_code == 409
    assert len(fake.calls) == 5  # szósty skan nie wywołał modelu


def test_other_family_forbidden(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    fake.script(draft())
    draft_id = scan(c, anna).json()["draft_id"]
    # nawet partner z tej samej rodziny nie może zatwierdzić ani usunąć cudzej umowy
    piotr = login(c, "persona-nowak-piotr")
    r = c.post(f"/api/contracts/{draft_id}/confirm", json=draft().model_dump(mode="json"), headers=piotr)
    assert r.status_code == 404
    assert c.delete(f"/api/contracts/{draft_id}", headers=piotr).status_code == 404


def test_family_isolation_lists(env, store):
    import asyncio

    _, c, fake = env
    anna, piotr = family_with_partner(c)
    scan_and_confirm(c, fake, anna, draft())
    # Piotr opuszcza rodzinę (symulacja innej rodziny): przenosimy go do osobnej rodziny w bazie
    user = asyncio.run(store.get("users", "user-nowak-piotr"))
    asyncio.run(store.put("users", {**user, "family_id": "family-other"}))
    asyncio.run(store.put("families", {"id": "family-other", "name": "Inna", "owner_id": "user-nowak-piotr",
                                      "member_ids": ["user-nowak-piotr"]}))
    assert c.get("/api/contracts", headers=piotr).json() == []
    assert c.get("/api/risks", headers=piotr).json() == []


def test_partner_sees_confirmed_data_not_file(env):
    _, c, fake = env
    anna, piotr = family_with_partner(c)
    scan_and_confirm(c, fake, anna, draft())
    own = c.get("/api/contracts", headers=anna).json()
    partner = c.get("/api/contracts", headers=piotr).json()
    assert own[0]["filename"] == "umowa.txt"
    assert partner[0]["employer_name"] == "Studio Foto Sp. z o.o."
    assert partner[0]["filename"] is None


def test_delete_own_contract(env):
    _, c, fake = env
    anna, _ = family_with_partner(c)
    contract = scan_and_confirm(c, fake, anna, draft())
    assert c.delete(f"/api/contracts/{contract['id']}", headers=anna).status_code == 204
    assert c.get("/api/contracts", headers=anna).json() == []


def test_risks_endpoint_uses_contracts_and_zus(env, store):
    import asyncio

    _, c, fake = env
    anna, piotr = family_with_partner(c)
    assert c.get("/api/risks", headers=anna).json() == []
    scan_and_confirm(c, fake, anna, draft())  # zlecenie bez chorobowego -> high
    # dług składkowy Piotra z „ZUS” + JDG
    prof = asyncio.run(store.get("profiles", "user-nowak-piotr"))
    prof["contribution_debt"] = {"amount": 1200.0, "since": "2026-01-01"}
    prof["insurance"].append({"kind": "jdg", "payer": "Piotr Nowak", "contribution_base": 5000.0,
                              "voluntary_sickness": None, "since": "2024-01-01"})
    asyncio.run(store.put("profiles", prof))
    risks = c.get("/api/risks", headers=piotr).json()
    titles = {(r["user_id"], r["severity"], r["title"].split()[0]) for r in risks}
    assert ("user-nowak-anna", "high", "Brak") in titles
    assert ("user-nowak-piotr", "high", "Zadłużenie") in titles
    assert len(risks) == len({r["id"] for r in risks})


def test_official_cannot_use_contracts(env):
    from conftest import login_official

    _, c, _ = env
    h = login_official(c, "urzednik.krakow@mrodzina.local")
    assert c.get("/api/contracts", headers=h).status_code == 403
    assert c.get("/api/risks", headers=h).status_code == 403


def test_tool_ryzyka(env, store):
    import asyncio

    from app.ai.tools import ToolContext, call_tool, load_all_tools
    from app.security import Principal

    _, c, fake = env
    anna, _ = family_with_partner(c)
    scan_and_confirm(c, fake, anna, draft())
    load_all_tools()
    fam = asyncio.run(store.get("users", "user-nowak-anna"))["family_id"]
    ctx = ToolContext(Principal("user-nowak-anna", "parent", fam), store, date.today())
    out = asyncio.run(call_tool("ryzyka", {}, ctx))
    assert out["risks"][0]["severity"] == "high"


def test_demo_mode_scans_sample_pdf_end_to_end(client):
    """Bez Azure (DemoLLM): przykładowa umowa Anny -> szkic bez braków -> zatwierdzenie -> profil."""
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "app" / "seed" / "sample_umowa_anna_nowak.pdf"
    anna = login(client, "persona-nowak-anna")
    client.post("/api/families", headers=anna)
    r = scan(client, anna, content=sample.read_bytes(), ctype="application/pdf", name=sample.name)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draft"]["missing"] == []
    assert body["draft"]["employer_name"] == "Krakowskie Centrum Usług Wspólnych Sp. z o.o."
    r = client.post(f"/api/contracts/{body['draft_id']}/confirm", json=body["draft"], headers=anna)
    assert r.status_code == 200
    assert len(client.get("/api/profile/me", headers=anna).json()["insurance"]) == 1  # scalone z wpisem ZUS
