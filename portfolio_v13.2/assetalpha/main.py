"""
main.py — Точка входа FastAPI приложения AssetAlpha v13.2

Исправления:
- Версия из app.__version__ (единый источник)
- dispose_engine() — синхронный вызов (совместим с sync database.py)
- УДАЛЁН app.state.user_level (уровень теперь в JWT per-user)
- allow_credentials=False явно задан в CORS
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import assets, markets, optimize, system, user
from app.routers import auth as auth_router
from app.services.data_service import configure_cache, startup_preload
from app.database import init_engine, dispose_engine, init_users_table
from config import configure_logging, get_settings

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Версия приложения
try:
    from app.__version__ import __version__, APP_TITLE
except ImportError:
    __version__ = "13.2.0"
    APP_TITLE   = "AssetAlpha API"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"AssetAlpha API {__version__} запускается...")

    # Sync engine — совместим с data_service.py
    init_engine(settings.db_url)

    # Таблицы
    init_users_table()

    # Кэш
    configure_cache(settings.cache_ttl_hours)

    # УДАЛЕНО: app.state.user_level — уровень хранится в JWT

    # Предзагрузка данных (DB-first)
    import asyncio
    asyncio.create_task(startup_preload())

    logger.info("Инициализация завершена")
    yield

    # Остановка — sync dispose
    dispose_engine()
    logger.info(f"AssetAlpha API {__version__} остановлен")


app = FastAPI(
    title=APP_TITLE,
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.warning(f"Ошибка валидации 422: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )


# Статические файлы
if FRONTEND_DIR.exists():
    for subfolder in ("css", "js"):
        path = FRONTEND_DIR / subfolder
        if path.exists():
            app.mount(f"/{subfolder}", StaticFiles(directory=str(path)), name=subfolder)
else:
    logger.warning(f"Папка frontend не найдена: {FRONTEND_DIR}")


# HTML роуты
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


# API роутеры
app.include_router(system.router)
app.include_router(auth_router.router)
app.include_router(user.router)
app.include_router(assets.router)
app.include_router(optimize.router)
app.include_router(markets.router)
