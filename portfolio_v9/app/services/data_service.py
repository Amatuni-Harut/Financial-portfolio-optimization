"""
data_service.py — Сервис загрузки и кэширования финансовых данных.

Изменения в v7:
- Убран Singleton engine (теперь через app/database.py)
- Убрана зависимость от os.getenv (теперь через config.py)
- Добавлен batch-запрос для загрузки нескольких тикеров за раз (устранена N+1 проблема)
- Кэш вынесен в отдельный класс SimpleCache для ясности
- Устранено дублирование списков тикеров (теперь из constants.py)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd

from app.constants import FALLBACK_TICKERS
from app.database import get_engine

logger = logging.getLogger(__name__)


# ============================================================
# КЭШ
# ============================================================

class SimpleCache:
    """
    Простой in-memory кэш с TTL.
    Не потокобезопасен — для production замените на Redis.
    """

    def __init__(self, ttl_hours: int = 4) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(hours=ttl_hours)

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if datetime.now() - entry["loaded_at"] > self._ttl:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = {"value": value, "loaded_at": datetime.now()}

    def clear(self) -> None:
        self._store.clear()
        logger.info("Кэш очищен")


# Глобальный экземпляр кэша. TTL устанавливается при инициализации приложения.
_cache = SimpleCache(ttl_hours=4)


def configure_cache(ttl_hours: int) -> None:
    """Вызывается при старте приложения для установки TTL из конфига."""
    global _cache
    _cache = SimpleCache(ttl_hours=ttl_hours)


def clear_cache() -> None:
    _cache.clear()


# ============================================================
# ЗАГРУЗКА ИЗ БД
# ============================================================

def _load_batch_from_db(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Загружает данные для нескольких тикеров одним SQL-запросом.
    Устраняет N+1 проблему: вместо N запросов — один.

    Возвращает: {ticker: DataFrame} для успешно загруженных тикеров.
    """
    engine = get_engine()
    if engine is None or not tickers:
        return {}

    # Параметризованный запрос — защита от SQL-инъекций
    placeholders = ", ".join(f":t{i}" for i in range(len(tickers)))
    query = f"""
        SELECT "Ticker", "Date", "Open", "High", "Low", "Close"
        FROM public.prices
        WHERE "Ticker" IN ({placeholders})
        ORDER BY "Ticker", "Date"
    """
    params = {f"t{i}": t for i, t in enumerate(tickers)}

    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            df_all = pd.read_sql(text(query), conn, params=params)

        if df_all.empty:
            return {}

        df_all["Date"] = pd.to_datetime(df_all["Date"])
        return {
            ticker: group.drop(columns=["Ticker"]).reset_index(drop=True)
            for ticker, group in df_all.groupby("Ticker")
        }
    except Exception as exc:
        logger.warning(f"Batch-загрузка из БД не удалась: {exc}")
        return {}


def _load_single_from_db(ticker: str) -> Optional[pd.DataFrame]:
    """Загружает данные для одного тикера из БД."""
    result = _load_batch_from_db([ticker])
    return result.get(ticker)


def _load_from_yfinance(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
    """Загружает исторические данные через yfinance (fallback)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            return None
        hist.reset_index(inplace=True)
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        return hist[["Date", "Open", "High", "Low", "Close"]].copy()
    except Exception as exc:
        logger.warning(f"yfinance загрузка не удалась для {ticker}: {exc}")
        return None


def load_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """
    Загружает OHLC данные для одного тикера.
    Приоритет: кэш → БД → yfinance.
    """
    cached = _cache.get(ticker)
    if cached is not None:
        return cached

    df = _load_single_from_db(ticker)
    if df is None:
        logger.info(f"Fallback на yfinance для {ticker}")
        df = _load_from_yfinance(ticker)

    if df is not None:
        _cache.set(ticker, df)
    return df


# ============================================================
# ПОСТРОЕНИЕ МАТРИЦ ДЛЯ ОПТИМИЗАЦИИ
# ============================================================

def build_returns_and_prices(tickers: List[str]):
    """
    Строит матрицу месячных доходностей и словарь последних цен.

    Оптимизация v7: сначала пробуем batch-загрузку из БД для всех тикеров,
    затем yfinance только для тех, кого не нашли в БД.

    Возвращает: (returns_wide, latest_prices, available_tickers)
    """
    # Разбиваем на закэшированные и незакэшированные
    cached_tickers = [t for t in tickers if _cache.get(t) is not None]
    uncached_tickers = [t for t in tickers if _cache.get(t) is None]

    # Batch-загрузка незакэшированных из БД
    if uncached_tickers:
        db_results = _load_batch_from_db(uncached_tickers)
        for ticker, df in db_results.items():
            _cache.set(ticker, df)

    # Для тех, кого нет в БД — yfinance поштучно
    still_missing = [t for t in uncached_tickers if _cache.get(t) is None]
    for ticker in still_missing:
        logger.info(f"Fallback на yfinance для {ticker}")
        df = _load_from_yfinance(ticker)
        if df is not None:
            _cache.set(ticker, df)

    # Собираем данные из кэша
    frames = []
    for ticker in tickers:
        df = _cache.get(ticker)
        if df is None:
            logger.warning(f"Нет данных для {ticker}, пропускаем")
            continue
        frames.append(pd.DataFrame({
            "date":   pd.to_datetime(df["Date"]),
            "close":  df["Close"].values,
            "ticker": ticker,
        }))

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


# ============================================================
# ДЕТАЛИ АКТИВА
# ============================================================

def get_asset_details(ticker: str) -> Dict:
    """
    Возвращает детальные данные по активу для модального окна.
    Бизнес-логика расчётов не изменена.
    """
    cache_key = f"details_{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    df = load_ticker(ticker)
    if df is None:
        raise ValueError(f"Нет данных для {ticker}")

    df = df.sort_values("Date").copy()
    closes = df["Close"].values

    current_price = float(closes[-1])
    max_price = float(closes.max())

    # Изменение за последние ~30 дней
    if len(closes) >= 22:
        prev_price = float(closes[-22])
    elif len(closes) >= 2:
        prev_price = float(closes[-2])
    else:
        prev_price = current_price
    change_pct = (current_price - prev_price) / prev_price * 100 if prev_price else 0.0

    # Месячные метрики
    df["year_month"] = pd.to_datetime(df["Date"]).dt.to_period("M")
    monthly = df.groupby("year_month")["Close"].last()
    monthly_returns = monthly.pct_change().dropna()

    mean_ret = float(monthly_returns.mean()) if len(monthly_returns) > 0 else 0.0
    std_ret  = float(monthly_returns.std())  if len(monthly_returns) > 1 else 0.0
    risk_free_monthly = 0.02 / 12
    sharpe = (mean_ret - risk_free_monthly) / std_ret if std_ret > 0 else 0.0

    # История цен (последние 24 месяца)
    df_monthly = df.copy()
    df_monthly["ym"] = pd.to_datetime(df_monthly["Date"]).dt.to_period("M")
    history_df = (
        df_monthly.sort_values("Date")
        .groupby("ym").last()
        .tail(24)
        .reset_index()
    )
    history = [
        {"date": str(row["ym"]), "price": round(float(row["Close"]), 2)}
        for _, row in history_df.iterrows()
    ]

    change_sign = "+" if change_pct >= 0 else ""
    result = {
        "ticker":      ticker,
        "name":        ticker,
        "price":       f"${current_price:,.2f}",
        "change":      f"{change_sign}{change_pct:.2f}%",
        "max_price":   f"${max_price:,.2f}",
        "mean_return": f"{mean_ret * 100:.2f}%/мес",
        "risk":        f"{std_ret * 100:.2f}%",
        "sharpe":      round(sharpe, 4),
        "history":     history,
    }

    _cache.set(cache_key, result)
    return result


# ============================================================
# СПИСОК ДОСТУПНЫХ ТИКЕРОВ
# ============================================================

def get_available_tickers() -> List[str]:
    """
    Возвращает список тикеров.
    Всегда включает все тикеры из FALLBACK_TICKERS (constants.py),
    плюс дополнительные из БД если они там есть.
    Это исправляет проблему v8: когда в БД только 10 тикеров,
    остальные 25+ из constants не показывались в скринере.
    """
    engine = get_engine()
    db_tickers: List[str] = []

    if engine is not None:
        try:
            df = pd.read_sql(
                'SELECT DISTINCT "Ticker" FROM public.prices ORDER BY "Ticker"',
                engine,
            )
            db_tickers = df["Ticker"].tolist()
        except Exception as exc:
            logger.warning(f"Не удалось получить тикеры из БД: {exc}")

    # Объединяем: все из constants + доп. из БД, порядок сохраняем
    merged = list(FALLBACK_TICKERS)
    for t in db_tickers:
        if t not in merged:
            merged.append(t)

    logger.info(f"Доступно тикеров: {len(merged)} (БД: {len(db_tickers)}, constants: {len(FALLBACK_TICKERS)})")
    return merged


# ============================================================
# BOOTSTRAP — первоначальная загрузка данных
# ============================================================

def bootstrap_data(extra_tickers: Optional[List[str]] = None) -> None:
    """
    Первоначальная загрузка данных в БД при пустой базе.
    Вызывается в фоне при первом входе пользователя.
    """
    from app.constants import BOOTSTRAP_TICKERS
    from connect import process_data

    all_tickers = list(set(BOOTSTRAP_TICKERS + (extra_tickers or [])))
    logger.info(f"Bootstrap: загружаем {len(all_tickers)} тикеров")

    try:
        process_data(all_tickers)
        clear_cache()
        logger.info("Bootstrap завершён успешно")
    except Exception as exc:
        logger.error(f"Bootstrap не удался: {exc}")
