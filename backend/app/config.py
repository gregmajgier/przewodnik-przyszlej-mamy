from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SESSION_SECRET = "dev-secret-change-me"
DEFAULT_OFFICIAL_PASSWORD = "demo1234"
MIN_SESSION_SECRET_LENGTH = 32
MIN_OFFICIAL_PASSWORD_LENGTH = 12


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "dev" (domyślnie, lokalnie i w testach) albo cokolwiek innego = produkcja (walidacja fail-closed)
    env: str = "dev"
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "mrodzina"
    cors_origins: list[str] = ["http://localhost:5173"]
    session_secret: str = DEFAULT_SESSION_SECRET
    session_ttl_hours: int = 12
    official_default_password: str = DEFAULT_OFFICIAL_PASSWORD

    # AI (plan 02). Bez endpointu i klucza działa DemoLLM (offline).
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-5.4-nano"
    azure_openai_api_version: str = "2025-04-01-preview"
    # Modele z rozumowaniem (gpt-5.x): minimal | low | medium | high. Puste = parametr nie jest wysyłany
    # (np. dla gpt-4o-mini / gpt-4.1-nano, które go nie obsługują).
    azure_openai_reasoning_effort: str = "low"
    ai_max_output_tokens: int = 1500

    # Limity zapytań AI (spec §14). IP z X-Forwarded-For wg TRUST_PROXY_HOPS.
    ai_user_rpm: int = 20
    ai_user_daily: int = 300
    ai_ip_rpm: int = 60
    ai_ip_daily: int = 1000
    ai_daily_tokens: int = 500000
    ai_max_input_chars: int = 8000
    # Ile zaufanych proxy stoi przed aplikacją. 0 = ignoruj X-Forwarded-For; N = bierz N-ty wpis od PRAWEJ
    # (Azure Container Apps ingress: 1). Nigdy nie ufamy wpisom z lewej (kontroluje je klient).
    trust_proxy_hops: int = 0
    # Szacunek tokenów rezerwowany na żądanie AI (rozliczany po odpowiedzi) i limit równoległych żądań AI.
    ai_reserve_tokens: int = 4000
    ai_max_inflight: int = 20

    # Czat (plan 06): wyszukiwarka dla `szukaj_w_sieci`. `none` = brak dostępu do sieci (domyślnie).
    web_search_provider: str = "none"  # none | brave | serper
    web_search_api_key: str = ""
    # Poczta symulowana (plan 09): opóźnienie predefiniowanych odpowiedzi i cykl pobierania (0 = wyłączony).
    mail_sim_reply_delay_s: int = 20
    mail_poll_s: int = 30

    # Przykładowe wnioski „w toku” dla rodziny demo (seed/demo_applications.py). Testy: DEMO_APPLICATIONS=0.
    demo_applications: bool = True

    # Tryb jaskółki (plan 10): ile dni od zgłoszenia można je cofnąć.
    undo_window_days: int = 7

    @property
    def is_production(self) -> bool:
        """Produkcja = ENV != dev albo podłączony Cosmos (prawdziwe dane)."""
        return self.env.strip().lower() != "dev" or bool(self.cosmos_endpoint)


settings = Settings()
