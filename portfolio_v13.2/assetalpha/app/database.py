"""
database.py — Управление соединением с базой данных.

Использует синхронный SQLAlchemy engine (psycopg2).
data_service.py работает именно с sync engine — не меняем.

Исправления v13.2:
- Добавлена колонка knowledge_level в таблицу users
- dispose_engine() — синхронный (совместим с lifespan)
"""
import logging
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None


def _clean_db_url(db_url: str) -> str:
    """
    Убирает asyncpg из URL если он там есть.
    data_service использует psycopg2 (sync), не asyncpg.
    """
    return (
        db_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://",   "postgresql://")
    )


def init_engine(db_url: str) -> Optional[Engine]:
    """
    Создаёт синхронный SQLAlchemy engine.
    Вызывается один раз при старте приложения в lifespan.
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


def init_users_table() -> None:
    """
    Создаёт таблицу users если не существует.
    Включает колонку knowledge_level для хранения уровня per-user.
    """
    engine = _engine
    if engine is None:
        logger.warning("DB недоступна — таблица users не создана")
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.users (
                    id               SERIAL PRIMARY KEY,
                    username         TEXT UNIQUE NOT NULL,
                    email            TEXT,
                    hashed_password  TEXT NOT NULL,
                    knowledge_level  TEXT NOT NULL DEFAULT 'beginner',
                    created_at       TIMESTAMP DEFAULT NOW()
                )
            """))
            # Добавляем knowledge_level если таблица уже существует без неё
            conn.execute(text("""
                ALTER TABLE public.users
                ADD COLUMN IF NOT EXISTS knowledge_level TEXT NOT NULL DEFAULT 'beginner'
            """))
            conn.commit()
        logger.info("Таблица users готова")
    except Exception as exc:
        logger.error(f"init_users_table: {exc}")


def dispose_engine() -> None:
    """Закрывает все соединения пула. Вызывается при остановке приложения."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        logger.info("Пул соединений с БД закрыт")
        _engine = None
