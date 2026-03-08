"""
conftest.py — Pytest фикстуры для тестирования AssetAlpha API v13.1.

Изменения v13.1:
- Мок get_connection() (async context manager) вместо get_engine()
- Убран mock для app.state.user_level (его больше нет)
- Добавлена фикстура auth_headers для авторизованных запросов
- pytest-asyncio mode = auto
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from contextlib import asynccontextmanager

# Переопределяем настройки ДО импорта приложения
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-min32charsXXXXXX")
os.environ.setdefault("DB_URL",     "")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8000")
os.environ.setdefault("LOG_LEVEL",  "ERROR")

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Мок-данные
# ---------------------------------------------------------------------------

MOCK_TICKER_NAMES = {
    "AAPL":  ("Apple Inc.",     "Technology"),
    "GOOGL": ("Alphabet Inc.",  "Technology"),
    "MSFT":  ("Microsoft Corp.","Technology"),
}

MOCK_ASSET_DETAILS = {
    "ticker":      "AAPL",
    "name":        "Apple Inc.",
    "price":       "$150.00",
    "priceRaw":    150.0,
    "change":      "+1.50%",
    "max_price":   "$200.00",
    "mean_return": "12.50%",
    "risk":        "18.30%",
    "sharpe":      0.85,
    "history":     [{"date": "2024-01-01", "price": 145.0}],
}


# ---------------------------------------------------------------------------
# Мок async get_connection
# ---------------------------------------------------------------------------

def make_mock_get_connection(users_store: dict = None):
    """Создаёт мок для async get_connection() context manager."""
    if users_store is None:
        users_store = {}

    @asynccontextmanager
    async def mock_get_connection():
        mock_conn = AsyncMock()

        async def mock_execute(sql, params=None):
            sql_str = str(sql)
            result = MagicMock()
            result.fetchone.return_value = None

            if params and "u" in params and "SELECT" in sql_str:
                username = params["u"]
                user = users_store.get(username)
                if user:
                    row = MagicMock()
                    row._mapping = user
                    result.fetchone.return_value = row

            return result

        mock_conn.execute = mock_execute
        mock_conn.commit  = AsyncMock()
        yield mock_conn

    return mock_get_connection


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def patch_heavy_deps():
    mock_data_service = MagicMock()
    mock_data_service.get_available_tickers.return_value = list(MOCK_TICKER_NAMES.keys())
    mock_data_service.get_asset_details.return_value     = MOCK_ASSET_DETAILS.copy()
    mock_data_service.configure_cache.return_value       = None
    mock_data_service.clear_cache                        = MagicMock(return_value=None)

    async_startup = AsyncMock(return_value=None)

    with (
        patch("app.services.data_service.get_available_tickers", mock_data_service.get_available_tickers),
        patch("app.services.data_service.get_asset_details",     mock_data_service.get_asset_details),
        patch("app.services.data_service.configure_cache",       mock_data_service.configure_cache),
        patch("app.services.data_service.startup_preload",       async_startup),
        patch("app.services.data_service.clear_cache",           mock_data_service.clear_cache),
        patch("app.database.init_engine",      return_value=None),
        patch("app.database.init_users_table", new_callable=AsyncMock),
        patch("app.database.dispose_engine",   new_callable=AsyncMock),
    ):
        yield mock_data_service


@pytest.fixture(scope="session")
def client(patch_heavy_deps):
    """TestClient для всей сессии тестов."""
    from config import get_settings
    get_settings.cache_clear()

    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_db():
    """In-memory хранилище пользователей для тестов auth."""
    users_store: dict = {}
    mock_conn_factory = make_mock_get_connection(users_store)

    with patch("app.routers.auth.get_connection", mock_conn_factory):
        yield users_store


@pytest.fixture
def auth_headers(client, mock_db):
    """Возвращает заголовки с валидным JWT токеном."""
    import bcrypt
    password = "testpassword123"
    hashed   = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    mock_db["testuser"] = {
        "username":         "testuser",
        "hashed_password":  hashed,
        "email":            "test@example.com",
        "knowledge_level":  "beginner",
        "created_at":       "2024-01-01",
    }
    r = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": password},
    )
    token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
