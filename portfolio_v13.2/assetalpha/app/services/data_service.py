"""
data_service.py — Сервис данных с DB-first логикой.

ПРАВИЛО:
  - При старте: проверяем DB → берём оттуда → только новые качаем через yfinance
  - Кнопка "Обновить": качаем ВСЁ через yfinance → перезаписываем DB
  - Повторный старт при полной DB: yfinance = 0 вызовов, ~3 секунды
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd

from app.constants import FALLBACK_TICKERS, TICKER_NAMES
from app.database import get_engine

logger = logging.getLogger(__name__)


# ============================================================
# КЕШ
# ============================================================

class SimpleCache:
    def __init__(self, ttl_hours: int = 4):
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
        logger.info("Кеш очищен")

    def size(self) -> int:
        return len(self._store)


_cache = SimpleCache(ttl_hours=4)


def configure_cache(ttl_hours: int) -> None:
    global _cache
    _cache = SimpleCache(ttl_hours=ttl_hours)


def clear_cache() -> None:
    _cache.clear()


# ============================================================
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦЫ
# ============================================================

def _init_db_table() -> bool:
    """
    Создаёт таблицу prices если её нет.
    Добавляет PRIMARY KEY если отсутствует.
    Возвращает True если всё ок.
    """
    engine = get_engine()
    if engine is None:
        return False

    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # 1. Создаём таблицу если нет
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.prices (
                    "Ticker" TEXT        NOT NULL,
                    "Date"   TIMESTAMP   NOT NULL,
                    "Open"   DOUBLE PRECISION,
                    "High"   DOUBLE PRECISION,
                    "Low"    DOUBLE PRECISION,
                    "Close"  DOUBLE PRECISION
                )
            """))
            conn.commit()

            # 2. Проверяем PRIMARY KEY
            r = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE table_schema    = 'public'
                  AND table_name      = 'prices'
                  AND constraint_type = 'PRIMARY KEY'
            """))
            has_pk = (r.scalar() or 0) > 0

            if not has_pk:
                logger.info("prices: нет PRIMARY KEY — чистим дубликаты и добавляем...")
                conn.execute(text("""
                    DELETE FROM public.prices a
                    USING  public.prices b
                    WHERE  a.ctid < b.ctid
                      AND  a."Ticker" = b."Ticker"
                      AND  a."Date"   = b."Date"
                """))
                conn.execute(text("""
                    ALTER TABLE public.prices
                    ADD CONSTRAINT prices_pkey PRIMARY KEY ("Ticker", "Date")
                """))
                conn.commit()
                logger.info("prices: PRIMARY KEY добавлен")

            # 3. Индексы
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS idx_prices_ticker ON public.prices ("Ticker")'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS idx_prices_date ON public.prices ("Date")'
            ))
            conn.commit()

        return True
    except Exception as exc:
        logger.error(f"_init_db_table: {exc}")
        return False


# ============================================================
# ПРОВЕРКА DB
# ============================================================

def _get_tickers_in_db() -> set:
    """Какие тикеры уже есть в DB."""
    engine = get_engine()
    if engine is None:
        return set()
    try:
        df = pd.read_sql('SELECT DISTINCT "Ticker" FROM public.prices', engine)
        tickers = set(df["Ticker"].tolist())
        logger.info(f"В DB найдено тикеров: {len(tickers)}")
        return tickers
    except Exception as exc:
        logger.warning(f"_get_tickers_in_db: {exc}")
        return set()


# ============================================================
# ЗАГРУЗКА ИЗ DB
# ============================================================

def _load_batch_from_db(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """Загружает несколько тикеров одним SQL запросом."""
    engine = get_engine()
    if engine is None or not tickers:
        return {}

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
        result = {}
        for ticker, group in df_all.groupby("Ticker"):
            result[ticker] = group.drop(columns=["Ticker"]).reset_index(drop=True)
        return result
    except Exception as exc:
        logger.warning(f"_load_batch_from_db: {exc}")
        return {}


def _load_single_from_db(ticker: str) -> Optional[pd.DataFrame]:
    return _load_batch_from_db([ticker]).get(ticker)


# ============================================================
# СОХРАНЕНИЕ В DB — без временных таблиц
# ============================================================

def _save_to_db(all_data: Dict[str, pd.DataFrame]) -> int:
    """
    Сохраняет данные напрямую через executemany + ON CONFLICT.
    Не использует prices_tmp — нет риска потери данных.
    """
    engine = get_engine()
    if engine is None or not all_data:
        return 0

    # Гарантируем таблицу и PRIMARY KEY
    if not _init_db_table():
        logger.error("_save_to_db: не удалось инициализировать таблицу")
        return 0

    from sqlalchemy import text

    saved = 0
    for ticker, df in all_data.items():
        try:
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "ticker": ticker,
                    "date":   row["Date"].isoformat() if hasattr(row["Date"], "isoformat") else str(row["Date"]),
                    "open":   float(row["Open"])  if pd.notna(row["Open"])  else None,
                    "high":   float(row["High"])  if pd.notna(row["High"])  else None,
                    "low":    float(row["Low"])   if pd.notna(row["Low"])   else None,
                    "close":  float(row["Close"]) if pd.notna(row["Close"]) else None,
                })

            if not rows:
                continue

            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO public.prices
                        ("Ticker","Date","Open","High","Low","Close")
                    VALUES
                        (:ticker,:date,:open,:high,:low,:close)
                    ON CONFLICT ("Ticker","Date") DO UPDATE
                        SET "Open"  = EXCLUDED."Open",
                            "High"  = EXCLUDED."High",
                            "Low"   = EXCLUDED."Low",
                            "Close" = EXCLUDED."Close"
                """), rows)
                conn.commit()

            saved += 1
            logger.debug(f"DB сохранён: {ticker} ({len(rows)} строк)")

        except Exception as exc:
            logger.error(f"_save_to_db [{ticker}]: {exc}")

    logger.info(f"_save_to_db: сохранено {saved}/{len(all_data)} тикеров")
    return saved


# ============================================================
# ЗАГРУЗКА ЧЕРЕЗ yfinance
# ============================================================

def _fetch_yfinance(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            return None
        hist.reset_index(inplace=True)
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        return hist[["Date", "Open", "High", "Low", "Close"]].copy()
    except Exception as exc:
        logger.warning(f"yfinance [{ticker}]: {exc}")
        return None


# ============================================================
# СТАРТ ПРИЛОЖЕНИЯ — DB-FIRST
# ============================================================

async def startup_preload(tickers: Optional[List[str]] = None) -> None:
    """
    Вызывается при старте uvicorn.

    Алгоритм:
      1. Инициализируем таблицу (CREATE IF NOT EXISTS + PRIMARY KEY)
      2. Смотрим какие тикеры УЖЕ в DB
      3. Есть в DB → грузим в кеш НАПРЯМУЮ (yfinance не трогаем!)
      4. Нет в DB → качаем yfinance → кешируем → сохраняем в DB

    При полной DB (все 100 тикеров): yfinance = 0 вызовов, старт ~3 сек.
    """
    all_tickers = tickers or FALLBACK_TICKERS
    total = len(all_tickers)

    logger.info(f"[startup] Начало: {total} тикеров")
    t0 = datetime.now()
    loop = asyncio.get_event_loop()

    # Шаг 1: инициализируем таблицу
    await loop.run_in_executor(None, _init_db_table)

    # Шаг 2: что уже есть в DB?
    db_existing = await loop.run_in_executor(None, _get_tickers_in_db)

    in_db      = [t for t in all_tickers if t in db_existing]
    missing    = [t for t in all_tickers if t not in db_existing]

    logger.info(
        f"[startup] В DB: {len(in_db)} — из DB. "
        f"Отсутствует: {len(missing)} — через yfinance."
    )

    count_db = 0
    count_yf = 0
    count_err = 0

    # Шаг 3: грузим из DB в кеш
    if in_db:
        db_data = await loop.run_in_executor(None, _load_batch_from_db, in_db)
        for ticker, df in db_data.items():
            _cache.set(ticker, df)
            count_db += 1
        logger.info(f"[startup] Из DB в кеш: {count_db} тикеров")

    # Шаг 4: качаем недостающие через yfinance
    if missing:
        new_data: Dict[str, pd.DataFrame] = {}

        async def fetch_one(ticker: str):
            nonlocal count_yf, count_err
            df = await loop.run_in_executor(None, _fetch_yfinance, ticker)
            if df is not None and not df.empty:
                new_data[ticker] = df
                _cache.set(ticker, df)
                count_yf += 1
                done = count_db + count_yf
                logger.info(f"[{done}/{total}] yfinance: {ticker}")
            else:
                count_err += 1
                logger.warning(f"[startup] Не удалось загрузить: {ticker}")

        # По 5 параллельно
        for i in range(0, len(missing), 5):
            await asyncio.gather(*[fetch_one(t) for t in missing[i:i+5]])

        # Сохраняем новые в DB
        if new_data:
            logger.info(f"[startup] Сохраняем {len(new_data)} тикеров в DB...")
            saved = await loop.run_in_executor(None, _save_to_db, new_data)
            logger.info(f"[startup] Сохранено в DB: {saved} тикеров")

    elapsed = round((datetime.now() - t0).total_seconds())
    logger.info(
        f"[startup] Готово за {elapsed}с: "
        f"DB={count_db}, yfinance={count_yf}, ошибок={count_err}. "
        f"Кеш: {_cache.size()} тикеров."
    )


# ============================================================
# ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ (кнопка "Обновить данные")
# ============================================================

async def force_refresh_from_yfinance(tickers: Optional[List[str]] = None) -> dict:
    """
    Скачивает ВСЕ тикеры через yfinance и перезаписывает DB.
    Вызывается только по нажатию кнопки.
    """
    all_tickers = tickers or FALLBACK_TICKERS
    logger.info(f"[refresh] Принудительное обновление: {len(all_tickers)} тикеров")

    loop = asyncio.get_event_loop()
    new_data: Dict[str, pd.DataFrame] = {}
    failed: List[str] = []

    async def fetch_one(ticker: str):
        df = await loop.run_in_executor(None, _fetch_yfinance, ticker)
        if df is not None and not df.empty:
            new_data[ticker] = df
            _cache.set(ticker, df)
        else:
            failed.append(ticker)

    for i in range(0, len(all_tickers), 5):
        await asyncio.gather(*[fetch_one(t) for t in all_tickers[i:i+5]])

    if new_data:
        saved = await loop.run_in_executor(None, _save_to_db, new_data)
        logger.info(f"[refresh] Сохранено в DB: {saved} тикеров")

    return {
        "updated": len(new_data),
        "failed":  len(failed),
        "failed_tickers": failed,
    }


# ============================================================
# ПУБЛИЧНЫЕ ФУНКЦИИ
# ============================================================

def load_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """Кеш → DB → yfinance (последний вариант)."""
    cached = _cache.get(ticker)
    if cached is not None:
        return cached

    df = _load_single_from_db(ticker)
    if df is None:
        logger.info(f"Fallback yfinance: {ticker}")
        df = _fetch_yfinance(ticker)

    if df is not None:
        _cache.set(ticker, df)
    return df


def build_returns_and_prices(tickers: List[str]):
    uncached = [t for t in tickers if _cache.get(t) is None]
    if uncached:
        db_results = _load_batch_from_db(uncached)
        for ticker, df in db_results.items():
            _cache.set(ticker, df)

    still_missing = [t for t in tickers if _cache.get(t) is None]
    for ticker in still_missing:
        df = _fetch_yfinance(ticker)
        if df is not None:
            _cache.set(ticker, df)

    frames = []
    for ticker in tickers:
        df = _cache.get(ticker)
        if df is None:
            continue
        frames.append(pd.DataFrame({
            "date":   pd.to_datetime(df["Date"]),
            "close":  df["Close"].values,
            "ticker": ticker,
        }))

    if not frames:
        raise ValueError("Нет данных ни для одного тикера")

    combined = pd.concat(frames, ignore_index=True)
    combined["year_month"] = combined["date"].dt.to_period("M")
    monthly_close = (
        combined.sort_values("date")
        .groupby(["ticker", "year_month"])["close"]
        .last()
        .unstack(level=0)
    )
    returns_wide  = monthly_close.pct_change().dropna()
    available     = returns_wide.columns.tolist()
    latest_prices = {t: float(monthly_close[t].iloc[-1]) for t in available}
    return returns_wide, latest_prices, available


def get_asset_details(ticker: str) -> dict:
    cache_key = f"details_{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    df = load_ticker(ticker)
    if df is None:
        raise ValueError(f"Нет данных для {ticker}")

    df     = df.sort_values("Date").copy()
    closes = df["Close"].values

    current_price = float(closes[-1])
    max_price     = float(closes.max())
    prev_price    = float(closes[-22]) if len(closes) >= 22 else (float(closes[-2]) if len(closes) >= 2 else current_price)
    change_pct    = (current_price - prev_price) / prev_price * 100 if prev_price else 0.0

    df["year_month"] = pd.to_datetime(df["Date"]).dt.to_period("M")
    monthly          = df.groupby("year_month")["Close"].last()
    monthly_returns  = monthly.pct_change().dropna()
    mean_ret = float(monthly_returns.mean()) if len(monthly_returns) > 0 else 0.0
    std_ret  = float(monthly_returns.std())  if len(monthly_returns) > 1 else 0.0
    sharpe   = (mean_ret - 0.02/12) / std_ret if std_ret > 0 else 0.0

    df_m = df.copy()
    df_m["ym"] = pd.to_datetime(df_m["Date"]).dt.to_period("M")
    history_df = df_m.sort_values("Date").groupby("ym").last().tail(24).reset_index()
    history = [
        {"date": str(row["ym"]), "price": round(float(row["Close"]), 2)}
        for _, row in history_df.iterrows()
    ]

    result = {
        "ticker":      ticker,
        "name":        TICKER_NAMES.get(ticker, (ticker, ""))[0],
        "price":       f"${current_price:,.2f}",
        "priceRaw":    round(current_price, 4),
        "change":      f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%",
        "max_price":   f"${max_price:,.2f}",
        "mean_return": f"{mean_ret * 100:.2f}%/мес",
        "risk":        f"{std_ret * 100:.2f}%",
        "sharpe":      round(sharpe, 4),
        "history":     history,
    }
    _cache.set(cache_key, result)
    return result


def get_available_tickers() -> List[str]:
    engine = get_engine()
    db_tickers: List[str] = []
    if engine is not None:
        try:
            df = pd.read_sql(
                'SELECT DISTINCT "Ticker" FROM public.prices ORDER BY "Ticker"',
                engine
            )
            db_tickers = df["Ticker"].tolist()
        except Exception as exc:
            logger.warning(f"get_available_tickers: {exc}")

    merged = list(FALLBACK_TICKERS)
    for t in db_tickers:
        if t not in merged:
            merged.append(t)
    return merged


# Обратная совместимость
def bootstrap_data(extra_tickers=None):
    logger.warning("bootstrap_data() устарела")
