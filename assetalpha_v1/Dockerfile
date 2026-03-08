# ============================================================
# AssetAlpha v14.0 — Dockerfile
# Multi-stage build: меньший образ, нет build-зависимостей в production
# ============================================================

# ── Stage 1: Build ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Системные зависимости для компиляции (gcc нужен для bcrypt, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production ─────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Копируем установленные пакеты из builder (без компилятора — образ меньше)
COPY --from=builder /install /usr/local

# Только runtime зависимости (libpq для psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Код приложения
COPY . .

# Непривилегированный пользователь — безопасность
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /home/appuser/.cache/py-yfinance \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# Порт
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Запуск — миграции применяются через docker-compose command
# При запуске без compose: alembic upgrade head && uvicorn main:app ...
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
