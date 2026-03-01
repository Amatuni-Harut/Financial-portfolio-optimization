"""
config.py — Централизованное управление конфигурацией.

Все переменные окружения читаются здесь и только здесь.
Используйте get_settings() вместо прямых вызовов os.getenv().
"""
import json
import logging
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения из переменных окружения / .env файла."""

    # --- База данных ---
    db_url: str = ""

    # --- Кэш ---
    cache_ttl_hours: int = 4

    # --- CORS ---
    # Тип намеренно str, а не List[str].
    #
    # В pydantic-settings >= 2.1 поля типа List[str] декодируются как JSON
    # ДО запуска @field_validator. Значение "http://localhost:8000"
    # не является JSON-массивом, поэтому парсинг падает с JSONDecodeError.
    # Решение: принимаем как строку, разбираем в свойстве cors_origins_list.
    cors_origins_raw: str = "http://localhost:8000"

    # --- Логирование ---
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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

            CORS_ORIGINS_RAW=*
            CORS_ORIGINS_RAW=http://localhost:8000
            CORS_ORIGINS_RAW=http://a.com,https://b.com
            CORS_ORIGINS_RAW=["http://a.com","https://b.com"]
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
