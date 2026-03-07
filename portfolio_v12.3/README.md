# AssetAlpha — Portfolio Optimization App

## Версия 7

### Что изменилось в v12

| Категория | Было (v6) | Стало (v12) |
|-----------|-----------|-----------|
| Конфигурация | `os.getenv()` разбросан по всем файлам | Централизованный `config.py` (pydantic-settings) |
| DB Engine | Lazy singleton без lock → race condition | Инициализируется в `lifespan`, thread-safe |
| Глобальные переменные | `_user_level`, `global RISK_FREE_MONTHLY` | Убраны. Состояние в `app.state`, параметры через функции |
| Структура роутов | Всё в `main.py` (200+ строк) | Разбито на 5 роутеров в `app/routers/` |
| Запросы к БД | N+1: отдельный запрос на каждый тикер | Batch-запрос: один SQL для всех тикеров |
| Константы | TICKER_NAMES и FALLBACK_TICKERS продублированы в разных местах | Единый `app/constants.py` |
| Логирование | `print()` в connect.py | Везде `logging` |
| Безопасность | `.env` с реальным паролем в коде | `.gitignore`, заполненный `.env.example` |
| CORS | `allow_origins=["*"]` захардкожен | Настраивается через `CORS_ORIGINS` в `.env` |

### Что НЕ изменилось
- Математические алгоритмы оптимизации
- Структура базы данных PostgreSQL
- API контракты (все эндпоинты, параметры, форматы ответов)
- Бизнес-логика

---

## Быстрый старт

```bash
# 1. Клонируйте репозиторий
git clone <repo>
cd portfolio_app_v12

# 2. Создайте виртуальное окружение
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте переменные окружения
cp .env.example .env
# Отредактируйте .env — укажите DB_URL и CORS_ORIGINS

# 5. Запустите сервер
uvicorn main:app --reload
```

Документация API: http://localhost:8000/docs

---

## Структура проекта

```
portfolio_app_v12/
├── .env.example          # Шаблон конфигурации (БЕЗ реальных паролей)
├── .gitignore            # .env и секреты исключены из git
├── requirements.txt      # Зависимости
├── config.py             # Централизованная конфигурация (pydantic-settings)
├── connect.py            # Скрипт загрузки данных через yfinance
├── main.py               # Точка входа FastAPI (тонкий слой)
└── app/
    ├── constants.py      # TICKER_NAMES, FALLBACK_TICKERS (единственный источник)
    ├── database.py       # Управление SQLAlchemy engine
    ├── models.py         # Pydantic схемы (API-контракт)
    ├── routers/
    │   ├── system.py     # GET /health, DELETE /cache
    │   ├── user.py       # POST|GET /api/user/level
    │   ├── assets.py     # GET /api/stocks/search, /api/assets/{ticker}/details
    │   ├── optimize.py   # POST /api/optimize
    │   └── markets.py    # GET /api/markets/all, /api/market/refresh
    └── services/
        ├── data_service.py  # Загрузка, кэширование, построение матриц
        └── optimizer.py     # Движок оптимизации (6 методов)
```

---

## Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|------------|-------------|-------------|---------|
| `DB_URL` | ✅ | — | PostgreSQL connection string |
| `CORS_ORIGINS` | — | `http://localhost:8000` | Разрешённые origins через запятую |
| `CACHE_TTL_HOURS` | — | `4` | Время жизни кэша в часах |
| `LOG_LEVEL` | — | `INFO` | Уровень логирования |

---

## Дальнейшие улучшения (backlog)

- [ ] Добавить аутентификацию (JWT / FastAPI Users)
- [ ] Перейти на asyncpg для неблокирующих запросов к БД
- [ ] Вынести CPU-bound оптимизацию в ProcessPoolExecutor
- [ ] Заменить in-memory кэш на Redis
- [ ] Добавить тесты (pytest + httpx)
- [ ] Настроить Alembic для миграций
- [ ] Dockerfile + docker-compose.yml
- [ ] Исправить расчёт Sortino Ratio и CVaR (сейчас приближённые формулы)
