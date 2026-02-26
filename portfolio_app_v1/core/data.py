import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DB_URL"))

def load_ohlc(ticker: str) -> dict:
    # Явно указываем public.prices
    query = f"""
        SELECT "Date", "Open", "High", "Low", "Close" 
        FROM public.prices 
        WHERE "Ticker" = '{ticker}' 
        ORDER BY "Date"
    """
    df = pd.read_sql(query, engine)

    if df.empty:
        raise ValueError(f"Нет данных для {ticker}")

    return {
        "date":  df["Date"].tolist(),
        "open":  df["Open"].tolist(),
        "high":  df["High"].tolist(),
        "low":   df["Low"].tolist(),
        "close": df["Close"].tolist(),
    }

def load_all_tickers(tickers: list[str]) -> dict:
    result = {}
    for ticker in tickers:
        try:
            result[ticker] = load_ohlc(ticker)
            print(f"  [OK] {ticker} загружен")
        except Exception as e:
            print(f"  (!) Ошибка загрузки {ticker}: {e}")
    return result