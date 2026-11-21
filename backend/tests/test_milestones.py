from datetime import date, timedelta

from app.models.family import Child
from app.services.milestones import CERTIFICATE_DAYS_BEFORE_DUE, USC_DAYS_AFTER_BIRTH, milestones_for

TODAY = date(2026, 11, 21)


def child(**kw) -> Child:
    base = dict(id="c1", family_id="f", name="Dziecko")
    base.update(kw)
    return Child(**base)


def keys(ms):
    return sorted(m.key for m in ms)


def test_pregnancy_gets_certificate_and_usc_milestones_from_due_date():
    due = TODAY + timedelta(days=60)
    ms = {m.key: m for m in milestones_for([child(due_date=due)], TODAY)}
    assert set(ms) == {"pregnancy-certificate", "usc-registration"}
    assert ms["pregnancy-certificate"].due == due - timedelta(days=CERTIFICATE_DAYS_BEFORE_DUE)
    assert ms["usc-registration"].due == due + timedelta(days=USC_DAYS_AFTER_BIRTH)
    assert "pracodawc" in ms["pregnancy-certificate"].title and "USC" in ms["usc-registration"].title


def test_recently_born_child_gets_only_usc_reminder():
    ms = milestones_for([child(birth_date=TODAY - timedelta(days=5))], TODAY)
    assert keys(ms) == ["usc-registration"]
    assert ms[0].due == TODAY - timedelta(days=5) + timedelta(days=USC_DAYS_AFTER_BIRTH)


def test_older_child_gets_no_reminders():
    assert milestones_for([child(birth_date=TODAY - timedelta(days=7 * 365))], TODAY) == []


def test_loss_child_gets_no_milestones():
    assert milestones_for([child(due_date=TODAY + timedelta(days=30), situation="loss", situation_kind="poronienie")], TODAY) == []


def test_each_child_gets_own_milestones():
    kids = [child(id="a", due_date=TODAY + timedelta(days=30)), child(id="b", name="B", due_date=TODAY + timedelta(days=90))]
    assert sorted(m.child_id for m in milestones_for(kids, TODAY)) == ["a", "a", "b", "b"]
