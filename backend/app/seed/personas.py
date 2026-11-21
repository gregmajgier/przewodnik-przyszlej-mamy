"""Persony mObywatela (dane wymyślone). Dodanie persony = dodanie wpisu, bez zmian w kodzie logiki.

Klucz `zus` opisuje dane „z ZUS” względem dnia uruchomienia (przesunięcia w dniach).
Klucz `employment_docs` to umowy „z e-teczki pracodawcy”: z nich generujemy PDF-y, które rodzic dodaje w onboardingu.
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
        "employment_docs": [
            {
                "id": "umowa-o-prace-kcuw",
                "kind": "employment",
                "employer_name": "Krakowskie Centrum Usług Wspólnych Sp. z o.o.",
                "employer_address": "ul. Lubicz 23, 31-503 Kraków",
                "employer_email": "kadry@kcuw.example.pl",
                "position": "Specjalistka ds. kadr i płac",
                "fte": 1.0,
                "gross_monthly": 7850.0,
                "start_days_ago": 5 * 365,
                "end_in_days": None,
            },
            {
                "id": "umowa-zlecenia-fundacja",
                "kind": "mandate",
                "employer_name": "Fundacja Rodzinny Kraków",
                "employer_address": "ul. Józefa 14, 31-056 Kraków",
                "employer_email": "biuro@rodzinnykrakow.example.pl",
                "position": "Prowadzenie warsztatów dla przyszłych rodziców",
                "gross_monthly": 1200.0,
                "start_days_ago": 240,
                "end_in_days": 120,
                "voluntary_sickness": True,
            },
        ],
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
        "employment_docs": [
            {
                "id": "umowa-o-prace-mhb",
                "kind": "employment",
                "employer_name": "Małopolska Hurtownia Budowlana S.A.",
                "employer_address": "ul. Półłanki 18, 30-740 Kraków",
                "employer_email": "kadry@mhb.example.pl",
                "position": "Kierownik magazynu",
                "fte": 1.0,
                "gross_monthly": 6400.0,
                "start_days_ago": 8 * 365,
                "end_in_days": None,
            },
            {
                "id": "umowa-zlecenia-bhp",
                "kind": "mandate",
                "employer_name": "Akademia BHP Partner Sp. z o.o.",
                "employer_address": "ul. Zakopiańska 62, 30-418 Kraków",
                "employer_email": "zlecenia@bhppartner.example.pl",
                "position": "Prowadzenie szkoleń BHP dla magazynierów",
                "gross_monthly": 1500.0,
                "start_days_ago": 150,
                "end_in_days": 210,
                "voluntary_sickness": True,
            },
        ],
    },
}


def get_persona(persona_id: str) -> dict | None:
    return PERSONAS.get(persona_id)
