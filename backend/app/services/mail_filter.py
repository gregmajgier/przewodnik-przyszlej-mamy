"""Filtr poczty (plan 09, spec §9): które wiadomości ze skrzynki rodziny dotyczą wysłanego wniosku.

Czytamy tylko: odpowiedzi w wątku wniosku, maile z dokładnego adresu odbiorcy oraz — wyłącznie dla domen
instytucjonalnych (ZUS, gov.pl, urzędy z katalogu) — maile z tej samej domeny. Nigdy po całej domenie
publicznego dostawcy poczty (gmail.com, onet.pl, …). Wiadomości sprzed wysyłki wniosku są pomijane.
"""

import json
import re
from pathlib import Path

from ..models.application import Application
from ..models.mail import MailMessage

CATALOG = Path(__file__).resolve().parent.parent / "data" / "katalog_wnioskow_pdf.json"

PUBLIC_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com", "googlemail.com", "onet.pl", "onet.eu", "op.pl", "wp.pl", "o2.pl", "interia.pl",
        "interia.eu", "poczta.fm", "tlen.pl", "gazeta.pl", "outlook.com", "hotmail.com", "live.com",
        "msn.com", "yahoo.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "aol.com", "gmx.com",
        "vp.pl", "buziaczek.pl", "autograf.pl",
    }
)


def _catalog_domains() -> set[str]:
    try:
        text = CATALOG.read_text(encoding="utf-8")
    except OSError:
        return set()
    hosts = re.findall(r"https?://([^/\"?#:]+)", text)
    return {h.lower().removeprefix("www.") for h in hosts}


INSTITUTIONAL_DOMAINS: frozenset[str] = frozenset(
    ({"zus.pl", "gov.pl", "um.krakow.pl", "malopolska.pl"} | _catalog_domains()) - PUBLIC_DOMAINS
)


def domain_of(addr: str | None) -> str:
    addr = (addr or "").strip().lower()
    if "<" in addr and ">" in addr:  # "Jan Kowalski <jan@x.pl>"
        addr = addr[addr.rfind("<") + 1 : addr.rfind(">")]
    return addr.rsplit("@", 1)[-1] if "@" in addr else ""


def _email(addr: str | None) -> str:
    addr = (addr or "").strip().lower()
    if "<" in addr and ">" in addr:
        addr = addr[addr.rfind("<") + 1 : addr.rfind(">")]
    return addr


def is_public(domain: str) -> bool:
    return domain in PUBLIC_DOMAINS or any(domain.endswith("." + d) for d in PUBLIC_DOMAINS)


def is_institutional(domain: str) -> bool:
    if not domain or is_public(domain):
        return False
    return any(domain == d or domain.endswith("." + d) for d in INSTITUTIONAL_DOMAINS)


def matches_application(msg: MailMessage, app: Application) -> bool:
    if msg.folder != "inbox" or msg.family_id != app.family_id or app.sent_at is None:
        return False
    if msg.received_at < app.sent_at:
        return False
    if msg.related_application_id:  # powiązanie ustalone przy dostarczeniu/klasyfikacji: tylko ten wniosek
        return msg.related_application_id == app.id
    if app.thread_id and msg.thread_id == app.thread_id:
        return True
    sender = _email(msg.from_addr)
    if app.recipient_email and sender == _email(app.recipient_email):
        return True
    sender_domain = domain_of(sender)
    target = (app.recipient_domain or domain_of(app.recipient_email)).lower()
    return bool(target) and sender_domain == target and is_institutional(sender_domain)


def find_application(msg: MailMessage, apps: list[Application]) -> Application | None:
    """Najlepsze dopasowanie: wątek > dokładny adres > domena instytucjonalna; przy remisie najnowszy wniosek."""
    def rank(a: Application) -> int:
        if msg.related_application_id == a.id:
            return 4
        if a.thread_id and msg.thread_id == a.thread_id:
            return 3
        if a.recipient_email and _email(msg.from_addr) == _email(a.recipient_email):
            return 2
        return 1

    candidates = [a for a in apps if matches_application(msg, a)]
    if not candidates:
        return None
    return max(candidates, key=lambda a: (rank(a), a.sent_at))
