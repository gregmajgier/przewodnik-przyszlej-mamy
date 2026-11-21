import asyncio
from datetime import datetime, timedelta, timezone

from app.ai.llm import DemoLLM, FakeLLM, LLMError, LLMResult
from app.mail.sim_inbox import SimInbox, schedule_reply
from app.models.application import Application
from app.models.mail import MailMessage
from app.seed import demo_mail  # noqa: F401
from app.seed.mail_seed import ensure_seed_inbox
from app.services.mail_classify import Classification, classify
from app.services.mail_sync import sync_family_mail

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
SENT = NOW - timedelta(hours=2)


def run(c):
    return asyncio.run(c)


def setup(store, **kw):
    run(store.put("families", {"id": "fam-1", "name": "Nowak", "owner_id": "u1", "member_ids": ["u1", "u2"]}))
    a = Application(
        id="app-1", family_id="fam-1", applicant_id="u1", form_code="URLOP-MAC-ROD", channel="employer_email", status="sent",
        recipient_email="kadry@kcuw.example.pl", recipient_domain="kcuw.example.pl", thread_id="thread-1",
        sent_at=SENT, created_at=SENT, **kw,
    )
    run(store.put("applications", a.model_dump(mode="json")))
    return a


def reply(store, i=1, body="Potwierdzamy otrzymanie.", **kw):
    m = MailMessage(
        id=f"r{i}", family_id="fam-1", folder="inbox", from_addr="kadry@kcuw.example.pl", to_addr="",
        subject="Re: wniosek", body=body, thread_id="thread-1", message_id=f"<r{i}>",
        received_at=SENT + timedelta(minutes=i), **kw,
    )
    run(store.put("mail_messages", m.model_dump(mode="json")))
    return m


def app_status(store):
    return run(store.get("applications", "app-1"))["status"]


def notifications(store):
    return run(store.find("notifications", family_id="fam-1"))


def test_high_confidence_changes_status_and_notifies(store):
    setup(store)
    reply(store)
    fake = FakeLLM().script(Classification(status="accepted", confidence=0.95, summary="Zatwierdzono urlop."))
    r = run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    assert (r.new_messages, r.status_changes, r.to_review) == (1, 1, 0)
    assert app_status(store) == "accepted"
    [n] = notifications(store)
    assert n["kind"] == "status_change" and set(n["user_ids"]) == {"u1", "u2"}
    assert "URLOP-MAC-ROD" in n["text"]


def test_low_confidence_notifies_without_status_change(store):
    setup(store)
    reply(store)
    fake = FakeLLM().script(Classification(status="accepted", confidence=0.5, summary="?"))
    r = run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    assert (r.status_changes, r.to_review) == (0, 1)
    assert app_status(store) == "sent"
    [n] = notifications(store)
    assert n["kind"] == "mail_review"
    assert n["text"] == "Nowa wiadomość w sprawie wniosku URLOP-MAC-ROD — sprawdź."
    assert run(store.get("mail_messages", "r1"))["needs_review"] is True


def test_sync_is_idempotent(store):
    setup(store)
    reply(store)
    fake = FakeLLM().script(Classification(status="received", confidence=0.9))
    run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    r2 = run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    assert (r2.new_messages, r2.status_changes) == (0, 0)
    assert len(fake.calls) == 1
    assert len(notifications(store)) == 1


def test_classifier_error_goes_to_review(store):
    setup(store)
    reply(store)
    fake = FakeLLM().script(LLMError("timeout"))
    r = run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    assert (r.status_changes, r.to_review) == (0, 1)
    assert app_status(store) == "sent"


def test_classifier_garbage_goes_to_review():
    fake = FakeLLM().script(LLMResult(text="nie json"), LLMResult(text="{zły"))
    m = MailMessage(id="x", family_id="f", folder="inbox", from_addr="a@b.pl", to_addr="", subject="s",
                    body="b", message_id="<x>", received_at=NOW)
    c = run(classify(fake, m))
    assert (c.status, c.confidence) == ("other", 0.0)


def test_unrelated_mail_not_classified(store):
    setup(store)
    run(ensure_seed_inbox(store, "fam-1", NOW))
    fake = FakeLLM()
    r = run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW))
    assert r.new_messages == 0 and fake.calls == []


def test_no_applications_no_work(store):
    run(ensure_seed_inbox(store, "fam-1", NOW))
    fake = FakeLLM()
    assert run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW)).new_messages == 0


def test_demo_handler_classifies_by_keywords():
    def m(body):
        return MailMessage(id="x", family_id="f", folder="inbox", from_addr="a@zus.pl", to_addr="", subject="s",
                           body=body, message_id="<x>", received_at=NOW)

    demo = DemoLLM()
    assert run(classify(demo, m("Wezwanie do uzupełnienia dokumentów"))).status == "more_info"
    assert run(classify(demo, m("Wydano decyzję pozytywną"))).status == "accepted"
    assert run(classify(demo, m("Potwierdzamy otrzymanie wniosku"))).status == "received"
    assert run(classify(demo, m("Decyzja odmowna"))).status == "rejected"
    other = run(classify(demo, m("Dzień dobry")))
    assert other.status == "other" and other.confidence < 0.8


def test_employer_sim_replies_end_in_accepted(store):
    a = setup(store)
    run(schedule_reply(store, a, SENT))
    r = run(sync_family_mail(store, SimInbox(store), DemoLLM(), "fam-1", SENT + timedelta(seconds=30)))
    assert (r.new_messages, r.status_changes) == (2, 2)
    assert app_status(store) == "accepted"


def test_budget_reserved_in_background(store):
    from app.ai.limits import TokenBudget

    setup(store)
    reply(store)
    budget = TokenBudget(store, 100_000)
    fake = FakeLLM().script(LLMResult(text='{"status":"received","confidence":0.9,"summary":"ok"}',
                                      usage={"prompt_tokens": 50, "completion_tokens": 10}))
    run(sync_family_mail(store, SimInbox(store), fake, "fam-1", NOW, budget=budget))
    assert run(budget.used()) == 60
