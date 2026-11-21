# mRodzina — przewodnik developera

## Szybki start (bez Azure)

Wszystko działa lokalnie bez żadnej konfiguracji: dane w pamięci procesu (`MemoryStore`),
symulowany mObywatel/ZUS.

```bash
# backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000/docs

# frontend (drugi terminal)
cd frontend
npm ci
npm run dev                                   # http://localhost:5173
npm test -- --run && npm run lint && npm run build
```

Wymagania: Python 3.12+, Node 22+.

## Konfiguracja (zmienne środowiskowe, `backend/.env`)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `ENV` | `dev` | `dev` = lokalnie/testy. Dowolna inna wartość (np. `prod`) włącza walidację fail-closed. |
| `SESSION_SECRET` | `dev-secret-change-me` | Klucz HMAC tokenów sesji. Poza `dev` (albo gdy ustawiony `COSMOS_ENDPOINT`) aplikacja **nie wystartuje**, jeśli jest domyślny lub krótszy niż 32 znaki. W `dev` tylko ostrzeżenie w logu. |
| `OFFICIAL_DEFAULT_PASSWORD` | `demo1234` | Hasło początkowe kont urzędników. Seed tworzy tylko brakujące konta i **nigdy nie nadpisuje** istniejących haseł. Poza `dev` (lub z Cosmos) domyślne hasło powoduje pominięcie seedowania urzędników (ostrzeżenie w logu). |
| `SESSION_TTL_HOURS` | `12` | Ważność tokenu. |
| `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE` | puste | Puste = `MemoryStore`. Ustawione = `CosmosStore` i tryb produkcyjny. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Dozwolone originy (JSON). |

Losowy sekret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

**Wdrożenie:** ustaw `ENV=prod`, własny `SESSION_SECRET` i `OFFICIAL_DEFAULT_PASSWORD`
(jako sekrety Container App, nigdy w repo).
