"""
test_auth.py — Тесты аутентификации (/api/auth/*).

Использует in-memory SQLite через фикстуру из conftest, без реального PostgreSQL.
"""
import pytest
from unittest.mock import patch, MagicMock


# ─── Вспомогательные данные ──────────────────────────────────────────────────

TEST_USER = {"username": "testuser_ci", "password": "securepass123"}


# ─── Фикстуры ────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_db(client):
    """
    Мокает _get_user и engine.connect для тестов аутентификации,
    эмулируя in-memory хранилище пользователей.
    """
    users_store: dict = {}

    def fake_get_user(username):
        return users_store.get(username)

    def fake_register_execute(sql, params):
        username = params["u"]
        users_store[username] = {
            "username": params["u"],
            "email": params.get("e"),
            "hashed_password": params["h"],
            "created_at": "2024-01-01 00:00:00",
        }

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute = MagicMock(side_effect=fake_register_execute)
    mock_conn.commit = MagicMock()

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with (
        patch("app.routers.auth._get_user", side_effect=fake_get_user),
        patch("app.routers.auth.get_engine", return_value=mock_engine),
    ):
        yield users_store


# ─── Тесты регистрации ───────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client, mock_db):
        r = client.post("/api/auth/register", json=TEST_USER)
        assert r.status_code == 201

    def test_register_returns_token(self, client, mock_db):
        r = client.post("/api/auth/register", json=TEST_USER)
        data = r.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == TEST_USER["username"]

    def test_register_duplicate_returns_409(self, client, mock_db):
        """Повторная регистрация того же username → 409."""
        import bcrypt
        hashed = bcrypt.hashpw(TEST_USER["password"].encode(), bcrypt.gensalt()).decode()
        mock_db[TEST_USER["username"]] = {
            "username": TEST_USER["username"],
            "hashed_password": hashed,
            "email": None,
            "created_at": "2024-01-01",
        }
        r = client.post("/api/auth/register", json=TEST_USER)
        assert r.status_code == 409

    def test_register_short_username_returns_422(self, client, mock_db):
        """Username короче 3 символов → 422 Validation Error."""
        r = client.post("/api/auth/register", json={"username": "ab", "password": "pass123"})
        assert r.status_code == 422

    def test_register_short_password_returns_422(self, client, mock_db):
        """Пароль короче 6 символов → 422 Validation Error."""
        r = client.post("/api/auth/register", json={"username": "validname", "password": "123"})
        assert r.status_code == 422

    def test_register_without_db_returns_503(self, client):
        """Без БД должен вернуться 503."""
        with patch("app.routers.auth.get_engine", return_value=None):
            r = client.post("/api/auth/register", json=TEST_USER)
            assert r.status_code == 503


# ─── Тесты входа ─────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_wrong_credentials_returns_401(self, client, mock_db):
        """Несуществующий пользователь → 401."""
        r = client.post(
            "/api/auth/login",
            data={"username": "nobody", "password": "wrongpass"},
        )
        assert r.status_code == 401

    def test_login_success_returns_token(self, client, mock_db):
        """Правильные учётные данные → токен."""
        import bcrypt
        hashed = bcrypt.hashpw(TEST_USER["password"].encode(), bcrypt.gensalt()).decode()
        mock_db[TEST_USER["username"]] = {
            "username": TEST_USER["username"],
            "hashed_password": hashed,
            "email": None,
            "created_at": "2024-01-01",
        }
        r = client.post(
            "/api/auth/login",
            data={"username": TEST_USER["username"], "password": TEST_USER["password"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["username"] == TEST_USER["username"]

    def test_login_wrong_password_returns_401(self, client, mock_db):
        """Правильный логин, неправильный пароль → 401."""
        import bcrypt
        hashed = bcrypt.hashpw(b"correct_password", bcrypt.gensalt()).decode()
        mock_db[TEST_USER["username"]] = {
            "username": TEST_USER["username"],
            "hashed_password": hashed,
            "email": None,
            "created_at": "2024-01-01",
        }
        r = client.post(
            "/api/auth/login",
            data={"username": TEST_USER["username"], "password": "wrong_password"},
        )
        assert r.status_code == 401


# ─── Тесты /me ───────────────────────────────────────────────────────────────

class TestMe:
    def test_me_without_token_returns_401(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    def test_me_with_valid_token_returns_200(self, client, mock_db):
        """Регистрируемся, берём токен, проверяем /me."""
        import bcrypt
        hashed = bcrypt.hashpw(TEST_USER["password"].encode(), bcrypt.gensalt()).decode()
        mock_db[TEST_USER["username"]] = {
            "username": TEST_USER["username"],
            "hashed_password": hashed,
            "email": "test@example.com",
            "created_at": "2024-01-01",
        }

        login_r = client.post(
            "/api/auth/login",
            data={"username": TEST_USER["username"], "password": TEST_USER["password"]},
        )
        token = login_r.json()["access_token"]

        me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_r.status_code == 200
        data = me_r.json()
        assert data["username"] == TEST_USER["username"]
