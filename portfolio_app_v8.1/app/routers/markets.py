"""
routers/markets.py — Эндпоинты рыночных данных.
"""
import logging

from fastapi import APIRouter, HTTPException

from app.constants import TICKER_NAMES
from app.services import data_service, optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Market"])


@router.get("/markets/all")
async def markets_all():
    """Возвращает сводную таблицу по всем доступным инструментам."""
    try:
        tickers = data_service.get_available_tickers()
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
        stats = optimizer.analyze_stocks(returns_wide, latest_prices)

        data = [
            {
                "symbol":    s["ticker"],
                "name":      TICKER_NAMES.get(s["ticker"], (s["ticker"], ""))[0],
                "price":     f"${s['price']:,.2f}",
                "change":    round(s["mean_ret_pct"], 2),
                "marketCap": "—",
                "sharpe":    s["sharpe"],
            }
            for s in stats
        ]
        return {"data": data, "count": len(data)}
    except Exception as exc:
        logger.error(f"Ошибка markets/all: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/market/refresh")
async def market_refresh():
    """Очищает кэш рыночных данных."""
    data_service.clear_cache()
    return {"status": "ok", "message": "Кэш очищен"}
