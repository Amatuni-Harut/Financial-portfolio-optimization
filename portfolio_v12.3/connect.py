"""
connect.py — Загрузка исторических данных через yfinance и сохранение в PostgreSQL.

Изменения v7:
- Логирование через logger вместо print()
- Убрана дублирующаяся строка вывода (была два раза "[OK] Данные обновлены")
- Конфигурация через config.py вместо прямого os.getenv()
"""
import logging

import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text

from config import get_settings

logger = logging.getLogger(__name__)

TICKERS_DEFAULT = ["AAPL", "AMGN", "HON", "MSFT", "NVDA"]


def process_data(tickers_to_download=None):
    """
    Загружает 5-летнюю историю цен для указанных тикеров
    и сохраняет в таблицу public.prices в PostgreSQL.
    """
    settings = get_settings()
    engine = create_engine(settings.db_url)

    tickers = tickers_to_download if tickers_to_download is not None else TICKERS_DEFAULT
    total = len(tickers)
    all_data = []

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

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        conn.commit()

    logger.info(f"Сохранение в БД: {len(final_df)} строк")
    final_df.to_sql("prices", engine, schema="public", if_exists="replace", index=False)

    with engine.connect() as conn:
        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_ticker ON public.prices ("Ticker")'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_date   ON public.prices ("Date")'))
        conn.commit()

    logger.info(f"Данные обновлены в public.prices. Строк: {len(final_df)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    process_data()
