"""Odpowiedź trybu demo (bez Azure) dla klasyfikacji poczty (plan 09): słowa kluczowe."""

from ..ai.llm import LLMMessage, register_demo_handler
from ..services.mail_classify import FEATURE, Classification

RULES = [
    (("wezwan", "uzupełn", "uzupelni", "brakuj"), "more_info", "ZUS prosi o uzupełnienie dokumentów."),
    (("odmow", "negatywn", "nie przysługuje"), "rejected", "Wniosek został rozpatrzony negatywnie."),
    (("zatwierdz", "pozytywn", "przyzna"), "accepted", "Wniosek został rozpatrzony pozytywnie."),
    (("otrzyma", "potwierdzamy", "wpłynął"), "received", "Wniosek dotarł do adresata."),
]


def _classify(messages: list[LLMMessage]) -> Classification:
    user = next((m for m in reversed(messages) if m.role == "user"), None)
    text = (user.content or "").casefold() if user else ""
    for keys, status, summary in RULES:
        if any(k in text for k in keys):
            return Classification(status=status, confidence=0.92, summary=summary)
    return Classification(status="other", confidence=0.3, summary="Wiadomość wymaga Twojej uwagi.")


register_demo_handler(FEATURE, _classify)
