import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from conftest import login

from app.ai.tools import ToolContext
from app.errors import DomainError
from app.mcp_server import McpClient
from app.models.family import ChildPatch
from app.security import Principal
from app.services import situations
from app.services.situations import (
    CHILD_LOSS_NOTE,
    cancel_drafts_for_child,
    event_policy,
    exit_mode,
    family_mode,
    loss_support_applies,
    mode_info,
    set_serious_illness,
    set_situation,
    undo_situation,
)

ANNA = "persona-nowak-anna"
PIOTR = "persona-nowak-piotr"
T0 = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def make_family(client, store):
    """Anna i Piotr w jednej rodzinie; dzieci: Maja (7 lat), Antek (3 lata) i Dziecko w drodze."""
    ha, hp = login(client, ANNA), login(client, PIOTR)
    fam = client.post("/api/families", json={}, headers=ha).json()["family"]
    jr = client.post("/api/families/join", json={"code": fam["invite_code"]}, headers=hp).json()
    assert client.post(f"/api/families/me/join-requests/{jr['id']}/accept", headers=ha).status_code == 200
    ids = {}
    for name, body in {
        "Maja": {"birth_date": "2019-02-01"},
        "Antek": {"birth_date": "2023-08-01"},
        "Dziecko w drodze": {"due_date": "2027-01-20"},
    }.items():
        r = client.post("/api/families/me/children", json={"name": name, **body}, headers=ha)
        assert r.status_code == 201, r.text
        ids[name] = r.json()["id"]
    anna = Principal("user-nowak-anna", "parent", fam["id"], None)
    piotr = Principal("user-nowak-piotr", "parent", fam["id"], None)
    return anna, piotr, ids, fam["id"], (ha, hp)


@pytest.fixture
def fam(client, store):
    return make_family(client, store)


async def seed_apps(store, family_id, child_id, other_child_id):
    docs = [
        {"id": "a-draft", "family_id": family_id, "child_id": child_id, "status": "draft", "form_code": "800PLUS"},
        {"id": "a-needs", "family_id": family_id, "child_id": child_id, "status": "needs_input", "form_code": "KDR"},
        {"id": "a-ready", "family_id": family_id, "child_id": child_id, "status": "ready", "form_code": "ZAM"},
        {"id": "a-sent", "family_id": family_id, "child_id": child_id, "status": "sent", "form_code": "URLOP-MAC-ROD"},
        {"id": "a-accepted", "family_id": family_id, "child_id": child_id, "status": "accepted", "form_code": "BECIKOWE"},
        {"id": "a-other", "family_id": family_id, "child_id": other_child_id, "status": "draft", "form_code": "800PLUS"},
        {"id": "a-parent", "family_id": family_id, "child_id": None, "status": "draft", "form_code": "ZAM"},
    ]
    for d in docs:
        await store.put("applications", d)


# ---------- zgłoszenie ----------


def test_loss_for_expected_child_poronienie(fam, store):
    anna, piotr, ids, family_id, _ = fam
    child = run(set_situation(store, anna, ids["Dziecko w drodze"], "poronienie", now=T0))
    assert (child.situation, child.situation_kind, child.situation_at) == ("loss", "poronienie", T0)
    assert child.status == "expected" and child.name == "Dziecko w drodze"  # dziecko zostaje w profilu
    assert run(mode_info(store, piotr, now=T0))["mode"] == "jaskolka"  # drugi rodzic widzi to samo


def test_loss_for_born_child_smierc_only_one_child_changes(fam, store):
    anna, _, ids, _, _ = fam
    run(set_situation(store, anna, ids["Antek"], "smierc-dziecka", now=T0))
    docs = {d["name"]: d for d in run(store.find("children", family_id=anna.family_id))}
    assert docs["Antek"]["situation"] == "loss" and docs["Antek"]["situation_kind"] == "smierc-dziecka"
    assert docs["Maja"]["situation"] is None and docs["Dziecko w drodze"]["situation"] is None


def test_set_is_idempotent_and_first_report_wins(fam, store):
    anna, piotr, ids, _, _ = fam
    first = run(set_situation(store, anna, ids["Maja"], "martwe-urodzenie", now=T0))
    again = run(set_situation(store, piotr, ids["Maja"], "smierc-dziecka", now=T0 + timedelta(hours=5)))
    assert again.situation_kind == "martwe-urodzenie" and again.situation_at == first.situation_at == T0


def test_simultaneous_report_by_both_parents_is_idempotent(fam, store):
    anna, piotr, ids, family_id, _ = fam

    async def both():
        return await asyncio.gather(
            set_situation(store, anna, ids["Maja"], "poronienie"), set_situation(store, piotr, ids["Maja"], "poronienie")
        )

    a, b = run(both())
    assert a.situation_at == b.situation_at and a.situation_kind == b.situation_kind == "poronienie"


def test_cancelled_drafts_and_sent_applications_noted(fam, store):
    anna, _, ids, family_id, _ = fam
    run(seed_apps(store, family_id, ids["Maja"], ids["Antek"]))
    run(set_situation(store, anna, ids["Maja"], "smierc-dziecka", now=T0))
    status = {d["id"]: d for d in run(store.find("applications", family_id=family_id))}
    for app_id in ("a-draft", "a-needs", "a-ready"):
        assert status[app_id]["status"] == "cancelled" and status[app_id]["cancelled_reason"] == "child_situation"
        assert "child_loss_note" not in status[app_id]
    for app_id in ("a-sent", "a-accepted"):  # wysłanych nie ruszamy, tylko oznaczamy
        assert status[app_id]["status"] in ("sent", "accepted") and status[app_id]["child_loss_note"] == CHILD_LOSS_NOTE
    assert status["a-other"]["status"] == "draft" and status["a-parent"]["status"] == "draft"  # inne dziecko i wniosek bez dziecka


def test_no_notification_created_for_partner(fam, store):
    anna, piotr, ids, _, _ = fam
    run(set_situation(store, anna, ids["Maja"], "poronienie", now=T0))
    assert run(store.find("notifications")) == []
    assert run(mode_info(store, piotr, now=T0))["child_id"] == ids["Maja"]


def test_other_family_child_404_and_no_family_404_and_bad_kind(client, store, fam):
    anna, piotr, ids, _, _ = fam
    stranger = Principal("user-x", "parent", "family-other", None)
    with pytest.raises(DomainError) as e:
        run(set_situation(store, stranger, ids["Maja"], "poronienie"))
    assert e.value.status_code == 404
    with pytest.raises(DomainError) as e:
        run(set_situation(store, Principal("u", "parent", None, None), ids["Maja"], "poronienie"))
    assert e.value.status_code == 404
    with pytest.raises(DomainError) as e:
        run(set_situation(store, anna, ids["Maja"], "inne"))  # type: ignore[arg-type]
    assert e.value.status_code == 422
    assert run(store.get("children", ids["Maja"]))["situation"] is None


# ---------- cofnięcie ----------


def test_undo_works_on_day_7_and_409_on_day_8(fam, store):
    anna, piotr, ids, family_id, _ = fam
    run(seed_apps(store, family_id, ids["Maja"], ids["Antek"]))
    run(set_situation(store, anna, ids["Maja"], "poronienie", now=T0))

    with pytest.raises(DomainError) as e:  # 8. dzień
        run(undo_situation(store, piotr, ids["Maja"], now=T0 + timedelta(days=7, seconds=1)))
    assert e.value.status_code == 409 and "Czas na cofnięcie" in e.value.detail
    assert run(store.get("children", ids["Maja"]))["situation"] == "loss"

    child = run(undo_situation(store, piotr, ids["Maja"], now=T0 + timedelta(days=6, hours=23)))  # 7. dzień
    assert child.situation is None and child.situation_kind is None and child.situation_at is None
    assert run(mode_info(store, anna, now=T0))["mode"] == "normal"


def test_undo_keeps_cancelled_drafts_but_restores_benefits_calendar_and_notes(fam, store):
    anna, _, ids, family_id, _ = fam
    run(seed_apps(store, family_id, ids["Maja"], ids["Antek"]))
    run(set_situation(store, anna, ids["Maja"], "smierc-dziecka", now=T0))
    run(undo_situation(store, anna, ids["Maja"], now=T0 + timedelta(days=1)))
    apps = {d["id"]: d for d in run(store.find("applications", family_id=family_id))}
    assert apps["a-draft"]["status"] == "cancelled"  # nie wraca
    assert "child_loss_note" not in apps["a-sent"]  # pomyłka odwołana
    children = run(store.find("children", family_id=family_id))
    assert family_mode(children) == "normal" and event_policy(children) == {}  # świadczenia i kalendarz wracają
    assert loss_support_applies(["loss_support"], children) is False


def test_undo_without_report_409_and_window_is_configurable(fam, store, monkeypatch):
    anna, _, ids, _, _ = fam
    with pytest.raises(DomainError) as e:
        run(undo_situation(store, anna, ids["Maja"]))
    assert e.value.status_code == 409 and "Nie ma zgłoszenia" in e.value.detail
    monkeypatch.setattr(situations.settings, "undo_window_days", 1)
    run(set_situation(store, anna, ids["Maja"], "poronienie", now=T0))
    with pytest.raises(DomainError):
        run(undo_situation(store, anna, ids["Maja"], now=T0 + timedelta(days=2)))


def test_mode_info_undo_until_only_inside_window(fam, store):
    anna, _, ids, _, _ = fam
    assert run(mode_info(store, anna)) == {"mode": "normal", "since": None, "undo_until": None, "child_id": None}
    run(set_situation(store, anna, ids["Maja"], "poronienie", now=T0))
    inside = run(mode_info(store, anna, now=T0 + timedelta(days=3)))
    assert inside["mode"] == "jaskolka" and inside["undo_until"] == (T0 + timedelta(days=7)).isoformat()
    outside = run(mode_info(store, anna, now=T0 + timedelta(days=9)))
    assert outside["mode"] == "jaskolka" and outside["undo_until"] is None  # tryb zostaje; cofnięcie już nie


# ---------- wyjście z trybu ----------


def test_exit_mode_is_manual_and_keeps_child_in_situation(fam, store):
    anna, piotr, ids, family_id, _ = fam
    run(set_situation(store, anna, ids["Maja"], "smierc-dziecka", now=T0))
    # po długim czasie tryb nadal trwa — nie wychodzi sam
    assert run(mode_info(store, piotr, now=T0 + timedelta(days=400)))["mode"] == "jaskolka"
    run(exit_mode(store, piotr, now=T0 + timedelta(days=400)))
    assert run(mode_info(store, anna))["mode"] == "normal"
    child = run(store.get("children", ids["Maja"]))
    assert child["situation"] == "loss" and child["situation_exited_at"] is not None
    children = run(store.find("children", family_id=family_id))
    assert event_policy(children) == {ids["Maja"]: "skip"}  # o dziecku nadal nic nie przypominamy
    run(exit_mode(store, piotr))  # idempotentne
    # ponowne zgłoszenie nie włącza trybu na nowo (idempotencja)
    run(set_situation(store, anna, ids["Maja"], "smierc-dziecka"))
    assert run(mode_info(store, anna))["mode"] == "normal"


# ---------- reguły współdzielone ----------


def test_other_children_events_muted_not_removed(fam, store):
    anna, _, ids, family_id, _ = fam
    run(set_situation(store, anna, ids["Dziecko w drodze"], "poronienie", now=T0))
    children = run(store.find("children", family_id=family_id))
    policy = event_policy(children)
    assert policy == {ids["Dziecko w drodze"]: "skip", ids["Maja"]: "mute", ids["Antek"]: "mute"}
    assert event_policy([]) == {}


def test_benefits_for_lost_child_hidden_and_loss_support_shown(fam, store):
    anna, _, ids, family_id, _ = fam
    normal = run(store.find("children", family_id=family_id))
    assert loss_support_applies(["loss_support"], normal) is False  # zwykła rodzina nie widzi pozycji o stracie
    assert loss_support_applies(["800plus"], normal) is True
    run(set_situation(store, anna, ids["Antek"], "smierc-dziecka", now=T0))
    kids = run(store.find("children", family_id=family_id))
    assert loss_support_applies(["loss_support"], kids) is True
    assert situations.in_loss(next(k for k in kids if k["id"] == ids["Antek"]))  # matching pomija je (situation == loss)


def test_loss_support_seed_has_sources_and_is_tagged():
    items = json.loads((Path(situations.__file__).parent.parent / "data" / "benefits_loss.json").read_text(encoding="utf-8"))
    assert len(items) >= 4 and len({i["id"] for i in items}) == len(items)
    for i in items:
        assert i["tags"] == ["loss_support"]
        assert i["source_url"].startswith("https://") and i["status"] == "published"
        assert i["name"] and i["description"] and i["how_to_apply"]
        assert "!" not in i["description"] and "gratulac" not in json.dumps(i, ensure_ascii=False).lower()
    assert {"ZAM"} <= {c for i in items for c in i["form_codes"]}


def test_serious_illness_adds_za_zyciem_without_mode(fam, store):
    anna, piotr, ids, family_id, _ = fam
    child = run(set_serious_illness(store, piotr, ids["Antek"], True))
    assert child.serious_illness is True and child.situation is None
    kids = run(store.find("children", family_id=family_id))
    assert family_mode(kids) == "normal" and event_policy(kids) == {}
    assert run(mode_info(store, anna))["mode"] == "normal"
    assert run(set_serious_illness(store, anna, ids["Antek"], False)).serious_illness is False


def test_generic_child_patch_cannot_set_situation(fam):
    assert "situation" not in ChildPatch.model_fields and "situation_at" not in ChildPatch.model_fields
    assert ChildPatch.model_validate({"situation": "loss", "name": "X"}).model_dump(exclude_unset=True) == {"name": "X"}


def test_chat_tool_profile_includes_situation(fam, store):
    anna, _, ids, family_id, _ = fam
    run(set_situation(store, anna, ids["Antek"], "smierc-dziecka", now=T0))
    out = json.loads(run(McpClient(ToolContext(anna, store, date(2026, 11, 21))).call("profil_rodziny", {})))
    antek = next(c for c in out["children"] if c["name"] == "Antek")
    assert antek["situation"] == "loss" and antek["situation_kind"] == "smierc-dziecka"
    assert all("situation" not in c for c in out["children"] if c["name"] != "Antek")


def test_cancel_drafts_returns_count(fam, store):
    _, _, ids, family_id, _ = fam
    run(seed_apps(store, family_id, ids["Maja"], ids["Antek"]))
    assert run(cancel_drafts_for_child(store, family_id, ids["Maja"])) == 3
    assert run(cancel_drafts_for_child(store, family_id, ids["Maja"])) == 0  # ponowne wywołanie nic nie zmienia
