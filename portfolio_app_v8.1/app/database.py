"""
database.py — Управление соединением с базой данных.

Единственное место создания SQLAlchemy engine.
Инициализация происходит явно при старте приложения (lifespan),
что исключает race condition при одновременных запросах.
"""
import logging
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Хранит единственный экземпляр engine для всего приложения
_engine: Optional[Engine] = None


def init_engine(db_url: str) -> Optional[Engine]:
    """
    Создаёт и возвращает SQLAlchemy engine.
    Вызывается один раз при старте приложения в lifespan.
    """
    global _engine
    if not db_url:
        logger.warning("DB_URL не задан — работаем без базы данных (fallback на yfinance)")
        return None
    try:
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,   # проверять соединение перед использованием
            pool_recycle=1800,    # переиспользовать соединение каждые 30 минут
        )
        # Проверяем подключение сразу
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
