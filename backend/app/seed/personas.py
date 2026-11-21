"""Persony mObywatela (dane wymyślone). Dodanie persony = dodanie wpisu, bez zmian w kodzie logiki."""

PERSONAS: dict[str, dict] = {
    "persona-nowak-anna": {
        "id": "persona-nowak-anna",
        "name": "Anna Nowak",
        "role_label": "Mama, 31 lat, Kraków — w ciąży z trzecim dzieckiem",
    },
    "persona-nowak-piotr": {
        "id": "persona-nowak-piotr",
        "name": "Piotr Nowak",
        "role_label": "Tata, 34 lata, Kraków",
    },
}


def get_persona(persona_id: str) -> dict | None:
    return PERSONAS.get(persona_id)
