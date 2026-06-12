"""Application settings, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql://revenueos:revenueos@localhost:5433/revenueos"

    # App
    app_env: str = "local"
    default_tenant_id: str = "demo-practice-001"

    # LLM
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"

    # Mock services ? localhost for local dev (Phase 3),
    # swapped for service names when agents run in compose.
    mock_eligibility_url: str = "http://localhost:8001"
    mock_clearinghouse_url: str = "http://localhost:8002"
    mock_payer_url: str = "http://localhost:8003"


settings = Settings()
