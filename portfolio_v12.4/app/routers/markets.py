"""
routers/markets.py — Эндпоинты рыночных данных.
"""
import logging

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.constants import TICKER_NAMES
from app.services import data_service, optimizer
from app.services.data_service import force_refresh_from_yfinance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Market"])

# Символы валют
_CURRENCY_SYMBOLS: dict[str, str] = {
    "usd": "$",
    "eur": "€",
    "amd": "֏",
    "rub": "₽",
}

# Курсы (обновляются при запросе /api/currency/rates)
_CURRENCY_RATES: dict[str, float] = {
    "usd": 1.0,
    "eur": 0.92,
    "amd": 387.0,
    "rub": 90.0,
}

def _refresh_currency_rates() -> dict:
    """Получает актуальные курсы с open.er-api.com (бесплатно, без ключа, каждые 24ч)."""
    try:
        import urllib.request, json as _json
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = _json.loads(r.read())
        if data.get("result") == "success":
            rates = data["rates"]
            _CURRENCY_RATES["eur"] = round(rates.get("EUR", 0.92), 6)
            _CURRENCY_RATES["amd"] = round(rates.get("AMD", 387.0), 2)
            _CURRENCY_RATES["rub"] = round(rates.get("RUB", 90.0), 2)
            logger.info(f"Курсы: EUR={_CURRENCY_RATES['eur']}, AMD={_CURRENCY_RATES['amd']}, RUB={_CURRENCY_RATES['rub']}")
    except Exception as exc:
        logger.warning(f"Курсы не обновлены: {exc} — используются кешированные")
    return _CURRENCY_RATES


def _convert_price(usd_price: float, currency: str) -> str:
    cur = (currency or "usd").lower()
    rate = _CURRENCY_RATES.get(cur, 1.0)
    symbol = _CURRENCY_SYMBOLS.get(cur, "$")
    converted = usd_price * rate
    if cur == "rub":
        return f"{symbol}{converted:,.0f}"
    return f"{symbol}{converted:,.2f}"


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
                "symbol":    s["ticker"],
                "name":      TICKER_NAMES.get(s["ticker"], (s["ticker"], ""))[0],
                "sector":    TICKER_NAMES.get(s["ticker"], ("", ""))[1],
                "price":     _convert_price(s["price"], x_settings_currency),
                "priceRaw":  s["price"],
                "change":    round(s["mean_ret_pct"], 2),
                "marketCap": "—",
                "sharpe":    s["sharpe"],
                "currency":  (x_settings_currency or "usd").lower(),
            }
            for s in stats
        ]
        return {"data": data, "count": len(data)}
    except Exception as exc:
        logger.error(f"Ошибка markets/all: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/currency/rates")
async def currency_rates():
    """Возвращает актуальные курсы валют относительно USD."""
    rates = _refresh_currency_rates()
    return {
        "base": "USD",
        "rates": rates,
        "symbols": _CURRENCY_SYMBOLS,
    }


@router.get("/market/refresh")
async def market_refresh():
    """
    Принудительное обновление данных через yfinance + сохранение в DB.
    Вызывается кнопкой 'Обновить данные' во фронтенде.
    """
    try:
        result = await data_service.force_refresh_from_yfinance()
        return {
            "status":  "ok",
            "message": f"Обновлено {result['updated']} тикеров из yfinance",
            "updated": result["updated"],
            "failed":  result["failed"],
        }
    except Exception as exc:
        logger.error(f"Ошибка обновления данных: {exc}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(exc))
