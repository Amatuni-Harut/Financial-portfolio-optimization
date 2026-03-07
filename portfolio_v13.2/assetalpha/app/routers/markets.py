"""
routers/markets.py — Эндпоинты рыночных данных.

Исправления v13.1:
- _CURRENCY_RATES защищён asyncio.Lock (была race condition при concurrent requests)
- Добавлен TTL-кэш для курсов валют (не запрашиваем API чаще чем раз в час)
- Логика обновления курсов вынесена в _CurrencyCache класс
"""
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from app.constants import TICKER_NAMES
from app.services import data_service, optimizer
from app.services.data_service import force_refresh_from_yfinance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Market"])

# Символы валют (read-only — лок не нужен)
_CURRENCY_SYMBOLS: dict[str, str] = {
    "usd": "$",
    "eur": "€",
    "amd": "֏",
    "rub": "₽",
}


class _CurrencyCache:
    """
    Потокобезопасный кэш курсов валют с TTL.
    FIX: asyncio.Lock устраняет race condition при одновременных запросах.
    """
    TTL_SECONDS = 3600  # обновляем не чаще раза в час

    def __init__(self):
        self._rates: dict[str, float] = {
            "usd": 1.0,
            "eur": 0.92,
            "amd": 387.0,
            "rub": 90.0,
        }
        self._last_updated: float = 0.0
        self._lock = asyncio.Lock()

    async def get_rates(self) -> dict[str, float]:
        """Возвращает актуальные курсы, при необходимости обновляет через API."""
        now = time.monotonic()
        if now - self._last_updated < self.TTL_SECONDS:
            return dict(self._rates)  # возвращаем копию

        async with self._lock:
            # Double-check после получения лока
            if time.monotonic() - self._last_updated < self.TTL_SECONDS:
                return dict(self._rates)

            await self._fetch_rates()
            self._last_updated = time.monotonic()
            return dict(self._rates)

    async def _fetch_rates(self) -> None:
        """Загружает актуальные курсы с open.er-api.com (бесплатно, без ключа)."""
        try:
            import urllib.request
            import json as _json

            loop = asyncio.get_running_loop()
            url = "https://open.er-api.com/v6/latest/USD"

            def _do_request():
                with urllib.request.urlopen(url, timeout=5) as r:
                    return _json.loads(r.read())

            data = await loop.run_in_executor(None, _do_request)

            if data.get("result") == "success":
                rates = data["rates"]
                self._rates["eur"] = round(rates.get("EUR", 0.92), 6)
                self._rates["amd"] = round(rates.get("AMD", 387.0), 2)
                self._rates["rub"] = round(rates.get("RUB", 90.0), 2)
                logger.info(
                    f"Курсы обновлены: EUR={self._rates['eur']}, "
                    f"AMD={self._rates['amd']}, RUB={self._rates['rub']}"
                )
        except Exception as exc:
            logger.warning(f"Курсы не обновлены: {exc} — используются кешированные")

    def get_rates_sync(self) -> dict[str, float]:
        """Синхронный доступ для совместимости с не-async кодом."""
        return dict(self._rates)


_currency_cache = _CurrencyCache()

# Публичный доступ для других роутеров (markets.py экспортирует их)
_CURRENCY_RATES = _currency_cache.get_rates_sync()


def _convert_price(usd_price: float, currency: str) -> str:
    cur      = (currency or "usd").lower()
    rates    = _currency_cache.get_rates_sync()
    rate     = rates.get(cur, 1.0)
    symbol   = _CURRENCY_SYMBOLS.get(cur, "$")
    converted = usd_price * rate
    return f"{symbol}{converted:,.0f}" if cur == "rub" else f"{symbol}{converted:,.2f}"


@router.get("/markets/all")
async def markets_all(
    x_settings_currency: Optional[str] = Header(default="usd"),
):
    """Возвращает сводную таблицу по всем доступным инструментам."""
    try:
        tickers = data_service.get_available_tickers()
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
        stats = optimizer.analyze_stocks(returns_wide, latest_prices)

        data = [
            {
                "symbol":   s["ticker"],
                "name":     TICKER_NAMES.get(s["ticker"], (s["ticker"], ""))[0],
                "sector":   TICKER_NAMES.get(s["ticker"], ("", ""))[1],
                "price":    _convert_price(s["price"], x_settings_currency),
                "priceRaw": s["price"],
                "change":   round(s["mean_ret_pct"], 2),
                "marketCap": "—",
                "sharpe":   s["sharpe"],
                "currency": (x_settings_currency or "usd").lower(),
            }
            for s in stats
        ]
        return {"data": data, "count": len(data)}
    except Exception as exc:
        logger.error(f"Ошибка markets/all: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/currency/rates")
async def currency_rates():
    """Возвращает актуальные курсы валют относительно USD (с TTL-кэшем)."""
    rates = await _currency_cache.get_rates()
    return {
        "base":    "USD",
        "rates":   rates,
        "symbols": _CURRENCY_SYMBOLS,
    }


@router.get("/market/refresh")
async def market_refresh():
    """
    Принудительное обновление данных через yfinance + сохранение в DB.
    Вызывается кнопкой 'Обновить данные' во фронтенде.
    """
    try:
        result = await force_refresh_from_yfinance()
        return {
            "status":  "ok",
            "message": f"Обновлено {result['updated']} тикеров из yfinance",
            "updated": result["updated"],
            "failed":  result["failed"],
        }
    except Exception as exc:
        logger.error(f"Ошибка обновления данных: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
