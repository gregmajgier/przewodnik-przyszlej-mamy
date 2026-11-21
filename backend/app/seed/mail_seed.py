"""Predefiniowana zawartość symulowanej skrzynki (plan 09): maile NIEZWIĄZANE z wnioskami.

Pokazują, że filtr czyta tylko korespondencję w sprawie wniosków. Wkładane leniwie przy pierwszym dostępie
do skrzynki danej rodziny (identyfikator rodziny powstaje dopiero w trakcie działania aplikacji).
"""

from datetime import datetime, timedelta

from ..models.mail import MailMessage
from ..storage import Store

SEED_MESSAGES = [
    ("sklep@zabawki-maluch.pl", "Twoje zamówienie nr 48213 zostało wysłane", "Paczka z wózkiem dotrze jutro."),
    ("sekretariat@sp12.krakow.pl", "Zebranie z rodzicami klasy 1b", "Zapraszamy na zebranie w czwartek o 17:00."),
    ("rejestracja@przychodnia-zdrowie.pl", "Przypomnienie o wizycie", "Wizyta u położnej: wtorek, 10:30."),
    ("newsletter@mamaitata.example.pl", "10 rzeczy do torby do porodu", "Sprawdź naszą listę!"),
    ("babcia.krysia@gmail.com", "Niedzielny obiad", "Przyjedźcie w niedzielę, upiekę sernik."),
    ("powiadomienia@bank.example.pl", "Wyciąg z konta za październik", "Twój wyciąg jest dostępny w bankowości."),
]


async def ensure_seed_inbox(store: Store, family_id: str, now: datetime) -> None:
    for i, (sender, subject, body) in enumerate(SEED_MESSAGES):
        mid = f"mail-seed-{family_id}-{i}"
        if await store.get("mail_messages", mid) is not None:
            continue
        msg = MailMessage(
            id=mid,
            family_id=family_id,
            folder="inbox",
            from_addr=sender,
            to_addr="",
            subject=subject,
            body=body,
            message_id=f"<seed-{i}-{family_id}@sim>",
            received_at=now - timedelta(days=i + 1),
        )
        await store.put("mail_messages", msg.model_dump(mode="json"))
