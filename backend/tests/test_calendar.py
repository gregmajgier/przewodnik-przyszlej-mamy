import asyncio
from datetime import date, datetime, timedelta, timezone

from app.models.application import Application
from app.models.benefit import Benefit, Criteria, Deadline
from app.models.contract import Risk
from app.models.family import Child, Family, FamilyView
from app.models.user import User
from app.services.calendar_gen import BenefitWithMatch, add_months, generate_events, merge_done
from conftest import login

TODAY = date(2026, 11, 21)

ANNA = User(id="u-anna", role="parent", name="Anna Nowak")
PIOTR = User(id="u-piotr", role="parent", name="Piotr Nowak")

ZASILEK = Benefit(
    id="zas", name="Zasiłek macierzyński", scope="national", category="benefit", description="x", how_to_apply="x", source_url="https://x.pl",
    deadline=Deadline(anchor="due", offset_days=-21), criteria=Criteria(requires_pregnancy=True),
)
B800 = Benefit(
    id="800", name="800+", scope="national", category="benefit", description="x", how_to_apply="x", source_url="https://x.pl",
    deadline=Deadline(anchor="birth", offset_months=3), criteria=Criteria(child_age_min_months=0, child_age_max_months=215),
)


def view(*children: Child) -> FamilyView:
    return FamilyView(family=Family(id="fam", name="Nowak", owner_id="u-anna", member_ids=["u-anna", "u-piotr"]),
                      members=[ANNA, PIOTR], children=list(children))


def expected(due=date(2027, 1, 20)) -> Child:
    return Child(id="c-new", family_id="fam", name="Maluszek", due_date=due)


def born(birth=date(2026, 11, 1)) -> Child:
    return Child(id="c-new", family_id="fam", name="Maluszek", birth_date=birth)


def fits(*bs):
    return [BenefitWithMatch(benefit=b, status="fits") for b in bs]


def test_due_date_generates_prebirth_deadlines():
    evs = generate_events(view(expected()), fits(ZASILEK, B800), [], [], TODAY)
    deadlines = [e for e in evs if e.kind == "deadline" and e.source_ref.startswith("benefit:")]
    assert [(e.source_ref, e.due_date) for e in deadlines] == [
        ("benefit:zas", date(2026, 12, 30)),
        ("benefit:800", date(2027, 4, 20)),  # termin „po porodzie” liczony orientacyjnie od przewidywanego porodu
    ]
    assert "przed porodem" in deadlines[0].title and "po porodzie" in deadlines[1].title
    assert "orientacyjny" in deadlines[1].summary
    # kamienie milowe ciąży: zaświadczenie dla pracodawcy (8 tyg. przed porodem) i rejestracja w USC (21 dni po)
    milestones = {e.source_ref: e.due_date for e in evs if e.source_ref.startswith("milestone:")}
    assert milestones == {"milestone:pregnancy-certificate": date(2027, 1, 20) - timedelta(days=56),
                          "milestone:usc-registration": date(2027, 1, 20) + timedelta(days=21)}
    assert any(e.kind == "child" and e.due_date == date(2027, 1, 20) for e in evs)


def test_birth_unlocks_800plus_deadline_3_months():
    evs = generate_events(view(born(date(2026, 11, 1))), fits(ZASILEK, B800), [], [], TODAY)
    [e] = [e for e in evs if e.source_ref == "benefit:800"]
    assert e.due_date == date(2027, 2, 1)
    assert e.effect_until == date(2044, 10, 31)  # do dnia przed 18. urodzinami
    assert not any(e.source_ref == "benefit:zas" for e in evs)


def test_benefit_deadline_carries_form_code_for_redirect_to_wizard():
    with_form = ZASILEK.model_copy(update={"form_codes": ["ZAM"]})
    evs = generate_events(view(expected()), fits(with_form, B800), [], [], TODAY)
    by_ref = {e.source_ref: e for e in evs if e.source_ref.startswith("benefit:")}
    assert by_ref["benefit:zas"].form_code == "ZAM"
    assert by_ref["benefit:zas"].child_id == "c-new"
    assert by_ref["benefit:800"].form_code is None  # świadczenie bez kreatora — brak przycisku w kalendarzu


def test_no_benefit_events_for_status_no():
    evs = generate_events(view(born()), [BenefitWithMatch(benefit=B800, status="no")], [], [], TODAY)
    assert not [e for e in evs if e.kind == "deadline" and e.source_ref.startswith("benefit:")]


def test_done_preserved_on_regeneration():
    evs = generate_events(view(expected()), fits(ZASILEK), [], [], TODAY)
    target = evs[0]
    stored = {target.id: {**target.model_dump(mode="json"), "done": True}}
    again = merge_done(generate_events(view(expected()), fits(ZASILEK), [], [], TODAY), stored)
    assert next(e for e in again if e.id == target.id).done is True


def test_overdue_marked():
    evs = generate_events(view(born(date(2026, 6, 1))), fits(B800), [], [], TODAY)
    [e] = [e for e in evs if e.kind == "deadline"]
    assert e.due_date == date(2026, 9, 1) and e.overdue is True
    # bardzo stare terminy (np. 800+ dla 7-latka) są pomijane, bez błędu
    old = generate_events(view(born(date(2019, 5, 1))), fits(B800), [], [], TODAY)
    assert not [e for e in old if e.kind == "deadline"]


def test_month_end_offsets():
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)


def test_application_event_shows_who_submitted():
    sent = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    app = Application(id="a1", family_id="fam", applicant_id="u-piotr", form_code="URLOP-OJC", channel="employer_email", status="sent",
                      recipient_email="kadry@firma.pl", sent_at=sent, created_at=sent)
    [e] = [e for e in generate_events(view(), [], [app], [], TODAY) if e.kind == "application"]
    assert e.actor_name == "Piotr Nowak" and e.actor_user_id == "u-piotr"
    assert "Piotr Nowak" in e.summary and "kadry@firma.pl" in e.summary
    assert e.due_date == date(2026, 11, 20) and e.status == "sent"


def test_warning_from_risk():
    r = Risk(id="mandate-sickness:u-anna:c1:c-new", severity="high", title="Brak zasiłku", explanation="Wyjaśnienie.",
             action="Zgłoś się.", deadline=date(2026, 12, 1), user_id="u-anna", source_ref="c1")
    [e] = [e for e in generate_events(view(), [], [], [r], TODAY) if e.kind == "warning"]
    assert e.severity == "high" and e.due_date == date(2026, 12, 1)
    assert "Zgłoś się." in e.summary and e.actor_name == "Anna Nowak"


def test_ids_stable_no_duplicates_after_due_date_change():
    a = generate_events(view(expected(date(2027, 1, 20))), fits(ZASILEK), [], [], TODAY)
    b = generate_events(view(expected(date(2027, 2, 10))), fits(ZASILEK), [], [], TODAY)
    assert {e.id for e in a} == {e.id for e in b}
    assert len(b) == len({e.id for e in b})
    zas = next(e for e in b if e.source_ref == "benefit:zas")
    assert zas.due_date == date(2027, 1, 20)


def test_loss_situation_skips_child_events():
    ch = expected().model_copy(update={"situation": "loss", "situation_kind": "poronienie"})
    evs = generate_events(view(ch), fits(ZASILEK), [], [], TODAY)
    assert evs == []


# --- API ---------------------------------------------------------------------------------------


def family(client):
    anna = login(client, "persona-nowak-anna")
    client.post("/api/families", headers=anna)
    due = (date.today() + timedelta(days=60)).isoformat()
    child = client.post("/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=anna).json()
    return anna, child


def test_calendar_api_generates_and_patch_done_persists(client):
    anna, _ = family(client)
    evs = client.get("/api/calendar", headers=anna).json()
    assert any(e["kind"] == "child" for e in evs)
    assert any(e["source_ref"] == "benefit:nat-zasilek-macierzynski" for e in evs)
    target = evs[0]["id"]
    assert client.patch(f"/api/calendar/{target}", json={"done": True}, headers=anna).json()["done"] is True
    again = client.get("/api/calendar", headers=anna).json()
    assert next(e for e in again if e["id"] == target)["done"] is True
    assert len(again) == len({e["id"] for e in again})


def test_calendar_due_date_change_no_duplicates(client):
    anna, child = family(client)
    before = client.get("/api/calendar", headers=anna).json()
    new_due = (date.today() + timedelta(days=80)).isoformat()
    client.patch(f"/api/families/me/children/{child['id']}", json={"due_date": new_due}, headers=anna)
    after = client.get("/api/calendar", headers=anna).json()
    assert {e["id"] for e in before} == {e["id"] for e in after}


def test_calendar_range_filter_and_isolation(client, store):
    anna, _ = family(client)
    far = (date.today() + timedelta(days=30)).isoformat()
    evs = client.get(f"/api/calendar?to={far}", headers=anna).json()
    assert all(e["due_date"] is None or e["due_date"] <= far for e in evs)
    piotr = login(client, "persona-nowak-piotr")
    assert client.get("/api/calendar", headers=piotr).status_code == 404  # bez rodziny
    some = client.get("/api/calendar", headers=anna).json()[0]["id"]
    assert client.patch(f"/api/calendar/{some}", json={"done": True}, headers=piotr).status_code == 404


def test_notifications_read(client, store):
    anna, _ = family(client)
    fid = asyncio.run(store.get("users", "user-nowak-anna"))["family_id"]
    now = datetime.now(timezone.utc).isoformat()
    asyncio.run(store.put("notifications", {"id": "n1", "family_id": fid, "user_ids": ["user-nowak-anna"],
                                            "kind": "status_change", "text": "Wniosek ZAM: otrzymano.",
                                            "link": "/poczta", "created_at": now}))
    [n] = client.get("/api/notifications", headers=anna).json()
    assert n["read"] is False
    assert client.post("/api/notifications/n1/read", headers=anna).json()["read"] is True
    assert client.get("/api/notifications", headers=anna).json()[0]["read"] is True
    piotr = login(client, "persona-nowak-piotr")
    assert client.post("/api/notifications/n1/read", headers=piotr).status_code == 404


def test_tool_kalendarz(client, store):
    from app.ai.tools import ToolContext, call_tool, load_all_tools
    from app.security import Principal

    family(client)
    load_all_tools()
    fid = asyncio.run(store.get("users", "user-nowak-anna"))["family_id"]
    out = asyncio.run(call_tool("kalendarz", {"days": 120}, ToolContext(Principal("user-nowak-anna", "parent", fid), store, date.today())))
    assert any("porodu" in e["title"] for e in out["events"])
