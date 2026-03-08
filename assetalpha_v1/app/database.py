"""
database.py — Управление соединением с базой данных. AssetAlpha v14.0

Изменения v14:
- УДАЛЕНА init_users_table() — схема управляется ТОЛЬКО через Alembic
- УДАЛЕНА ALTER TABLE в runtime — нет DDL в production коде
- Оставлены: init_engine, get_engine, dispose_engine
- _clean_db_url убирает asyncpg если ошибочно указан в .env
"""
import logging
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None


def _clean_db_url(db_url: str) -> str:
    """
    Гарантирует синхронный psycopg2 URL.
    data_service использует sync engine — asyncpg не совместим.
    """
    return (
        db_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://",   "postgresql://")
    )


def init_engine(db_url: str) -> Optional[Engine]:
    """
    Создаёт синхронный SQLAlchemy engine.
    Вызывается один раз при старте в lifespan.
    Схема БД управляется Alembic (alembic upgrade head) — не здесь.
    """
    global _engine
    if not db_url:
        logger.warning("DB_URL не задан — работаем без базы данных (fallback на yfinance)")
        return None
    try:
        sync_url = _clean_db_url(db_url)
        _engine = create_engine(
            sync_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Соединение с базой данных установлено")
        return _engine
    except Exception as exc:
        logger.error(f"Не удалось подключиться к БД: {exc}")
        _engine = None
        return None


def get_engine() -> Optional[Engine]:
    """Возвращает текущий engine (может быть None если БД недоступна)."""
    return _engine


def dispose_engine() -> None:
    """Закрывает все соединения пула. Вызывается при остановке приложения."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        logger.info("Пул соединений с БД закрыт")
        _engine = None
