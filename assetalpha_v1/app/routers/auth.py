"""
routers/auth.py — Аутентификация. AssetAlpha v14.0

Изменения v14:
- Добавлен rate limiting на /login и /register (защита от brute-force)
  Реализован через простой in-memory счётчик с TTL (без внешних зависимостей).
  Лимит настраивается через settings.rate_limit_auth (default: 5 req/min).
- knowledge_level хранится в БД и передаётся в JWT payload (per-user, из v13.2)
- Sync engine через get_engine() — совместим с data_service
"""
import logging
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text

from app.database import get_engine
from app.models import KnowledgeLevel
from config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ALGORITHM = "HS256"


# ─── Rate Limiter (in-memory, без Redis) ─────────────────────────────────────

class _RateLimiter:
    """
    Простой in-memory rate limiter по IP-адресу.
    Thread-safe через threading.Lock.
    Лимит: max_calls запросов в window_seconds секунд.
    """
    def __init__(self, max_calls: int = 5, window_seconds: int = 60):
        self._max_calls      = max_calls
        self._window_seconds = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            # Удаляем устаревшие записи
            self._calls[key] = [t for t in self._calls[key] if t > cutoff]
            if len(self._calls[key]) >= self._max_calls:
                return False
            self._calls[key].append(now)
            return True

    def seconds_until_reset(self, key: str) -> int:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            valid = [t for t in self._calls[key] if t > cutoff]
            if not valid:
                return 0
            oldest = min(valid)
            return max(0, int(self._window_seconds - (now - oldest)) + 1)


_auth_limiter = _RateLimiter(
    max_calls=settings.rate_limit_auth,
    window_seconds=60,
)


def _get_client_ip(request: Request) -> str:
    """Извлекает IP клиента с учётом reverse proxy (X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    """Проверяет лимит запросов. Вызывать в начале /login и /register."""
    ip = _get_client_ip(request)
    if not _auth_limiter.is_allowed(ip):
        wait = _auth_limiter.seconds_until_reset(ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много попыток. Попробуйте через {wait} секунд.",
            headers={"Retry-After": str(wait)},
        )


# ─── Pydantic модели ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str            = Field(..., min_length=3, max_length=50)
    password: str            = Field(..., min_length=6)
    email:    Optional[EmailStr] = None


class TokenResponse(BaseModel):
    access_token:    str
    token_type:      str            = "bearer"
    username:        str
    knowledge_level: KnowledgeLevel = KnowledgeLevel.beginner


class MeResponse(BaseModel):
    username:        str
    email:           Optional[str]
    created_at:      Optional[str]
    knowledge_level: KnowledgeLevel


# ─── Криптография ─────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _create_token(username: str, level: KnowledgeLevel = KnowledgeLevel.beginner) -> str:
    """JWT с username И knowledge_level. Per-user, нет глобального state."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": username, "level": level.value, "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _get_user(username: str) -> Optional[dict]:
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, email, hashed_password, knowledge_level, created_at "
                    "FROM public.users WHERE username = :u"
                ),
                {"u": username},
            ).fetchone()
        return dict(row._mapping) if row else None
    except Exception as exc:
        logger.error(f"_get_user: {exc}")
        return None


# ─── Dependencies ─────────────────────────────────────────────────────────────

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_level(token: Optional[str] = Depends(oauth2_scheme)) -> KnowledgeLevel:
    """Читает knowledge_level из JWT. Per-user, не глобальный."""
    if token is None:
        return KnowledgeLevel.beginner
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return KnowledgeLevel(payload.get("level", "beginner"))
    except (JWTError, ValueError):
        return KnowledgeLevel.beginner


async def require_user(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    user = await get_current_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ─── Эндпоинты ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: Request, body: RegisterRequest):
    """Регистрация нового пользователя. Rate limited: 5 запросов/мин с одного IP."""
    _check_rate_limit(request)  # защита от брутфорса

    engine = get_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="База данных недоступна")

    if _get_user(body.username):
        raise HTTPException(status_code=409, detail="Пользователь уже существует")

    hashed = _hash_password(body.password)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.users (username, email, hashed_password) "
                    "VALUES (:u, :e, :h)"
                ),
                {"u": body.username, "e": body.email, "h": hashed},
            )
            conn.commit()
    except Exception as exc:
        logger.error(f"register: {exc}")
        raise HTTPException(status_code=500, detail="Ошибка при создании пользователя")

    logger.info(f"Новый пользователь: {body.username}")
    token = _create_token(body.username, KnowledgeLevel.beginner)
    return TokenResponse(access_token=token, username=body.username)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    """Вход. Rate limited: 5 запросов/мин с одного IP."""
    _check_rate_limit(request)  # защита от брутфорса

    user = _get_user(form.username)
    if user is None or not _verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    level = KnowledgeLevel(user.get("knowledge_level", "beginner"))
    token = _create_token(form.username, level)
    logger.info(f"Вход: {form.username} (level={level.value})")
    return TokenResponse(access_token=token, username=form.username, knowledge_level=level)


@router.get("/me", response_model=MeResponse)
async def me(username: str = Depends(require_user)):
    """Профиль текущего пользователя."""
    user = _get_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return MeResponse(
        username=user["username"],
        email=user.get("email"),
        created_at=str(user.get("created_at", "")),
        knowledge_level=KnowledgeLevel(user.get("knowledge_level", "beginner")),
    )


@router.patch("/level", response_model=TokenResponse)
async def update_level(
    level: KnowledgeLevel,
    username: str = Depends(require_user),
):
    """Меняет уровень знаний. Сохраняет в БД и возвращает новый JWT."""
    engine = get_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="База данных недоступна")
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE public.users SET knowledge_level = :l WHERE username = :u"),
                {"l": level.value, "u": username},
            )
            conn.commit()
    except Exception as exc:
        logger.error(f"update_level: {exc}")
        raise HTTPException(status_code=500, detail="Ошибка обновления уровня")

    new_token = _create_token(username, level)
    logger.info(f"Уровень {username} -> {level.value}")
    return TokenResponse(access_token=new_token, username=username, knowledge_level=level)
