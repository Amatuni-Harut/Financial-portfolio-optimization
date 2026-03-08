# AssetAlpha v14.0 — Portfolio Optimization API

## Что исправлено в v14

| # | Проблема | Было (v13.2) | Стало (v14.0) |
|---|----------|--------------|---------------|
| 🔴 | JWT Secret Key небезопасен | `default="CHANGE_ME..."` — стартовал с известным ключом | `Field(...)` — обязательный + валидатор длины (≥32 символа) |
| 🔴 | Двойное управление схемой БД | `init_users_table()` в runtime + Alembic | Только Alembic — `init_users_table()` удалена |
| 🟠 | Нет rate limiting | `/login` и `/register` открыты для brute-force | In-memory лимитер: 5 запросов/мин с одного IP |
| 🟠 | ThreadPoolExecutor без lifecycle | Модульная переменная — утечка при `--workers N` | В `lifespan` → `app.state.executor`, корректный `shutdown(wait=True)` |
| 🟠 | SimpleCache не потокобезопасен | Обычный dict — race condition в ThreadPoolExecutor | `threading.Lock` на все операции get/set/clear |
| 🟠 | `.env.example` с asyncpg | `postgresql+asyncpg://` — несоответствие с кодом | `postgresql://` (psycopg2) — соответствует database.py |
| ➕ | Docker Compose отсутствовал | Только Dockerfile, БД отдельно | `docker-compose.yml` — приложение + PostgreSQL одной командой |

---

## Быстрый старт (локально без Docker)

```bash
# 1. Клонируйте репозиторий
git clone <repo-url>
cd assetalpha

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\Activate.ps1       # Windows

# 3. Зависимости
pip install -r requirements.txt

# 4. Конфигурация — создайте .env из шаблона
cp .env.example .env
# Отредактируйте .env: заполните DB_URL и SECRET_KEY (ОБЯЗАТЕЛЬНО)

# 5. Миграции — создают таблицы users и prices
alembic upgrade head

# 6. Запуск
uvicorn main:app --reload
```

Открыть: http://localhost:8000 | Swagger: http://localhost:8000/docs

---

## Быстрый старт (Docker — приложение + PostgreSQL)

```bash
# 1. Создайте .env из шаблона
cp .env.example .env
# Заполните: POSTGRES_PASSWORD, SECRET_KEY

# 2. Запустите всё одной командой
docker compose up --build

# Фоновый режим
docker compose up -d --build

# Остановка
docker compose down

# Логи
docker compose logs -f api
```

> При первом запуске Docker автоматически:
> — создаёт PostgreSQL контейнер
> — применяет Alembic миграции (`alembic upgrade head`)
> — запускает FastAPI приложение

---

## Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|------------|:---:|-------------|---------|
| `SECRET_KEY` | ✅ | — | JWT ключ, ≥32 символа. Генерация: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_URL` | ✅ (без Docker) | — | `postgresql://user:pass@host:5432/dbname` |
| `POSTGRES_PASSWORD` | ✅ (Docker) | — | Пароль PostgreSQL для docker-compose |
| `POSTGRES_USER` | — | `postgres` | Пользователь PostgreSQL (Docker) |
| `POSTGRES_DB` | — | `assetalpha` | Имя БД (Docker) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `60` | Время жизни JWT токена |
| `CORS_ORIGINS` | — | `http://localhost:8000` | Разрешённые origins |
| `CACHE_TTL_HOURS` | — | `4` | TTL кэша данных |
| `LOG_LEVEL` | — | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `RATE_LIMIT_AUTH` | — | `5` | Макс. запросов к /login и /register в минуту с одного IP |

---

## Структура проекта

```
assetalpha/
├── .env.example              ← Шаблон (в git). НЕ содержит реальных секретов
├── .gitignore                ← .env заблокирован
├── docker-compose.yml        ← Запуск приложения + PostgreSQL одной командой
├── Dockerfile                ← Multi-stage build для production
├── requirements.txt          ← Зависимости Python
├── alembic.ini               ← Конфиг миграций
├── alembic/
│   └── versions/
│       └── 001_initial_schema.py  ← Единственный источник схемы БД
├── main.py                   ← Точка входа + lifespan (executor, engine, cache)
├── config.py                 ← Централизованные настройки + валидаторы
├── app/
│   ├── database.py           ← Sync SQLAlchemy engine (только connect/disconnect)
│   ├── models.py             ← Pydantic схемы
│   ├── routers/
│   │   ├── auth.py           ← Регистрация, вход, rate limiting
│   │   ├── optimize.py       ← Оптимизация портфеля
│   │   ├── markets.py        ← Рыночные данные
│   │   ├── assets.py         ← Поиск тикеров
│   │   ├── user.py           ← Уровень пользователя
│   │   └── system.py         ← Health check
│   └── services/
│       ├── data_service.py   ← DB-first загрузка, thread-safe кэш
│       └── optimizer.py      ← 6 методов оптимизации
└── frontend/                 ← HTML/CSS/JS интерфейс
```

---

## Запуск тестов

```bash
pytest tests/ -v
```
