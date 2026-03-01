"""
routers/user.py — Управление уровнем знаний пользователя.

Изменение v7: убрана глобальная переменная _user_level.
Состояние теперь хранится в request.app.state.user_level,
что является стандартным подходом FastAPI для разделяемого состояния приложения.

Примечание: при многопользовательском сценарии следует перенести
уровень в сессию / JWT-токен конкретного пользователя.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.models import KnowledgeLevel, UserLevelRequest, UserLevelResponse
from app.services import data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["User"])

_LEVEL_MESSAGES = {
    KnowledgeLevel.beginner:     "Режим новичка активирован.",
    KnowledgeLevel.professional: "Профессиональный режим активирован.",
}


async def _bootstrap_if_needed() -> None:
    """Запускает первоначальную загрузку данных если БД пустая."""
    try:
        tickers = data_service.get_available_tickers()
        if len(tickers) < 5:
            logger.info("БД пустая — запускаем bootstrap")
            data_service.bootstrap_data()
        else:
            logger.info(f"БД: {len(tickers)} тикеров, bootstrap не нужен")
    except Exception as exc:
        logger.error(f"Bootstrap не удался: {exc}")


@router.post("/level", response_model=UserLevelResponse)
async def set_user_level(
    request: Request,
    body: UserLevelRequest,
    background_tasks: BackgroundTasks,
):
    """Устанавливает уровень знаний пользователя."""
    request.app.state.user_level = body.level
    logger.info(f"Уровень знаний установлен: {body.level}")
    background_tasks.add_task(_bootstrap_if_needed)
    return UserLevelResponse(level=body.level, message=_LEVEL_MESSAGES[body.level])


@router.get("/level", response_model=UserLevelResponse)
async def get_user_level(request: Request):
    """Возвращает текущий уровень знаний пользователя."""
    level = getattr(request.app.state, "user_level", KnowledgeLevel.beginner)
    return UserLevelResponse(level=level, message="OK")
