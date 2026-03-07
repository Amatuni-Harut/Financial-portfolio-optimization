"""
routers/assets.py — Эндпоинты для поиска и деталей активов.
"""
import logging

from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional

from app.constants import TICKER_NAMES
from app.services import data_service
from app.routers.markets import _convert_price, _CURRENCY_RATES, _CURRENCY_SYMBOLS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Data"])


@router.get("/stocks/search")
async def search_stocks(query: str = Query(..., min_length=1)):
    """Ищет тикеры по подстроке."""
    try:
        all_tickers = data_service.get_available_tickers()
        q = query.upper()
        matched = [t for t in all_tickers if q in t.upper()][:10]
        return [
            {
                "ticker": t,
                "name":   TICKER_NAMES.get(t, (t, ""))[0],
                "sector": TICKER_NAMES.get(t, ("", ""))[1],
            }
            for t in matched
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/assets/{ticker}/details")
async def get_asset_details(
    ticker: str,
    x_settings_currency: Optional[str] = Header(default="usd"),
):
    """Возвращает детальные данные актива для модального окна."""
    ticker = ticker.upper()
    try:
        details = data_service.get_asset_details(ticker)
        # priceRaw уже есть из data_service (всегда USD)
        if "priceRaw" not in details or not details["priceRaw"]:
            try:
                details["priceRaw"] = float(str(details.get("price","0")).replace("$","").replace(",",""))
            except Exception:
                details["priceRaw"] = 0.0

        # Конвертируем все денежные поля согласно выбранной валюте
        cur = (x_settings_currency or "usd").lower()
        rate   = _CURRENCY_RATES.get(cur, 1.0)
        symbol = _CURRENCY_SYMBOLS.get(cur, "$")

        def fmt_money(usd_val):
            v = usd_val * rate
            return f"{symbol}{v:,.0f}" if cur == "rub" else f"{symbol}{v:,.2f}"

        def parse_usd(s):
            """Извлекает число из строки вида '$285.92'"""
            try:
                return float(str(s).replace("$","").replace(",","").strip())
            except Exception:
                return 0.0

        # Конвертируем price
        details["price"] = fmt_money(details["priceRaw"])

        # Конвертируем max_price
        if details.get("max_price"):
            details["max_price"] = fmt_money(parse_usd(details["max_price"]))

        return details
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Ошибка деталей {ticker}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
