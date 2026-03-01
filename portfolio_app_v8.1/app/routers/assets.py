"""
routers/assets.py — Эндпоинты для поиска и деталей активов.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from app.constants import TICKER_NAMES
from app.services import data_service

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
async def get_asset_details(ticker: str):
    """Возвращает детальные данные актива для модального окна."""
    ticker = ticker.upper()
    try:
        return data_service.get_asset_details(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Ошибка деталей {ticker}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
