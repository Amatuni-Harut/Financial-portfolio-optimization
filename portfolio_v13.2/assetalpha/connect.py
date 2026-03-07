"""
connect.py — Загрузка исторических данных через yfinance и сохранение в PostgreSQL.

Исправления v13.1:
- ИСПРАВЛЕНО: if_exists='replace' → безопасный upsert через INSERT ON CONFLICT
  Старое поведение: DROP TABLE + CREATE — потеря всех данных на время загрузки
  Новое поведение: новые записи добавляются, существующие обновляются (no downtime)
- Добавлена поддержка asyncpg URL (автоматически конвертирует в sync для ETL)
- Транзакция на весь batch для атомарности
"""
import logging

import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text

from config import get_settings

logger = logging.getLogger(__name__)

TICKERS_DEFAULT = ["AAPL", "AMGN", "HON", "MSFT", "NVDA"]


def _get_sync_db_url(db_url: str) -> str:
    """
    Конвертирует asyncpg URL в синхронный psycopg2 URL для ETL-скрипта.
    connect.py запускается отдельно, не в async контексте FastAPI.
    """
    return (
        db_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
    )


def _ensure_prices_table(engine) -> None:
    """Создаёт таблицу prices с правильной схемой, если её нет."""
    create_sql = text("""
        CREATE TABLE IF NOT EXISTS public.prices (
            "Ticker"  VARCHAR(20)  NOT NULL,
            "Date"    TIMESTAMP    NOT NULL,
            "Open"    DOUBLE PRECISION,
            "High"    DOUBLE PRECISION,
            "Low"     DOUBLE PRECISION,
            "Close"   DOUBLE PRECISION,
            PRIMARY KEY ("Ticker", "Date")
        )
    """)
    with engine.begin() as conn:
        conn.execute(create_sql)
    logger.info("Таблица public.prices готова.")


def process_data(tickers_to_download=None) -> None:
    """
    Загружает 5-летнюю историю цен для указанных тикеров
    и сохраняет в таблицу public.prices в PostgreSQL.

    Использует UPSERT (INSERT ON CONFLICT DO UPDATE) — не удаляет данные.
    """
    settings   = get_settings()
    sync_url   = _get_sync_db_url(settings.db_url)
    engine     = create_engine(sync_url)
    tickers    = tickers_to_download or TICKERS_DEFAULT
    total      = len(tickers)
    all_data   = []

    for index, symbol in enumerate(tickers, 1):
        logger.info(f"[{index}/{total}] Загрузка: {symbol}")
        try:
            hist = yf.Ticker(symbol).history(period="5y")
            if hist.empty:
                logger.warning(f"Данные для {symbol} не найдены")
                continue

            hist.reset_index(inplace=True)
            hist["Date"] = hist["Date"].dt.tz_localize(None)
            df = hist[["Date", "Open", "High", "Low", "Close"]].copy()
            df["Ticker"] = symbol
            all_data.append(df)

        except Exception as exc:
            logger.error(f"Ошибка загрузки {symbol}: {exc}")

    if not all_data:
        logger.warning("Нет данных для сохранения")
        return

    final_df = pd.concat(all_data, ignore_index=True)

    # Убеждаемся что таблица существует с правильной схемой
    _ensure_prices_table(engine)

    # --- ИСПРАВЛЕНО: UPSERT вместо DROP + CREATE ---
    # Старый код: final_df.to_sql(..., if_exists="replace")  <- удалял ВСЕ данные
    # Новый код:  пакетный INSERT ON CONFLICT DO UPDATE      <- безопасное обновление
    upsert_sql = text("""
        INSERT INTO public.prices ("Ticker", "Date", "Open", "High", "Low", "Close")
        VALUES (:ticker, :date, :open, :high, :low, :close)
        ON CONFLICT ("Ticker", "Date")
        DO UPDATE SET
            "Open"  = EXCLUDED."Open",
            "High"  = EXCLUDED."High",
            "Low"   = EXCLUDED."Low",
            "Close" = EXCLUDED."Close"
    """)

    rows = [
        {
            "ticker": row["Ticker"],
            "date":   row["Date"],
            "open":   row["Open"],
            "high":   row["High"],
            "low":    row["Low"],
            "close":  row["Close"],
        }
        for _, row in final_df.iterrows()
    ]

    logger.info(f"Сохранение в БД: {len(rows)} строк (upsert)...")
    with engine.begin() as conn:
        conn.execute(upsert_sql, rows)

    logger.info(f"Данные обновлены в public.prices. Строк: {len(rows)}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    process_data()
