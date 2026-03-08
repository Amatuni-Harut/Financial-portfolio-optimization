"""
config.py — Централизованная конфигурация AssetAlpha v14.0

Изменения v14:
- SECRET_KEY: убран небезопасный дефолт — теперь обязательный (Field(...))
- Добавлен валидатор: минимум 32 символа, запрет на дефолтные заглушки
- DB_URL: убран asyncpg — используем только psycopg2 (sync)
- Добавлен rate_limit_auth — лимит запросов на /login и /register
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

    # База данных (sync psycopg2 — asyncpg не используется)
    db_url: str = ""

    # JWT — ОБЯЗАТЕЛЬНЫЙ, без дефолта (Field(...) = нет значения по умолчанию)
    secret_key: str = Field(
        ...,
        description=(
            "Секретный ключ для JWT. Минимум 32 символа. "
            'Генерация: python -c "import secrets; print(secrets.token_hex(32))"'
        ),
    )
    access_token_expire_minutes: int = 60

    # CORS
    cors_origins: str = Field(
        default="http://localhost:8000",
        validation_alias="cors_origins",
    )

    # Кэш
    cache_ttl_hours: int = 4

    # Логирование
    log_level: str = "INFO"

    # Rate limiting — максимум запросов к /login и /register в минуту с одного IP
    rate_limit_auth: int = 5

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        # Список известных небезопасных заглушек
        forbidden_patterns = {
            "change_me_in_production_use_long_random_string_32chars",
            "replace_with_strong_secret_key_min32chars",
            "secret",
            "changeme",
            "your_secret_key",
            "mysecretkey",
        }
        if v.lower() in forbidden_patterns:
            raise ValueError(
                "SECRET_KEY содержит небезопасное значение-заглушку. "
                'Сгенерируйте ключ командой: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY слишком короткий ({len(v)} символов). "
                "Минимум 32 символа."
            )
        return v

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
