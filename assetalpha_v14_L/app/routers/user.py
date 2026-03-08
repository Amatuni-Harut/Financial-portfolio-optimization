"""
routers/user.py — Уровень знаний пользователя.

Исправление v13.2:
- УДАЛЁН app.state.user_level (был один глобальный для всех!)
- GET /api/user/level читает уровень из JWT (per-user)
- POST /api/user/level сохранён для совместимости с фронтендом,
  но теперь сохраняет в БД и возвращает новый токен
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends
from app.models import KnowledgeLevel, UserLevelRequest, UserLevelResponse
from app.routers.auth import get_current_level, require_user, _create_token, _get_user
from app.database import get_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["User"])

_MESSAGES = {
    KnowledgeLevel.beginner:     "Режим новичка активирован.",
    KnowledgeLevel.professional: "Профессиональный режим активирован.",
}


@router.get("/level", response_model=UserLevelResponse)
async def get_user_level(level: KnowledgeLevel = Depends(get_current_level)):
    """Возвращает уровень из JWT токена (per-user, не глобальный)."""
    return UserLevelResponse(level=level, message=_MESSAGES[level])


@router.post("/level", response_model=UserLevelResponse)
async def set_user_level(
    body: UserLevelRequest,
    username: Optional[str] = Depends(require_user),
):
    """
    Устанавливает уровень знаний.
    Сохраняет в БД если пользователь авторизован.
    """
    engine = get_engine()
    if engine and username:
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE public.users SET knowledge_level = :l WHERE username = :u"),
                    {"l": body.level.value, "u": username},
                )
                conn.commit()
            logger.info(f"Уровень {username} -> {body.level.value}")
        except Exception as exc:
            logger.error(f"set_user_level: {exc}")

    return UserLevelResponse(level=body.level, message=_MESSAGES[body.level])
