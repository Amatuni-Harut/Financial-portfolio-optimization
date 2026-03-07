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
        # Всегда добавляем priceRaw (USD число) для JS-расчётов бюджета
        try:
            raw_price = float(str(details.get("price", "0")).replace("$", "").replace(",", ""))
            details["priceRaw"] = raw_price
        except Exception:
            details["priceRaw"] = 0.0

        # Конвертируем цену если задана валюта
        cur = (x_settings_currency or "usd").lower()
        if cur != "usd":
            rate = _CURRENCY_RATES.get(cur, 1.0)
            symbol = _CURRENCY_SYMBOLS.get(cur, "$")
            try:
                converted = details["priceRaw"] * rate
                details["price"] = f"{symbol}{converted:,.0f}" if cur == "rub" else f"{symbol}{converted:,.2f}"
            except Exception:
                pass
        return details
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Ошибка деталей {ticker}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
