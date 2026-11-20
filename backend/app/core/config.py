from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agile Project Management Tool"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "sqlite:///./data/agile_pm.db"
    secret_key: str = "dev-insecure-secret-key-change-in-production"
    session_cookie_name: str = "agile_pm_session"
    session_cookie_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 24 * 7
    csrf_cookie_name: str = "agile_pm_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 60
    login_ip_rate_limit_max_attempts: int = 15
    login_ip_rate_limit_window_seconds: int = 60
    login_account_backoff_base_seconds: float = 0.05
    login_account_backoff_max_seconds: float = 1.0
    login_account_backoff_window_seconds: int = 300
    register_rate_limit_max_attempts: int = 10
    register_rate_limit_window_seconds: int = 60
    max_request_body_bytes: int = 1_048_576
    sse_max_streams_per_user: int = 3
    sse_max_lifetime_seconds: float = 1800.0
    sse_poll_interval_seconds: float = 1.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
