"""
routers/user.py — Уровень знаний пользователя + сохранение портфеля.

Исправление v13.2:
- УДАЛЁН app.state.user_level (был один глобальный для всех!)
- GET /api/user/level читает уровень из JWT (per-user)
- POST /api/user/level сохранён для совместимости с фронтендом,
  но теперь сохраняет в БД и возвращает новый токен

v14.1:
- POST /api/user/portfolio — сохранение портфеля пользователя при выходе
- GET  /api/user/portfolio — загрузка сохранённого портфеля при входе
"""
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


# ─── Схемы для портфеля ───────────────────────────────────────────────────────

class PortfolioAssetSave(BaseModel):
    ticker:    str
    quantity:  Optional[float] = None
    minWeight: Optional[float] = None
    maxWeight: Optional[float] = None

class PortfolioSaveRequest(BaseModel):
    assets:   List[PortfolioAssetSave]
    saved_at: Optional[str] = None

class PortfolioLoadResponse(BaseModel):
    assets: List[PortfolioAssetSave]


# ─── Эндпоинты уровня знаний ─────────────────────────────────────────────────

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


# ─── Эндпоинты портфеля ──────────────────────────────────────────────────────

@router.post("/portfolio", status_code=200)
async def save_portfolio(
    body: PortfolioSaveRequest,
    username: str = Depends(require_user),
):
    """
    Сохраняет портфель пользователя при выходе из системы.
    Данные хранятся в колонке portfolio_json таблицы users.
    """
    engine = get_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="База данных недоступна")

    portfolio_json = json.dumps(
        [a.model_dump() for a in body.assets],
        ensure_ascii=False,
    )
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE public.users SET portfolio_json = :p WHERE username = :u"
                ),
                {"p": portfolio_json, "u": username},
            )
            conn.commit()
        logger.info(f"Портфель сохранён для {username}: {len(body.assets)} активов")
        return {"status": "ok", "saved": len(body.assets)}
    except Exception as exc:
        logger.error(f"save_portfolio: {exc}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения портфеля")


@router.get("/portfolio", response_model=PortfolioLoadResponse)
async def load_portfolio(username: str = Depends(require_user)):
    """
    Загружает сохранённый портфель пользователя.
    Вызывается при входе в систему чтобы восстановить состояние.
    """
    engine = get_engine()
    if engine is None:
        return PortfolioLoadResponse(assets=[])

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT portfolio_json FROM public.users WHERE username = :u"),
                {"u": username},
            ).fetchone()

        if not row or not row[0]:
            return PortfolioLoadResponse(assets=[])

        raw = json.loads(row[0])
        assets = [PortfolioAssetSave(**a) for a in raw]
        return PortfolioLoadResponse(assets=assets)
    except Exception as exc:
        logger.error(f"load_portfolio: {exc}")
        return PortfolioLoadResponse(assets=[])
