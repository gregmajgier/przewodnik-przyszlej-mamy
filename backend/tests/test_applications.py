import asyncio
from datetime import date, timedelta
from io import BytesIO

import pytest
from conftest import login, login_official
from pypdf import PdfReader

from app.mail import MailProvider, SimMailProvider, get_mail
from app.services.applications import cancel_drafts_for_child

TODAY = date.today()
EMAIL = "kadry@kcuw.example.pl"


class RecordingMail:
    """SimMailProvider, który dodatkowo zapamiętuje załączniki (w magazynie są tylko metadane)."""

    def __init__(self, store):
        self.inner: MailProvider = SimMailProvider(store)
        self.sent: list[dict] = []

    async def send(self, family_id, from_user_id, to, subject, body, attachments):
        self.sent.append({"to": to, "subject": subject, "body": body, "attachments": attachments})
        return await self.inner.send(family_id, from_user_id, to, subject, body, attachments)

    async def list_messages(self, family_id):
        return await self.inner.list_messages(family_id)


@pytest.fixture
def mail(client, store):
    rec = RecordingMail(store)
    client.app.dependency_overrides[get_mail] = lambda: rec
    return rec


def _family(client, persona="persona-nowak-anna"):
    """Rodzina Nowaków: Maja (7 l.), dziecko w drodze. Zwraca (nagłówki, {imię: id})."""
    h = login(client, persona)
    assert client.post("/api/families", json={}, headers=h).status_code == 201
    ids = {}
    for body in (
        {"name": "Maja", "birth_date": (TODAY - timedelta(days=7 * 365 + 90)).isoformat()},
        {"name": "Dziecko w drodze", "due_date": (TODAY + timedelta(days=60)).isoformat()},
    ):
        r = client.post("/api/families/me/children", json=body, headers=h)
        assert r.status_code == 201, r.text
        ids[body["name"]] = r.json()["id"]
    return h, ids


def _create(client, h, code, child=None, channel=None, expect=201):
    body = {"form_code": code}
    if child:
        body["child_id"] = child
    if channel:
        body["channel"] = channel
    r = client.post("/api/applications", json=body, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _answer(client, h, app_id, **answers):
    r = client.post(f"/api/applications/{app_id}/answers", json={"answers": answers}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _complete_zam(client, h, child, channel=None):
    app = _create(client, h, "ZAM", child, channel)
    return _answer(client, h, app["id"], street="Floriańska", house_no="12")


def _join_partner(client, ha):
    fam = client.get("/api/families/me", headers=ha).json()["family"]
    hp = login(client, "persona-nowak-piotr")
    req = client.post("/api/families/join", json={"code": fam["invite_code"]}, headers=hp).json()
    assert client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=ha).status_code == 200
    return hp


# ---------- dostęp ----------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/applications"),
        ("get", "/api/applications/forms"),
        ("post", "/api/applications"),
        ("get", "/api/applications/x"),
        ("post", "/api/applications/x/submit"),
    ],
)
def test_endpoints_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_official_cannot_use_applications(client):
    h = login_official(client, "urzednik.krakow@mrodzina.local")
    assert client.get("/api/applications", headers=h).status_code == 403
    assert client.get("/api/applications/forms", headers=h).status_code == 403


def test_user_without_family_gets_clear_error(client):
    h = login(client, "persona-nowak-anna")
    assert client.get("/api/applications", headers=h).status_code == 404


# ---------- katalog i tworzenie ----------


def test_forms_catalog_channels_and_recommended_flow(client):
    h, _ = _family(client)
    data = client.get("/api/applications/forms", headers=h).json()
    forms = {f["code"]: f for f in data["forms"]}
    assert data["recommended_flow"] == ["URLOP-MAC-ROD", "ZAM"]  # Anna jest pracownicą
    assert forms["800PLUS"]["channels"] == ["portal_agent"] and forms["800PLUS"]["only_electronic"] is True
    assert forms["ZAM"]["channels"] == ["portal_agent", "pdf_download"]
    assert forms["URLOP-MAC-ROD"]["channels"] == ["employer_email", "pdf_download"]
    assert forms["ZAS-53"]["channels"] == ["pdf_download"]
    assert "Z-3" not in forms and "Z-3a" not in forms  # dokumenty źródłowe parsera nie są wnioskami


def test_create_draft_prefills(client):
    h, ids = _family(client)
    app = _create(client, h, "ZAM", ids["Dziecko w drodze"])
    assert app["id"].startswith("app-") and app["channel"] == "portal_agent"
    assert app["values"]["first_name"] == "Anna" and app["values"]["last_name"] == "Nowak"
    assert app["applicant_id"] == "user-nowak-anna"
    assert app["status"] == "needs_input"
    assert {m["field_id"] for m in app["missing"]} == {"street", "house_no"}
    assert "signed_digest" not in app  # wewnętrzny odcisk nie wychodzi do klienta
    labels = {f["id"]: f["label"] for f in app["fields"]}  # etykiety do podglądu i edycji pól
    assert labels["street"] == "Ulica" and set(app["values"]) <= set(labels)
    assert all("source_key" not in f and "pdf_field" not in f for f in app["fields"])


def test_answers_complete_the_application_and_are_remembered(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    assert app["status"] == "draft" and app["missing"] == []
    assert app["values"]["street"] == "Floriańska"
    # zapamiętane w profilu → kolejny wniosek o ten sam adres już nie pyta
    assert client.get("/api/profile/me", headers=h).json()["answers"]["street"] == "Floriańska"
    kdr = _create(client, h, "KDR", ids["Maja"])
    assert kdr["missing"] == [] and kdr["status"] == "draft"


def test_invalid_answers_rejected(client):
    h, ids = _family(client)
    app = _create(client, h, "URLOP-MAC-ROD", ids["Dziecko w drodze"])
    r = client.post(f"/api/applications/{app['id']}/answers", json={"answers": {"employer_email": "nie-adres"}}, headers=h)
    assert r.status_code == 422 and "e-mail" in r.json()["detail"]
    r = client.post(f"/api/applications/{app['id']}/answers", json={"answers": {"hacker": "x"}}, headers=h)
    assert r.status_code == 422
    assert client.post(f"/api/applications/{app['id']}/answers", json={"answers": {}}, headers=h).status_code == 422


def test_create_requires_child_and_unknown_form_rejected(client):
    h, _ = _family(client)
    assert "dziecko" in _create(client, h, "ZAM", expect=422)["detail"]
    _create(client, h, "NIE-MA-TAKIEGO", expect=422)
    _create(client, h, "Z-3", expect=422)  # dokument źródłowy, nie wniosek


def test_other_family_child_404(client):
    h, _ = _family(client)
    hp = login(client, "persona-nowak-piotr")
    assert client.post("/api/families", json={}, headers=hp).status_code == 201
    other = client.post(
        "/api/families/me/children", json={"name": "Obce", "birth_date": "2024-01-01"}, headers=hp
    ).json()["id"]
    _create(client, h, "ZAM", other, expect=404)


def test_tylko_elektronicznie_rejects_pdf_channel(client):
    h, ids = _family(client)
    r = _create(client, h, "800PLUS", ids["Maja"], channel="pdf_download", expect=422)
    assert "elektronicznie" in r["detail"]
    app = _create(client, h, "800PLUS", ids["Maja"])
    assert app["channel"] == "portal_agent"
    r = client.patch(f"/api/applications/{app['id']}", json={"channel": "pdf_download"}, headers=h)
    assert r.status_code == 422


def test_missing_child_pesel_is_needs_input_not_a_crash(client):
    h, ids = _family(client)
    app = _create(client, h, "800PLUS", ids["Maja"])
    assert app["status"] == "needs_input"
    assert "child_pesel" in {m["field_id"] for m in app["missing"]}
    r = client.post(f"/api/applications/{app['id']}/portal-submitted", headers=h)
    assert r.status_code == 409


def test_child_pesel_answer_is_validated_and_saved_on_the_child(client):
    from app.services.zus_sim import _pesel

    h, ids = _family(client)
    app = _create(client, h, "800PLUS", ids["Maja"])
    bad = client.post(f"/api/applications/{app['id']}/answers", json={"answers": {"child_pesel": "11111111111"}}, headers=h)
    assert bad.status_code == 422 and "PESEL" in bad.json()["detail"]

    good = _pesel(TODAY - timedelta(days=7 * 365 + 90), "321", True)
    done = _answer(client, h, app["id"], child_pesel=good, street="Floriańska", house_no="1", account_number="12 3456 7890")
    assert done["status"] == "draft" and done["values"]["child_pesel"] == good
    maja = next(c for c in client.get("/api/families/me/children", headers=h).json() if c["id"] == ids["Maja"])
    assert maja["pesel"] == good  # kolejny wniosek dla Mai już o to nie zapyta


# ---------- rodzina: partner ----------


def test_partner_sees_application_in_family_list_but_cannot_edit(client):
    ha, ids = _family(client)
    app = _create(client, ha, "ZAM", ids["Dziecko w drodze"])
    hp = _join_partner(client, ha)
    listed = client.get("/api/applications", headers=hp).json()
    assert [a["id"] for a in listed] == [app["id"]]
    assert listed[0]["applicant_id"] == "user-nowak-anna"
    assert client.get(f"/api/applications/{app['id']}", headers=hp).status_code == 200
    r = client.post(f"/api/applications/{app['id']}/answers", json={"answers": {"street": "X"}}, headers=hp)
    assert r.status_code == 403
    assert client.patch(f"/api/applications/{app['id']}", json={"channel": "pdf_download"}, headers=hp).status_code == 403
    assert client.post(f"/api/applications/{app['id']}/submit", headers=hp).status_code == 403


def test_application_of_other_family_is_404(client):
    ha, ids = _family(client)
    app = _create(client, ha, "ZAM", ids["Dziecko w drodze"])
    hp = login(client, "persona-nowak-piotr")
    assert client.post("/api/families", json={}, headers=hp).status_code == 201
    for call in (
        client.get(f"/api/applications/{app['id']}", headers=hp),
        client.get(f"/api/applications/{app['id']}/pdf", headers=hp),
        client.post(f"/api/applications/{app['id']}/submit", headers=hp),
        client.post(f"/api/applications/{app['id']}/agent-plan", headers=hp),
    ):
        assert call.status_code == 404
    assert client.get("/api/applications", headers=hp).json() == []


# ---------- wysyłka do pracodawcy ----------


def _employer_ready(client, h, child):
    app = _create(client, h, "URLOP-MAC-ROD", child)
    assert app["channel"] == "employer_email" and app["status"] == "needs_input"
    app = _answer(client, h, app["id"], employer_email=EMAIL.upper())
    assert app["status"] == "draft" and app["recipient_email"] == EMAIL and app["recipient_domain"] == "kcuw.example.pl"
    return app


def test_submit_needs_input_409(client, mail):
    h, ids = _family(client)
    app = _create(client, h, "URLOP-MAC-ROD", ids["Dziecko w drodze"])
    r = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert r.status_code == 409 and "Brakuje" in r.json()["detail"]
    assert mail.sent == []


def test_submit_employer_sends_mail_with_pdf_attachment_and_stores_thread(client, store, mail):
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).json()["status"] == "ready"
    r = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert r.status_code == 200, r.text
    sent = r.json()
    assert sent["status"] == "sent" and sent["thread_id"].startswith("thread-") and sent["sent_at"]

    assert len(mail.sent) == 1
    msg = mail.sent[0]
    assert msg["to"] == EMAIL
    (filename, pdf), = msg["attachments"]
    assert filename == "URLOP-MAC-ROD.pdf" and pdf.startswith(b"%PDF")
    text = "".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "Anna Nowak" in text and "urlopu macierzyńskiego" in text

    stored = asyncio.run(store.find("mail_messages", family_id=sent["family_id"]))
    assert len(stored) == 1 and stored[0]["folder"] == "sent" and stored[0]["thread_id"] == sent["thread_id"]
    assert stored[0]["attachments"] == [{"filename": "URLOP-MAC-ROD.pdf", "size": len(pdf)}]  # bez treści PDF w bazie


def test_submit_twice_sends_once(client, mail):
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    first = client.post(f"/api/applications/{app['id']}/submit", headers=h).json()
    second = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert second.status_code == 200 and second.json()["thread_id"] == first["thread_id"]
    assert len(mail.sent) == 1


def test_submit_pdf_channel_requires_sign(client, mail):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"], channel="pdf_download")
    assert app["channel"] == "pdf_download" and app["status"] == "draft"
    r = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert r.status_code == 409 and "podpisz" in r.json()["detail"]
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).status_code == 200
    done = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert done.status_code == 200 and done.json()["status"] == "sent" and done.json()["thread_id"] is None
    assert mail.sent == []  # kanał PDF nie wysyła poczty


def test_changing_data_after_signing_invalidates_the_signature(client, mail):
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    r = client.patch(f"/api/applications/{app['id']}", json={"values": {"parental_weeks": "26"}}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["signed_at"] is None
    assert client.post(f"/api/applications/{app['id']}/submit", headers=h).status_code == 409
    assert mail.sent == []


def test_family_data_change_after_signing_blocks_submit(client, mail):
    """Termin porodu zmienił się po podpisie → daty urlopu w PDF są inne → trzeba podpisać ponownie."""
    h, ids = _family(client)
    child = ids["Dziecko w drodze"]
    app = _employer_ready(client, h, child)
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    new_due = (TODAY + timedelta(days=90)).isoformat()
    assert client.patch(f"/api/families/me/children/{child}", json={"due_date": new_due}, headers=h).status_code == 200

    r = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert r.status_code == 409 and "podpisz ponownie" in r.json()["detail"]
    assert mail.sent == []
    again = client.get(f"/api/applications/{app['id']}", headers=h).json()
    assert again["status"] == "draft" and again["values"]["child_date"] == new_due
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    assert client.post(f"/api/applications/{app['id']}/submit", headers=h).status_code == 200


def test_mail_failure_returns_502_and_keeps_application_ready(client, store):
    class Broken:
        async def send(self, *a, **k):
            raise RuntimeError("smtp down")

        async def list_messages(self, family_id):
            return []

    client.app.dependency_overrides[get_mail] = lambda: Broken()
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    r = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert r.status_code == 502 and "smtp" not in r.text
    assert client.get(f"/api/applications/{app['id']}", headers=h).json()["status"] == "ready"


def test_sent_application_is_frozen(client, mail):
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert client.post(f"/api/applications/{app['id']}/answers", json={"answers": {"employer_email": "a@b.pl"}}, headers=h).status_code == 409
    assert client.patch(f"/api/applications/{app['id']}", json={"values": {"parental_weeks": "1"}}, headers=h).status_code == 409
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).status_code == 409


def test_cannot_sign_incomplete_application(client):
    h, ids = _family(client)
    app = _create(client, h, "URLOP-MAC-ROD", ids["Dziecko w drodze"])
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).status_code == 409


def test_portal_channel_cannot_be_signed_or_submitted_as_email(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    assert app["channel"] == "portal_agent"
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).status_code == 409
    assert client.post(f"/api/applications/{app['id']}/submit", headers=h).status_code == 409


# ---------- PDF ----------


def test_pdf_preview_for_acroform_and_employer(client):
    h, ids = _family(client)
    zam = _complete_zam(client, h, ids["Dziecko w drodze"])
    r = client.get(f"/api/applications/{zam['id']}/pdf", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "no-store" and r.content.startswith(b"%PDF")
    fields = PdfReader(BytesIO(r.content)).get_fields()
    assert any(f.get("/V") == "ANNA" for f in fields.values())

    emp = _employer_ready(client, h, ids["Dziecko w drodze"])
    assert client.get(f"/api/applications/{emp['id']}/pdf", headers=h).content.startswith(b"%PDF")


def test_pdf_preview_needs_complete_data_and_not_for_portal_only(client):
    h, ids = _family(client)
    app = _create(client, h, "ZAM", ids["Dziecko w drodze"])
    assert client.get(f"/api/applications/{app['id']}/pdf", headers=h).status_code == 409
    kdr = _create(client, h, "KDR", ids["Maja"])
    _answer(client, h, kdr["id"], street="Floriańska", house_no="1")
    r = client.get(f"/api/applications/{kdr['id']}/pdf", headers=h)
    assert r.status_code == 422 and "portal" in r.json()["detail"]


# ---------- portal i agent ----------


def test_portal_submitted_is_idempotent(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    first = client.post(f"/api/applications/{app['id']}/portal-submitted", headers=h)
    assert first.status_code == 200 and first.json()["status"] == "sent"
    second = client.post(f"/api/applications/{app['id']}/portal-submitted", headers=h)
    assert second.status_code == 200 and second.json()["sent_at"] == first.json()["sent_at"]


def test_portal_submitted_rejects_non_portal_channel(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"], channel="pdf_download")
    assert client.post(f"/api/applications/{app['id']}/portal-submitted", headers=h).status_code == 409


def test_agent_plan_demo_mode_builds_steps_from_profile(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    r = client.post(f"/api/applications/{app['id']}/agent-plan", headers=h)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["portal_id"] == "ezus_zam" and plan["kind"] == "ezus" and plan["blocked"] == []
    by_id = {s["field_id"]: s for s in plan["steps"]}
    assert by_id["first_name"]["value"] == "Anna" and by_id["street"]["value"] == "Floriańska"
    assert all(s["reason"] for s in plan["steps"])


def test_agent_plan_blocks_on_missing_data(client):
    h, ids = _family(client)
    app = _create(client, h, "800PLUS", ids["Maja"])
    plan = client.post(f"/api/applications/{app['id']}/agent-plan", headers=h).json()
    assert {q["field_id"] for q in plan["blocked"]} >= {"street", "house_no", "child_pesel"}
    assert "street" not in {s["field_id"] for s in plan["steps"]}


def test_agent_plan_only_for_portal_channel(client):
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"], channel="pdf_download")
    assert client.post(f"/api/applications/{app['id']}/agent-plan", headers=h).status_code == 409


def test_agent_plan_is_ai_guarded_and_settles_tokens(client, store):
    from app.ai.llm import FakeLLM, LLMResult, Usage, get_llm
    from app.services.agent_plan import DraftStep, PlanDraft

    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    fake = FakeLLM().script(PlanDraft(steps=[DraftStep(field_id="first_name", reason="Z ZUS.")]))
    client.app.dependency_overrides[get_llm] = lambda: fake
    r = client.post(f"/api/applications/{app['id']}/agent-plan", headers=h)
    assert r.status_code == 200 and fake.calls[0].feature == "agent_plan"
    assert {s["field_id"]: s["reason"] for s in r.json()["steps"]}["first_name"] == "Z ZUS."
    assert asyncio.run(store.find("ai_usage"))  # rezerwacja została rozliczona w budżecie


def test_agent_plan_llm_failure_is_503_and_releases_budget(client, store):
    from app.ai.llm import FakeLLM, LLMError, get_llm

    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"])
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM().script(LLMError("Asystent AI jest chwilowo niedostępny."))
    r = client.post(f"/api/applications/{app['id']}/agent-plan", headers=h)
    assert r.status_code == 503
    used = sum(d.get("tokens", 0) for d in asyncio.run(store.find("ai_usage")))
    assert used == 0  # rezerwacja zwrócona


def test_portal_schema_endpoint(client):
    h, _ = _family(client)
    data = client.get("/api/applications/portals/emp_kdr", headers=h).json()
    assert data["kind"] == "empatia" and data["form_code"] == "KDR"
    assert {"id", "label", "type"} <= set(data["fields"][0]) and "source_key" not in data["fields"][0]
    assert client.get("/api/applications/portals/nie-ma", headers=h).status_code == 404
    assert client.get("/api/applications/portals/ezus_zam", headers=h).json()["fields"]  # extends_form


# ---------- tryb straty (plan 10) ----------


def test_cancel_drafts_for_child(client, store):
    h, ids = _family(client)
    child = ids["Dziecko w drodze"]
    a = _create(client, h, "ZAM", child)
    b = _create(client, h, "URLOP-MAC-ROD", child)
    sent = _complete_zam(client, h, child)
    client.post(f"/api/applications/{sent['id']}/portal-submitted", headers=h)
    other = _create(client, h, "KDR", ids["Maja"])

    assert asyncio.run(cancel_drafts_for_child(store, child)) == 2
    status = {x["id"]: x["status"] for x in client.get("/api/applications", headers=h).json()}
    assert status[a["id"]] == "cancelled" and status[b["id"]] == "cancelled"
    assert status[sent["id"]] == "sent"  # wysłanych nie ruszamy
    assert status[other["id"]] != "cancelled"
    assert asyncio.run(cancel_drafts_for_child(store, child)) == 0


def test_loss_blocks_new_and_pending_applications(client):
    h, ids = _family(client)
    child = ids["Dziecko w drodze"]
    app = _employer_ready(client, h, child)
    client.post(f"/api/applications/{app['id']}/sign", headers=h)
    # sytuację zmienia tylko serwis planu 10 (anuluje szkice po cichu)
    r = client.post(f"/api/families/me/children/{child}/situation", json={"kind": "poronienie"}, headers=h)
    assert r.status_code == 200, r.text
    blocked = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert blocked.status_code == 409
    assert client.get(f"/api/applications/{app['id']}", headers=h).json()["status"] == "cancelled"
    _create(client, h, "URLOP-MAC-ROD", child, expect=409)
    # wyjątek: zasiłek macierzyński po stracie (wsparcie z trybu jaskółki) można złożyć także o to dziecko
    _create(client, h, "ZAM", child)


# ---------- współbieżność ----------


def test_concurrent_submits_send_exactly_one_mail(client, store):
    """Podwójne kliknięcie „Wyślij” (równoległe żądania, wolna poczta) → jedna wiadomość."""
    from concurrent.futures import ThreadPoolExecutor

    class SlowMail(RecordingMail):
        async def send(self, *args, **kwargs):
            await asyncio.sleep(0.05)  # okno na wyścig
            return await super().send(*args, **kwargs)

    slow = SlowMail(store)
    client.app.dependency_overrides[get_mail] = lambda: slow
    h, ids = _family(client)
    app = _employer_ready(client, h, ids["Dziecko w drodze"])
    client.post(f"/api/applications/{app['id']}/sign", headers=h)

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: client.post(f"/api/applications/{app['id']}/submit", headers=h), range(5)))
    assert all(r.status_code == 200 and r.json()["status"] == "sent" for r in results)
    assert len(slow.sent) == 1
    assert len({r.json()["thread_id"] for r in results}) == 1
