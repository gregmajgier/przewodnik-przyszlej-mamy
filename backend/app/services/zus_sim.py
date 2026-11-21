"""Symulacja mObywatela/ZUS za jednym interfejsem: `fetch_zus_data(persona_id, today)`.

Podmiana na prawdziwe źródło = podmiana tej funkcji; dane person żyją w `app/seed/personas.py`.
"""

from datetime import date, timedelta

from ..errors import DomainError
from ..models.profile import Address, Debt, Ezla, Insurance, KnownChild, ParentProfile
from ..seed.personas import get_persona

_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def _pesel(birth: date, serial: str, female: bool) -> str:
    """Syntetyczny numer o poprawnej sumie kontrolnej (dane wymyślone)."""
    month = birth.month + {1800: 80, 1900: 0, 2000: 20, 2100: 40, 2200: 60}[birth.year // 100 * 100]
    digits = f"{birth.year % 100:02d}{month:02d}{birth.day:02d}{serial}{'2' if female else '1'}"
    check = (10 - sum(int(d) * w for d, w in zip(digits, _PESEL_WEIGHTS)) % 10) % 10
    return f"{digits}{check}"


def user_id_for_persona(persona_id: str) -> str:
    return f"user-{persona_id.removeprefix('persona-')}"


def fetch_zus_data(persona_id: str, today: date) -> ParentProfile:
    persona = get_persona(persona_id)
    if persona is None:
        raise DomainError(404, "Nie znaleziono takiej persony mObywatela.")
    z = persona["zus"]
    birth = today - timedelta(days=z["age_days"])
    return ParentProfile(
        user_id=user_id_for_persona(persona_id),
        first_name=z["first_name"],
        last_name=z["last_name"],
        pesel=_pesel(birth, z["pesel_serial"], z["female"]),
        birth_date=birth,
        address=Address(**z["address"]),
        insurance=[
            Insurance(
                kind=i["kind"],
                payer=i["payer"],
                contribution_base=i["contribution_base"],
                voluntary_sickness=i["voluntary_sickness"],
                since=today - timedelta(days=i["since_days_ago"]),
            )
            for i in z["insurance"]
        ],
        ezla=[
            Ezla(
                code=e["code"],
                from_date=today + timedelta(days=e["from_days"]),
                to_date=today + timedelta(days=e["to_days"]),
            )
            for e in z["ezla"]
        ],
        contribution_debt=(
            Debt(
                amount=z["contribution_debt"]["amount"],
                since=today - timedelta(days=z["contribution_debt"]["since_days_ago"]),
            )
            if z["contribution_debt"]
            else None
        ),
        known_children=[
            KnownChild(
                name=c["name"],
                birth_date=today - timedelta(days=c["birth_days_ago"]) if "birth_days_ago" in c else None,
                due_date=today + timedelta(days=c["due_in_days"]) if "due_in_days" in c else None,
            )
            for c in z["known_children"]
        ],
    )
