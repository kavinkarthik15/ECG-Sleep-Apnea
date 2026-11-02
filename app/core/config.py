from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])
    max_upload_mb: int = 10
    log_level: str = "INFO"
    model_path: Path = Path(__file__).resolve().parents[1] / "models" / "ecg_apnea_hrv_lr_v2.joblib"
    database_url: SecretStr | None = None
    database_dns_over_https: bool = False
    database_dns_over_https_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    session_cookie_name: str = "ecg_visitor_session"
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "lax"
    cron_secret: SecretStr | None = None
    assistant_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    ollama_read_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openrouter_app_name: str | None = None
    openrouter_app_url: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict, or none.")
        return normalized

    @model_validator(mode="after")
    def validate_cookie_security(self) -> "Settings":
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires a Secure session cookie.")
        if self.app_env.lower() in {"production", "prod"} and not self.session_cookie_secure:
            raise ValueError("Session cookies must be Secure in production.")
        return self

    @field_validator("openrouter_model")
    @classmethod
    def validate_openrouter_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.endswith(":free"):
            raise ValueError("OPENROUTER_MODEL must identify an explicitly free model ending in :free.")
        return normalized

    @field_validator("assistant_provider")
    @classmethod
    def validate_assistant_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"ollama", "openrouter"}:
            raise ValueError("ASSISTANT_PROVIDER must be ollama or openrouter.")
        return normalized

    @model_validator(mode="after")
    def validate_database_dns_workaround(self) -> "Settings":
        database_url = self.database_url.get_secret_value() if self.database_url else ""
        if (
            self.database_dns_over_https
            and self.app_env.lower() in {"production", "prod"}
            and not database_url.startswith("sqlite")
        ):
            raise ValueError("DATABASE_DNS_OVER_HTTPS is only supported in local development or tests.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()