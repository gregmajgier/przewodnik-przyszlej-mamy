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

    @property
    def is_production(self) -> bool:
        """Produkcja = ENV != dev albo podłączony Cosmos (prawdziwe dane)."""
        return self.env.strip().lower() != "dev" or bool(self.cosmos_endpoint)


settings = Settings()
