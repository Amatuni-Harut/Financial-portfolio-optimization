# 🚀 AssetAlpha — Инструкция по установке для нового разработчика

> Инструкция написана для Windows + pgAdmin 4 + Git

---

## ШАГ 1 — Клонировать репозиторий

Открой **PowerShell** или **Git Bash** и выполни:

```bash
git clone https://github.com/ВАШ_АККАУНТ/ВАШ_РЕПОЗИТОРИЙ.git
cd assetalpha
```

> ⚠️ Замени ссылку на реальную из GitHub (кнопка **Code → HTTPS**)

---

## ШАГ 2 — Создать виртуальное окружение Python

```bash
# Создаём виртуальное окружение
python -m venv .venv

# Активируем его (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Если PowerShell не разрешает скрипты — выполни сначала:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

> После активации в терминале появится `(.venv)` слева — это значит окружение активно.

---

## ШАГ 3 — Установить зависимости

```bash
pip install -r requirements.txt
```

Если файл `requirements.txt` отсутствует — установи вручную:

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic pydantic-settings python-jose bcrypt yfinance pandas numpy scipy alembic python-multipart
```

---

## ШАГ 4 — Создать базу данных в pgAdmin 4

1. Открой **pgAdmin 4**
2. В левой панели: **Servers → PostgreSQL → правой кнопкой на "Databases" → Create → Database**
3. В поле **Database** введи имя — например `assetalpha` (можешь выбрать любое своё)
4. Нажми **Save**

> 📌 Запомни: имя пользователя PostgreSQL (обычно `postgres`), пароль, порт (обычно `5432`) и имя БД — они понадобятся на следующем шаге.

---

## ШАГ 5 — Создать файл `.env`

В папке проекта (рядом с `main.py`) создай файл с именем **`.env`**

> ⚠️ Этот файл **не попадает в git** (.gitignore блокирует его) — каждый разработчик создаёт его вручную на своём компьютере.

Скопируй содержимое из `.env.example` и заполни своими данными:

```env
# Строка подключения к PostgreSQL
# Формат: postgresql://ПОЛЬЗОВАТЕЛЬ:ПАРОЛЬ@ХОСТ:ПОРТ/ИМЯ_БД
DB_URL=postgresql://postgres:ВАШ_ПАРОЛЬ@localhost:5432/ВАШ_ИМЯ_БД

# Секретный ключ для JWT — сгенерируй случайную строку (минимум 32 символа)
# Способ 1: просто придумай длинную строку
# Способ 2: запусти в терминале: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=сюда_вставь_длинный_случайный_ключ_минимум_32_символа

# Время жизни токена (в минутах)
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Разрешённые адреса для браузерных запросов
CORS_ORIGINS=http://localhost:8000

# Кэш данных (часы)
CACHE_TTL_HOURS=4

# Уровень логов
LOG_LEVEL=INFO
```

### Пример заполненного `.env`:
```env
DB_URL=postgresql://postgres:mypassword123@localhost:5432/myportfolio
SECRET_KEY=a3f8d92c14e75b6019283746afed9012c4b8e5f17a2930d6c5849102e3f78b4a
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:8000
CACHE_TTL_HOURS=4
LOG_LEVEL=INFO
```

---

## ШАГ 6 — Создать таблицы в базе данных

Проект использует **Alembic** для управления схемой БД. Выполни:

```bash
# Убедись что виртуальное окружение активно (.venv)
alembic upgrade head
```

После этого в твоей БД (в pgAdmin) появятся две таблицы:
- `public.users` — пользователи
- `public.prices` — исторические цены акций

> ✅ Проверь в pgAdmin: открой свою БД → **Schemas → public → Tables**

---

## ШАГ 7 — Запустить сервер

```bash
uvicorn main:app --reload --port 8000
```

Ты должен увидеть в терминале что-то вроде:
```
INFO:     AssetAlpha API 13.2.0 запускается...
INFO:     Соединение с базой данных установлено
INFO:     Таблица users готова
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## ШАГ 8 — Проверить что всё работает

Открой браузер и перейди по адресам:

| Адрес | Что откроется |
|-------|--------------|
| http://localhost:8000 | Страница входа |
| http://localhost:8000/docs | Swagger UI — документация API |
| http://localhost:8000/health | JSON: `{"status": "ok"}` |

---

## ❓ Частые проблемы и решения

### Ошибка: `could not connect to server`
**Причина:** PostgreSQL не запущен или неверный пароль/порт в `.env`  
**Решение:** Проверь что pgAdmin работает и сервис PostgreSQL запущен. Проверь пароль в `.env`.

### Ошибка: `password authentication failed for user "postgres"`
**Причина:** Неверный пароль в DB_URL  
**Решение:** Открой pgAdmin → правой кнопкой на сервере → Properties → Connection — убедись что пароль правильный.

### Ошибка: `database "assetalpha" does not exist`
**Причина:** БД не создана или имя в `.env` не совпадает с именем в pgAdmin  
**Решение:** Создай БД в pgAdmin (Шаг 4) и убедись что имя точно совпадает с `DB_URL` в `.env`.

### Ошибка: `ModuleNotFoundError`
**Причина:** Не установлены зависимости или виртуальное окружение не активировано  
**Решение:**
```bash
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Ошибка: `alembic: command not found`
**Причина:** Alembic не установлен или окружение не активировано  
**Решение:**
```bash
.venv\Scripts\Activate.ps1
pip install alembic
alembic upgrade head
```

### Ошибка: `SECRET_KEY must be at least 32 characters`
**Причина:** SECRET_KEY в `.env` слишком короткий  
**Решение:** Сгенерируй ключ командой:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Вставь результат в `.env` как значение SECRET_KEY.

---

## 📁 Структура проекта (для понимания)

```
assetalpha/
├── .env                  ← СОЗДАЁШЬ ВРУЧНУЮ (в git не попадает!)
├── .env.example          ← Шаблон (уже в git, смотри сюда)
├── .gitignore            ← Блокирует .env и другие секреты
├── main.py               ← Точка входа (запуск uvicorn main:app)
├── config.py             ← Читает настройки из .env
├── alembic.ini           ← Конфиг миграций
├── alembic/
│   └── versions/
│       └── 001_initial_schema.py  ← Миграция: создаёт таблицы users и prices
├── app/
│   ├── database.py       ← Подключение к PostgreSQL
│   ├── models.py         ← Pydantic схемы
│   ├── routers/          ← API эндпоинты
│   └── services/         ← Бизнес-логика и оптимизация
├── frontend/
│   ├── index.html        ← Дашборд
│   ├── login.html        ← Страница входа
│   ├── css/              ← Стили
│   └── js/               ← JavaScript модули
└── tests/                ← Тесты (pytest)
```

---

## 🔄 Рабочий процесс с git (ежедневно)

```bash
# Перед началом работы — получи последние изменения от напарника
git pull origin main

# После своих изменений
git add .
git commit -m "Описание что ты сделал"
git push origin main
```

> ⚠️ **Никогда не делай `git add .env`** — этот файл должен оставаться только у тебя локально.

---

## ✅ Чеклист — всё готово если:

- [ ] Репозиторий склонирован
- [ ] Виртуальное окружение `.venv` активировано
- [ ] `pip install -r requirements.txt` выполнен без ошибок
- [ ] База данных создана в pgAdmin
- [ ] Файл `.env` создан с правильными значениями
- [ ] `alembic upgrade head` выполнен — таблицы появились в pgAdmin
- [ ] `uvicorn main:app --reload` запущен
- [ ] http://localhost:8000 открывается в браузере
