"""Kamienie milowe ciąży i porodu, które nie są terminami żadnego świadczenia, a rodzic nie może ich przegapić.

Czysta funkcja — używana przez kalendarz (`calendar_gen`) i „najbliższy termin” w podsumowaniu
(`benefit_service`), żeby oba pokazywały to samo. Daty wynikają z terminu porodu (albo z daty urodzenia) i
mają charakter orientacyjny; opis każdego wpisu mówi, skąd się biorą.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..models.family import Child

# wniosek o urlop macierzyński składa się z wyprzedzeniem; urlop można zacząć do 6 tygodni przed porodem
CERTIFICATE_DAYS_BEFORE_DUE = 56
USC_DAYS_AFTER_BIRTH = 21
USC_GRACE_DAYS = 30  # po tylu dniach od terminu nie przypominamy o rejestracji już urodzonego dziecka


@dataclass(frozen=True)
class Milestone:
    key: str  # trwały identyfikator (np. `pregnancy-certificate`)
    title: str
    summary: str
    due: date
    child_id: str


def _fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def milestones_for(children: list[Child], today: date) -> list[Milestone]:
    """Kamienie milowe dla dzieci w drodze i niedawno urodzonych (bez dzieci w sytuacji straty)."""
    out: list[Milestone] = []
    for c in children:
        if c.situation == "loss":
            continue
        if c.status == "expected" and c.due_date:
            cert = c.due_date - timedelta(days=CERTIFICATE_DAYS_BEFORE_DUE)
            out.append(
                Milestone(
                    key="pregnancy-certificate",
                    title=f"Zaświadczenie lekarskie o ciąży dla pracodawcy ({c.name})",
                    summary=(
                        "Weź od lekarza prowadzącego zaświadczenie o ciąży i terminie porodu: pracodawca potrzebuje go "
                        f"do wniosku o urlop macierzyński. Orientacyjnie na około {_fmt(cert)} "
                        "(urlop można zacząć do 6 tygodni przed porodem, wniosek składa się z wyprzedzeniem)."
                    ),
                    due=cert,
                    child_id=c.id,
                )
            )
            usc = c.due_date + timedelta(days=USC_DAYS_AFTER_BIRTH)
            out.append(
                Milestone(
                    key="usc-registration",
                    title=f"Zgłoszenie urodzenia w USC ({c.name})",
                    summary=(
                        f"Urodzenie dziecka zgłasza się w urzędzie stanu cywilnego do {USC_DAYS_AFTER_BIRTH} dni od porodu "
                        f"(przy terminie porodu {_fmt(c.due_date)}: około {_fmt(usc)}). Szpital często robi to za Was. "
                        "Zapytaj, czy tak jest. Numer PESEL dziecka jest potrzebny do kolejnych wniosków."
                    ),
                    due=usc,
                    child_id=c.id,
                )
            )
        elif c.status == "born" and c.birth_date:
            usc = c.birth_date + timedelta(days=USC_DAYS_AFTER_BIRTH)
            if usc < today - timedelta(days=USC_GRACE_DAYS):
                continue  # starsze dziecko: rejestracja dawno załatwiona
            out.append(
                Milestone(
                    key="usc-registration",
                    title=f"Zgłoszenie urodzenia w USC ({c.name})",
                    summary=(
                        f"Urodzenie dziecka zgłasza się w urzędzie stanu cywilnego do {USC_DAYS_AFTER_BIRTH} dni od porodu "
                        f"(do {_fmt(usc)}). Jeśli szpital już to zrobił, odznacz ten wpis."
                    ),
                    due=usc,
                    child_id=c.id,
                )
            )
    return out
