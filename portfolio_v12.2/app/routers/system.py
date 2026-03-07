"""
routers/system.py — Системные эндпоинты: health check, управление кэшем.
"""
import logging

from fastapi import APIRouter, BackgroundTasks

from app.database import get_engine
from app.services import data_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/health")
async def health():
    """Проверка состояния приложения и подключения к БД."""
    db_ok = False
    try:
        engine = get_engine()
        if engine:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db_connected": db_ok, "version": "2.0.0"}


@router.delete("/cache")
async def clear_cache(background_tasks: BackgroundTasks):
    """Очищает кэш данных в фоновом режиме."""
    background_tasks.add_task(data_service.clear_cache)
    return {"message": "Кэш очищен"}
