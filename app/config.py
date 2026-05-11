"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    vllm_base_url: str = "http://localhost:7777"
    vllm_model: str = "Qwen/Qwen3.5-9B"
    database_url: str = "postgresql://simon:simon@localhost:5432/simon"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    db_command_timeout: float = 30.0
    origin: str = "http://localhost:3080"
    session_cookie_name: str = "simon_session"
    session_max_age_hours: int = 168
    session_cookie_secure: bool = False
    api_key_revocation_retention_minutes: int = 5
    pdf_parser_url: str = "http://pdf-parser:8080"
    pdf_max_markdown_chars: int = 80000
    pdf_parser_timeout_sec: float = 600.0
    images_dir: str = "data/images"
    image_max_dimension: int = 1568
    image_max_bytes: int = 10 * 1024 * 1024

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
