"""
main.py — Точка входа FastAPI приложения AssetAlpha v7.

Изменения v7:
- main.py стал "тонким": только сборка приложения и lifespan
- Все роуты вынесены в app/routers/
- Engine инициализируется один раз в lifespan (thread-safe)
- Конфигурация через config.py
- Убрана глобальная переменная _user_level (теперь app.state)
- CORS настраивается из конфига
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import KnowledgeLevel
from app.routers import assets, markets, optimize, system, user
from app.services.data_service import configure_cache, startup_preload
from app.database import init_engine, dispose_engine
from config import configure_logging, get_settings

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------
settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# ---------------------------------------------------------------------------
# Lifespan: старт и остановка приложения
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AssetAlpha API v7 запускается...")

    # Инициализируем engine один раз — thread-safe
    init_engine(settings.db_url)

    # Устанавливаем TTL кэша из конфига
    configure_cache(settings.cache_ttl_hours)

    # Начальное состояние уровня пользователя
    app.state.user_level = KnowledgeLevel.beginner

    # Предзагрузка данных: DB-first (yfinance только для новых тикеров)
    import asyncio
    asyncio.create_task(startup_preload())

    logger.info("Инициализация завершена")
    yield

    # Корректное завершение
    dispose_engine()
    logger.info("AssetAlpha API v7 остановлен")


# ---------------------------------------------------------------------------
# Инициализация приложения
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AssetAlpha API",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Обработчики ошибок
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Ошибка валидации 422: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


# ---------------------------------------------------------------------------
# Статические файлы (frontend)
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    for subfolder in ("css", "js"):
        path = FRONTEND_DIR / subfolder
        if path.exists():
            app.mount(f"/{subfolder}", StaticFiles(directory=str(path)), name=subfolder)
else:
    logger.error(f"Папка frontend не найдена: {FRONTEND_DIR}")


# ---------------------------------------------------------------------------
# HTML роуты
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/index.html", include_in_schema=False)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/login.html", include_in_schema=False)
async def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/markets.html", include_in_schema=False)
async def markets_page():
    return FileResponse(FRONTEND_DIR / "markets.html")

@app.get("/settings.html", include_in_schema=False)
async def settings_page():
    return FileResponse(FRONTEND_DIR / "settings.html")


# ---------------------------------------------------------------------------
# API роутеры
# ---------------------------------------------------------------------------
app.include_router(system.router)
app.include_router(user.router)
app.include_router(assets.router)
app.include_router(optimize.router)
app.include_router(markets.router)
