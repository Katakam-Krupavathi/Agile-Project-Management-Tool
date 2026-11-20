from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SECRET_KEY = "dev-insecure-secret-key-change-in-production"
_INSECURE_SECRET_KEYS = frozenset(
    {
        DEFAULT_DEV_SECRET_KEY,
        "change-me-to-a-long-random-secret",
        "change-me-in-production-to-a-long-random-string",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agile Project Management Tool"
    app_env: str = "development"
    debug: bool = False
    enable_api_docs: bool | None = None
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "sqlite:///./data/agile_pm.db"
    secret_key: str = DEFAULT_DEV_SECRET_KEY
    session_cookie_name: str = "agile_pm_session"
    session_cookie_secure: bool | None = None
    session_max_age_seconds: int = 60 * 60 * 24 * 7
    csrf_cookie_name: str = "agile_pm_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    forwarded_allow_ips: str = "127.0.0.1"
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
    report_cooldown_seconds: int = 30
    report_retention_max_per_project: int = 20
    job_cleanup_retention_days: int = 7
    worker_maintenance_interval_seconds: float = 30.0
    worker_lock_heartbeat_interval_seconds: float = 60.0
    worker_heartbeat_file: str = "./data/worker_heartbeat"
    worker_heartbeat_max_age_seconds: float = 30.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        is_prod = self.app_env.strip().lower() == "production"
        if self.session_cookie_secure is None:
            self.session_cookie_secure = is_prod
        if self.enable_api_docs is None:
            self.enable_api_docs = not is_prod
        if is_prod and (
            self.secret_key in _INSECURE_SECRET_KEYS or len(self.secret_key.strip()) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be a non-default secret of at least 32 characters in production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
