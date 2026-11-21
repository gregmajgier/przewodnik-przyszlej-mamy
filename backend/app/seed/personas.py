"""Persony mObywatela (dane wymyślone). Dodanie persony = dodanie wpisu, bez zmian w kodzie logiki.

Klucz `zus` opisuje dane „z ZUS” względem dnia uruchomienia (przesunięcia w dniach).
"""

_NOWAK_ADDRESS = {
    "city": "Kraków",
    "gmina": "Kraków",
    "powiat": "Kraków",
    "voivodeship": "Małopolskie",
    "postal_code": "30-001",
}

# Dzieci znane z systemów (wspólne dla obojga rodziców): 7 lat, 3 lata i dziecko w drodze (~2 mies.).
_NOWAK_CHILDREN = [
    {"name": "Maja", "birth_days_ago": 7 * 365 + 90},
    {"name": "Antek", "birth_days_ago": 3 * 365 + 120},
    {"name": "Dziecko w drodze", "due_in_days": 60},
]

PERSONAS: dict[str, dict] = {
    "persona-nowak-anna": {
        "id": "persona-nowak-anna",
        "name": "Anna Nowak",
        "role_label": "Mama, 31 lat, Kraków — w ciąży z trzecim dzieckiem",
        "zus": {
            "first_name": "Anna",
            "last_name": "Nowak",
            "female": True,
            "age_days": 31 * 365 + 100,
            "pesel_serial": "123",
            "address": _NOWAK_ADDRESS,
            "insurance": [
                {
                    "kind": "employment",
                    "payer": "Krakowskie Centrum Usług Wspólnych Sp. z o.o.",
                    "contribution_base": 7850.0,
                    "voluntary_sickness": None,
                    "since_days_ago": 5 * 365,
                }
            ],
            "ezla": [{"code": "B", "from_days": -7, "to_days": 21}],
            "contribution_debt": None,
            "known_children": _NOWAK_CHILDREN,
        },
    },
    "persona-nowak-piotr": {
        "id": "persona-nowak-piotr",
        "name": "Piotr Nowak",
        "role_label": "Tata, 34 lata, Kraków",
        "zus": {
            "first_name": "Piotr",
            "last_name": "Nowak",
            "female": False,
            "age_days": 34 * 365 + 40,
            "pesel_serial": "456",
            "address": _NOWAK_ADDRESS,
            "insurance": [
                {
                    "kind": "employment",
                    "payer": "Małopolska Hurtownia Budowlana S.A.",
                    "contribution_base": 6400.0,
                    "voluntary_sickness": None,
                    "since_days_ago": 8 * 365,
                }
            ],
            "ezla": [],
            "contribution_debt": None,
            "known_children": _NOWAK_CHILDREN,
        },
    },
}


def get_persona(persona_id: str) -> dict | None:
    return PERSONAS.get(persona_id)
