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
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-10-21"
    ai_max_output_tokens: int = 1500

    # Limity zapytań AI (spec §14). Pierwszy adres z X-Forwarded-For tylko gdy TRUST_PROXY=true.
    ai_user_rpm: int = 20
    ai_user_daily: int = 300
    ai_ip_rpm: int = 60
    ai_ip_daily: int = 1000
    ai_daily_tokens: int = 500000
    ai_max_input_chars: int = 8000
    trust_proxy: bool = False

    @property
    def is_production(self) -> bool:
        """Produkcja = ENV != dev albo podłączony Cosmos (prawdziwe dane)."""
        return self.env.strip().lower() != "dev" or bool(self.cosmos_endpoint)


settings = Settings()
