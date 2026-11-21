import asyncio
from datetime import datetime, timedelta, timezone

from app.mail.sim_inbox import SimInbox, schedule_reply
from app.models.application import Application
from app.models.mail import MailMessage
from app.seed.mail_seed import SEED_MESSAGES, ensure_seed_inbox
from app.services.mail_filter import INSTITUTIONAL_DOMAINS, PUBLIC_DOMAINS, find_application, matches_application

SENT = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def app_(**kw) -> Application:
    base = dict(
        id="app-1", family_id="fam-1", applicant_id="user-nowak-anna", form_code="URLOP-MAC-ROD",
        status="sent", channel="employer_email", recipient_email="kadry@kcuw.example.pl", recipient_domain="kcuw.example.pl",
        thread_id="thread-1", sent_at=SENT, created_at=SENT,
    )
    return Application(**{**base, **kw})


def msg(**kw) -> MailMessage:
    base = dict(
        id="m1", family_id="fam-1", folder="inbox", from_addr="ktos@inna.pl", to_addr="anna@gmail.com",
        subject="s", body="b", message_id="<m1>", received_at=SENT + timedelta(hours=1),
    )
    return MailMessage(**{**base, **kw})


def test_thread_match():
    assert matches_application(msg(thread_id="thread-1"), app_())


def test_exact_address_match():
    assert matches_application(msg(from_addr="Dział Kadr <KADRY@kcuw.example.pl>"), app_())


def test_institutional_domain_match():
    a = app_(recipient_email="wnioski@zus.pl", recipient_domain="zus.pl", thread_id=None)
    assert matches_application(msg(from_addr="zasilki@zus.pl"), a)
    assert matches_application(msg(from_addr="zasilki@oddzial.zus.pl"), a) is False  # inna domena niż odbiorca


def test_non_institutional_domain_not_matched_by_domain():
    assert not matches_application(msg(from_addr="prezes@kcuw.example.pl"), app_(thread_id=None))


def test_public_domain_never_matches_by_domain():
    a = app_(recipient_email="firma.kadry@gmail.com", recipient_domain="gmail.com", thread_id=None)
    assert not matches_application(msg(from_addr="jan@gmail.com"), a)
    assert matches_application(msg(from_addr="firma.kadry@gmail.com"), a)  # dokładny adres — tak
    assert "gmail.com" in PUBLIC_DOMAINS and "gmail.com" not in INSTITUTIONAL_DOMAINS
    assert {"zus.pl", "gov.pl"} <= INSTITUTIONAL_DOMAINS


def test_message_before_sent_at_ignored():
    assert not matches_application(msg(thread_id="thread-1", received_at=SENT - timedelta(minutes=1)), app_())


def test_other_family_or_sent_folder_ignored():
    assert not matches_application(msg(thread_id="thread-1", family_id="fam-2"), app_())
    assert not matches_application(msg(thread_id="thread-1", folder="sent"), app_())
    assert not matches_application(msg(thread_id="thread-1"), app_(sent_at=None))


def test_find_application_prefers_thread():
    a1 = app_(id="a1", thread_id="t-a1", recipient_email="wnioski@zus.pl", recipient_domain="zus.pl")
    a2 = app_(id="a2", thread_id="t-a2", recipient_email="inne@zus.pl", recipient_domain="zus.pl")
    assert find_application(msg(from_addr="x@zus.pl", thread_id="t-a1"), [a2, a1]).id == "a1"
    assert find_application(msg(from_addr="x@other.pl"), [a1, a2]) is None


def test_unrelated_inbox_mails_present_in_seed_and_ignored(store):
    asyncio.run(ensure_seed_inbox(store, "fam-1", SENT + timedelta(days=10)))
    asyncio.run(ensure_seed_inbox(store, "fam-1", SENT + timedelta(days=10)))  # idempotentne
    inbox = SimInbox(store)
    msgs = asyncio.run(inbox.list_messages("fam-1"))
    assert 5 <= len(msgs) == len(SEED_MESSAGES) <= 6
    a = app_(sent_at=SENT - timedelta(days=30))
    assert all(find_application(m, [a]) is None for m in msgs)


def test_sim_replies_match_their_application(store):
    a = app_(created_at=SENT)
    asyncio.run(store.put("applications", a.model_dump(mode="json")))
    asyncio.run(schedule_reply(store, a, SENT))
    inbox = SimInbox(store)
    assert asyncio.run(inbox.deliver_due("fam-1", SENT)) == 0  # jeszcze przed terminem
    assert asyncio.run(inbox.deliver_due("fam-1", SENT, force=True)) == 2
    assert asyncio.run(inbox.deliver_due("fam-1", SENT, force=True)) == 0
    msgs = asyncio.run(inbox.list_messages("fam-1"))
    assert len(msgs) == 2 and all(matches_application(m, a) for m in msgs)
