from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "mrodzina"
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
