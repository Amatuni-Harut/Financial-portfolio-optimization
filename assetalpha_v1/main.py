"""
main.py — Точка входа FastAPI приложения AssetAlpha v14.0

Изменения v14:
- ThreadPoolExecutor перенесён в lifespan → app.state.executor
  (устраняет утечку при --workers N: каждый воркер корректно создаёт и закрывает пул)
- УДАЛЁН вызов init_users_table() — схема только через Alembic
- УДАЛЁН app.state.user_level (было убрано в v13.2, подтверждено)
- allow_credentials=False явно задан в CORS
- SECRET_KEY теперь обязателен — приложение не стартует без валидного ключа
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
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
from app.database import init_engine, dispose_engine
from config import configure_logging, get_settings

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

try:
    from app.__version__ import __version__, APP_TITLE
except ImportError:
    __version__ = "14.0.0"
    APP_TITLE   = "AssetAlpha API"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"AssetAlpha API {__version__} запускается...")

    # Sync engine
    init_engine(settings.db_url)

    # Кэш данных
    configure_cache(settings.cache_ttl_hours)

    # ThreadPoolExecutor в lifespan — корректный lifecycle при --workers N
    # Каждый воркер создаёт свой пул и закрывает его при остановке
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="optimizer")
    app.state.executor = executor
    logger.info(f"ThreadPoolExecutor запущен (workers=4)")

    # Предзагрузка данных (DB-first, не блокирует старт)
    asyncio.create_task(startup_preload())

    logger.info("Инициализация завершена")
    yield

    # Graceful shutdown — ждём завершения текущих задач оптимизации
    executor.shutdown(wait=True)
    logger.info("ThreadPoolExecutor остановлен")

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
