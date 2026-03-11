"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    vllm_base_url: str = "http://localhost:7777"
    vllm_model: str = "Qwen/Qwen3.5-9B"
    database_path: str = "data/chat.db"
    origin: str = "http://localhost:3080"
    session_cookie_name: str = "simon_session"
    session_max_age_hours: int = 168
    session_cookie_secure: bool = False
    api_key_revocation_retention_minutes: int = 5

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
