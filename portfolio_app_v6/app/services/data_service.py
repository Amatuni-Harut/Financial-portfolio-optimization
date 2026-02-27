"""
data_service.py — Сервис загрузки и кэширования финансовых данных.
- Singleton engine
- Параметризованные SQL-запросы (без SQL-инъекций)
- Кэш с TTL
- get_asset_details для модального окна
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ================================================================
# SINGLETON ENGINE
# ================================================================

_engine_instance = None

def _engine():
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance
    try:
        from sqlalchemy import create_engine
        url = os.getenv("DB_URL")
        if not url:
            logger.warning("DB_URL не задан в .env")
            return None
        _engine_instance = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True  # проверять соединение перед использованием
        )
        logger.info("DB engine создан")
        return _engine_instance
    except Exception as e:
        logger.warning(f"Не удалось создать DB engine: {e}")
        return None


# ================================================================
# КЭШ
# ================================================================

_cache: Dict[str, Dict] = {}
_CACHE_TTL_HOURS = 4


def _is_cached(key: str) -> bool:
    if key not in _cache:
        return False
    age = datetime.now() - _cache[key]["loaded_at"]
    return age < timedelta(hours=_CACHE_TTL_HOURS)


def clear_cache():
    _cache.clear()
    logger.info("Кэш очищен")


# ================================================================
# ЗАГРУЗКА ДАННЫХ
# ================================================================

def _load_from_db(ticker: str) -> Optional[pd.DataFrame]:
    engine = _engine()
    if engine is None:
        return None
    try:
        # Параметризованный запрос — защита от SQL-инъекций
        query = "SELECT \"Date\", \"Open\", \"High\", \"Low\", \"Close\" FROM public.prices WHERE \"Ticker\" = %(ticker)s ORDER BY \"Date\""
        df = pd.read_sql(query, engine, params={"ticker": ticker})
        if df.empty:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        return df
    except Exception as e:
        logger.warning(f"DB загрузка не удалась для {ticker}: {e}")
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
        logger.warning(f"yfinance загрузка не удалась для {ticker}: {e}")
        return None


def load_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """Загружает OHLC данные. Сначала из БД, fallback на yfinance. Кэширует результат."""
    if _is_cached(ticker):
        return _cache[ticker]["df"]

    df = _load_from_db(ticker)
    if df is None:
        logger.info(f"Fallback на yfinance для {ticker}")
        df = _load_from_yfinance(ticker)

    if df is not None:
        _cache[ticker] = {"df": df, "loaded_at": datetime.now()}
    return df


# ================================================================
# ПОСТРОЕНИЕ МАТРИЦ ДЛЯ ОПТИМИЗАЦИИ
# ================================================================

def build_returns_and_prices(tickers: List[str]):
    """
    Строит матрицу месячных доходностей и словарь последних цен.
    Возвращает: (returns_wide, latest_prices, available_tickers)
    """
    frames = []
    for t in tickers:
        df = load_ticker(t)
        if df is None:
            logger.warning(f"Нет данных для {t}, пропускаем")
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


# ================================================================
# ДЕТАЛИ АКТИВА (для модального окна скринера)
# ================================================================

def get_asset_details(ticker: str) -> Dict:
    """
    Возвращает детальные данные по активу для модального окна:
    текущая цена, максимальная цена, изменение за последний период,
    доходность, риск, Sharpe, история цен.
    """
    cache_key = f"details_{ticker}"
    if _is_cached(cache_key):
        return _cache[cache_key]["df"]

    df = load_ticker(ticker)
    if df is None:
        raise ValueError(f"Нет данных для {ticker}")

    df = df.sort_values("Date").copy()
    closes = df["Close"].values
    dates = df["Date"]

    # Текущая и максимальная цена
    current_price = float(closes[-1])
    max_price = float(closes.max())

    # Изменение за последние 30 дней (примерно)
    if len(closes) >= 22:
        prev_price = float(closes[-22])
        change_pct = (current_price - prev_price) / prev_price * 100
    elif len(closes) >= 2:
        prev_price = float(closes[-2])
        change_pct = (current_price - prev_price) / prev_price * 100
    else:
        change_pct = 0.0

    # Месячные доходности для метрик
    df["year_month"] = pd.to_datetime(df["Date"]).dt.to_period("M")
    monthly = df.groupby("year_month")["Close"].last()
    monthly_returns = monthly.pct_change().dropna()

    mean_ret = float(monthly_returns.mean()) if len(monthly_returns) > 0 else 0.0
    std_ret = float(monthly_returns.std()) if len(monthly_returns) > 1 else 0.0
    risk_free_monthly = 0.02 / 12
    sharpe = (mean_ret - risk_free_monthly) / std_ret if std_ret > 0 else 0.0

    # История цен для графика (последние 12 месяцев, последний день каждого месяца)
    df_monthly = df.copy()
    df_monthly["ym"] = pd.to_datetime(df_monthly["Date"]).dt.to_period("M")
    history_df = (
        df_monthly.sort_values("Date")
        .groupby("ym")
        .last()
        .tail(24)
        .reset_index()
    )

    history = [
        {
            "date": str(row["ym"]),
            "price": round(float(row["Close"]), 2)
        }
        for _, row in history_df.iterrows()
    ]

    change_sign = "+" if change_pct >= 0 else ""
    result = {
        "ticker": ticker,
        "name": ticker,
        "price": f"${current_price:,.2f}",
        "change": f"{change_sign}{change_pct:.2f}%",
        "max_price": f"${max_price:,.2f}",
        "mean_return": f"{mean_ret * 100:.2f}%/мес",
        "risk": f"{std_ret * 100:.2f}%",
        "sharpe": round(sharpe, 4),
        "history": history,
    }

    _cache[cache_key] = {"df": result, "loaded_at": datetime.now()}
    return result


# ================================================================
# СПИСОК ДОСТУПНЫХ ТИКЕРОВ
# ================================================================

FALLBACK_TICKERS = [
    # Technology
    "AAPL", "MSFT", "GOOGL", "NVDA", "META", "AVGO", "ORCL", "CRM", "ADBE", "INTC",
    # Consumer
    "AMZN", "TSLA", "HD", "MCD", "PG", "KO", "WMT",
    # Financial
    "JPM", "V", "MA", "BRK-B", "BAC", "GS",
    # Healthcare
    "JNJ", "UNH", "LLY", "AMGN", "PFE",
    # Energy & Industrials
    "XOM", "CVX", "HON", "CAT", "BA",
]


def get_available_tickers() -> List[str]:
    engine = _engine()
    if engine is None:
        return FALLBACK_TICKERS
    try:
        df = pd.read_sql(
            'SELECT DISTINCT "Ticker" FROM public.prices ORDER BY "Ticker"',
            engine
        )
        tickers = df["Ticker"].tolist()
        return tickers if tickers else FALLBACK_TICKERS
    except Exception as e:
        logger.warning(f"Не удалось получить тикеры из БД: {e}")
        return FALLBACK_TICKERS


# ================================================================
# BOOTSTRAP — первоначальная загрузка данных
# ================================================================

def bootstrap_data(extra_tickers: Optional[List[str]] = None):
    """
    Первоначальная загрузка данных в БД.
    Вызывается в фоне при первом входе пользователя.
    """
    from app.connect import process_data

    base_tickers = [
        # Tech
        "AAPL", "MSFT", "GOOGL", "NVDA", "META", "AVGO", "ORCL", "CRM", "ADBE", "INTC",
        # Consumer
        "AMZN", "TSLA", "HD", "MCD", "PG", "KO", "WMT",
        # Financial
        "JPM", "V", "MA", "BRK-B", "BAC", "GS",
        # Healthcare
        "JNJ", "UNH", "LLY", "AMGN", "PFE",
        # Energy & Industrials
        "XOM", "CVX", "HON", "CAT", "BA",
    ]

    all_tickers = list(set(base_tickers + (extra_tickers or [])))
    logger.info(f"Bootstrap: загружаем {len(all_tickers)} тикеров")

    try:
        process_data(all_tickers)
        clear_cache()  # сбрасываем кэш чтобы подтянуть свежие данные из БД
        logger.info("Bootstrap завершён успешно")
    except Exception as e:
        logger.error(f"Bootstrap не удался: {e}")
