"""
config.py — Централизованная конфигурация AssetAlpha v13.2
"""
import logging
import json
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # База данных
    db_url: str = ""

    # JWT
    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING_32chars",
        description="Секретный ключ для JWT. Минимум 32 символа.",
    )
    access_token_expire_minutes: int = 60 * 24  # 24 часа

    # CORS
    cors_origins: str = Field(
        default="http://localhost:8000",
        validation_alias="cors_origins",
    )

    # Кэш
    cache_ttl_hours: int = 4

    # Логирование
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level должен быть одним из {allowed}")
        return upper

    @property
    def cors_origins_list(self) -> List[str]:
        v = self.cors_origins.strip()
        if v.startswith("["):
            try:
                return json.loads(v)
            except Exception:
                pass
        return [o.strip() for o in v.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
