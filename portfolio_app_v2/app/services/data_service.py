import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_cache: Dict[str, Dict] = {}
_CACHE_TTL_HOURS = 4


def _engine():
    try:
        from sqlalchemy import create_engine
        url = os.getenv("DB_URL")
        if not url:
            return None
        return create_engine(url)
    except Exception as e:
        logger.warning(f"Cannot create DB engine: {e}")
        return None


def _load_from_db(ticker: str) -> Optional[pd.DataFrame]:
    engine = _engine()
    if engine is None:
        return None
    try:
        query = f"""
            SELECT "Date", "Open", "High", "Low", "Close"
            FROM public.prices
            WHERE "Ticker" = '{ticker}'
            ORDER BY "Date"
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        return df
    except Exception as e:
        logger.warning(f"DB load failed for {ticker}: {e}")
        return None


def _load_from_yfinance(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            return None
        hist.reset_index(inplace=True)
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        return hist[["Date", "Open", "High", "Low", "Close"]].copy()
    except Exception as e:
        logger.warning(f"yfinance load failed for {ticker}: {e}")
        return None


def _is_cached(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    age = datetime.now() - _cache[ticker]["loaded_at"]
    return age < timedelta(hours=_CACHE_TTL_HOURS)


def load_ticker(ticker: str) -> Optional[pd.DataFrame]:
    if _is_cached(ticker):
        return _cache[ticker]["df"]
    df = _load_from_db(ticker)
    if df is None:
        logger.info(f"Falling back to yfinance for {ticker}")
        df = _load_from_yfinance(ticker)
    if df is not None:
        _cache[ticker] = {"df": df, "loaded_at": datetime.now()}
    return df


def build_returns_and_prices(tickers: List[str]):
    frames = []
    for t in tickers:
        df = load_ticker(t)
        if df is None:
            logger.warning(f"No data for {t}, skipping")
            continue
        temp = pd.DataFrame({
            "date": pd.to_datetime(df["Date"]),
            "close": df["Close"].values,
            "ticker": t,
        })
        frames.append(temp)

    if not frames:
        raise ValueError("Не удалось загрузить данные ни для одного тикера")

    combined = pd.concat(frames, ignore_index=True)
    combined["year_month"] = combined["date"].dt.to_period("M")

    monthly_close = (
        combined.sort_values("date")
        .groupby(["ticker", "year_month"])["close"]
        .last()
        .unstack(level=0)
    )

    returns_wide = monthly_close.pct_change().dropna()
    available = returns_wide.columns.tolist()
    latest_prices = {t: float(monthly_close[t].iloc[-1]) for t in available}

    return returns_wide, latest_prices, available


def get_available_tickers() -> List[str]:
    engine = _engine()
    if engine is None:
        return ["AAPL", "MSFT", "GOOGL", "JPM", "XOM", "NVDA", "AMZN", "TSLA", "META"]
    try:
        df = pd.read_sql('SELECT DISTINCT "Ticker" FROM public.prices ORDER BY "Ticker"', engine)
        return df["Ticker"].tolist()
    except Exception as e:
        logger.warning(f"Could not fetch tickers from DB: {e}")
        return []


def clear_cache():
    _cache.clear()
