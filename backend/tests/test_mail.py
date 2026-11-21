import asyncio

from app.mail import SimMailProvider


def test_sim_mail_stores_message_in_sent_folder_without_attachment_bytes(store):
    mail = SimMailProvider(store)
    sent = asyncio.run(mail.send("fam-1", "user-1", "kadry@firma.pl", "Wniosek", "Treść", [("a.pdf", b"%PDF-1")]))
    assert sent.thread_id.startswith("thread-") and sent.message_id.startswith("mail-")
    (doc,) = asyncio.run(store.find("mail_messages", family_id="fam-1"))
    assert doc["folder"] == "sent" and doc["to_addr"] == "kadry@firma.pl" and doc["user_id"] == "user-1"
    assert doc["attachments"] == [{"filename": "a.pdf", "size": 6}]
    assert "%PDF" not in str(doc)


def test_list_messages_scoped_to_family_newest_first(store):
    mail = SimMailProvider(store)
    first = asyncio.run(mail.send("fam-1", "u", "a@b.pl", "Pierwsza", "x", []))
    second = asyncio.run(mail.send("fam-1", "u", "a@b.pl", "Druga", "x", []))
    asyncio.run(mail.send("fam-2", "u", "a@b.pl", "Cudza", "x", []))
    messages = asyncio.run(mail.list_messages("fam-1"))
    assert [m.subject for m in messages] == ["Druga", "Pierwsza"]
    assert {m.thread_id for m in messages} == {first.thread_id, second.thread_id}
    assert asyncio.run(mail.list_messages("fam-3")) == []
