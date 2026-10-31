from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])
    max_upload_mb: int = 10
    log_level: str = "INFO"
    model_path: Path = Path(__file__).resolve().parents[1] / "models" / "ecg_apnea_hrv_lr_v2.joblib"
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    gemini_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    gemini_max_retries: int = Field(default=2, ge=0, le=3)
    gemini_temperature: float = Field(default=0.2, ge=0, le=1)
    gemini_max_output_tokens: int = Field(default=512, ge=64, le=2048)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()