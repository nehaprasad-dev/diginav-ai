"""Application settings loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the DigiNav backend.

    Values are read from environment variables (or a `.env` file in the
    backend directory during local development).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/diginav"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Admin ---
    admin_token: str = "changeme"

    # --- General ---
    debug: bool = False


settings = Settings()
