"""Application settings, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql://revenueos:revenueos@localhost:5432/revenueos"

    # App
    app_env: str = "local"
    default_tenant_id: str = "demo-practice-001"

    # LLM (used from Phase 3)
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"


settings = Settings()
