"""
config.py — Централизованное управление конфигурацией.

Все переменные окружения читаются здесь и только здесь.
Используйте get_settings() вместо прямых вызовов os.getenv().
"""
import json
import logging
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения из переменных окружения / .env файла."""

    # --- База данных ---
    db_url: str = ""

    # --- Кэш ---
    cache_ttl_hours: int = 4

    # --- CORS ---
    # Принимает как CORS_ORIGINS_RAW=..., так и CORS_ORIGINS=... (для совместимости с .env)
    # validation_alias позволяет читать значение из CORS_ORIGINS или CORS_ORIGINS_RAW
    cors_origins_raw: str = Field(
        default="http://localhost:8000",
        validation_alias="cors_origins",   # читаем из CORS_ORIGINS в .env
    )

    # --- Логирование ---
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # игнорируем неизвестные переменные из .env
    )

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
        """
        Возвращает список CORS-origins.
        Поддерживает любой из форматов в .env:

            CORS_ORIGINS=*
            CORS_ORIGINS=http://localhost:8000
            CORS_ORIGINS=http://a.com,https://b.com
            CORS_ORIGINS=["http://a.com","https://b.com"]
        """
        v = self.cors_origins_raw.strip()
        if v.startswith("["):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Возвращает синглтон Settings.
    lru_cache гарантирует единственное создание объекта за время жизни процесса.
    """
    return Settings()


def configure_logging(settings: Settings) -> None:
    """Настраивает корневой логгер на основе конфигурации."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
