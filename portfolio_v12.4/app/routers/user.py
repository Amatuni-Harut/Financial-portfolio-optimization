"""
routers/user.py — Управление уровнем знаний пользователя.

Изменения v12:
- Убрана _bootstrap_if_needed: предзагрузка теперь происходит при старте uvicorn,
  не при входе пользователя.
- Роутер стал чище — только управление уровнем знаний.
"""
import logging

from fastapi import APIRouter, Request

from app.models import KnowledgeLevel, UserLevelRequest, UserLevelResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["User"])

_LEVEL_MESSAGES = {
    KnowledgeLevel.beginner:     "Режим новичка активирован.",
    KnowledgeLevel.professional: "Профессиональный режим активирован.",
}


@router.post("/level", response_model=UserLevelResponse)
async def set_user_level(
    request: Request,
    body: UserLevelRequest,
):
    """Устанавливает уровень знаний пользователя."""
    request.app.state.user_level = body.level
    logger.info(f"Уровень знаний установлен: {body.level}")
    return UserLevelResponse(level=body.level, message=_LEVEL_MESSAGES[body.level])


@router.get("/level", response_model=UserLevelResponse)
async def get_user_level(request: Request):
    """Возвращает текущий уровень знаний пользователя."""
    level = getattr(request.app.state, "user_level", KnowledgeLevel.beginner)
    return UserLevelResponse(level=level, message="OK")
