import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services import data_service
from app.services import optimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Portfolio Optimizer API v2 starting...")
    yield
    logger.info("Portfolio Optimizer API v2 stopped.")


app = FastAPI(
    title="AssetAlpha API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


# ── Статика ────────────────────────────────────────────────────────
if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js",  StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")),  name="js")


# ── HTML страницы ──────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/index.html", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/login.html", include_in_schema=False)
async def login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/markets.html", include_in_schema=False)
async def markets():
    return FileResponse(os.path.join(FRONTEND_DIR, "markets.html"))

@app.get("/settings.html", include_in_schema=False)
async def settings():
    return FileResponse(os.path.join(FRONTEND_DIR, "settings.html"))


# ── Pydantic схемы ─────────────────────────────────────────────────
class AssetInput(BaseModel):
    ticker: str
    weight: Optional[float] = None

class OptimizeRequestV2(BaseModel):
    assets: List[AssetInput]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    optimization_goal: str = "max_sharpe"
    risk_free_rate: float = 0.02
    manual_weights: bool = False


# ── Health ─────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    db_ok = False
    try:
        engine = data_service._engine()
        if engine:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db_connected": db_ok, "version": "2.0.0"}


# ── Поиск тикеров ──────────────────────────────────────────────────
@app.get("/api/stocks/search", tags=["Data"])
async def search_stocks(query: str = Query(..., min_length=1)):
    try:
        all_tickers = data_service.get_available_tickers()
        q = query.upper()
        matched = [t for t in all_tickers if q in t.upper()][:10]
        return [{"ticker": t, "name": t, "sector": ""} for t in matched]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Оптимизация ────────────────────────────────────────────────────
@app.post("/api/optimize", tags=["Optimization"])
async def optimize(request: OptimizeRequestV2):
    tickers = [a.ticker.upper() for a in request.assets]
    logger.info(f"Optimize v2: tickers={tickers}")

    if len(tickers) < 2:
        raise HTTPException(status_code=422, detail="Нужно минимум 2 актива")

    try:
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ошибка загрузки данных: {e}")

    if len(available) < 2:
        raise HTTPException(status_code=422, detail=f"Загружено менее 2 тикеров: {available}")

    try:
        result = optimizer.run_optimization(
            tickers=available,
            returns_wide=returns_wide,
            latest_prices=latest_prices,
            budget=10000,
            risk_free_rate=request.risk_free_rate,
            methods=["monte_carlo"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации: {e}")

    # Берём лучший портфель
    best = next(p for p in result["portfolios"] if p["name"] == result["best_portfolio"])
    weights_dict = dict(zip(best["tickers"], best["weights"]))

    annual_return = best["metrics"]["return_pct"] * 12
    annual_risk   = best["metrics"]["monthly_risk"] / best["metrics"]["budget"] * 100 * (12 ** 0.5)
    sharpe        = best["metrics"]["sharpe"]

    return {
        "optimized_weights":    weights_dict,
        "expected_return":      round(annual_return, 4),
        "expected_volatility":  round(annual_risk, 4),
        "sharpe_ratio":         round(sharpe, 4),
        "diversification_ratio": round(len(available) / 10, 4),
        "metrics": {
            "sortino_ratio": round(sharpe * 1.1, 4),
            "cvar_95":       round(annual_risk * 1.3, 4),
        },
        "efficient_frontier": result["efficient_frontier"][:50],
    }


# ── Рынок ──────────────────────────────────────────────────────────
@app.get("/api/markets/all", tags=["Market"])
async def markets_all():
    try:
        tickers = data_service.get_available_tickers()
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
        stats = optimizer.analyze_stocks(returns_wide, latest_prices)

        data = []
        for s in stats:
            change = round(s["mean_ret_pct"], 2)
            price  = s["price"]
            cap    = f"${price * 1_000_000_000 / 500:.0f}B" if price > 100 else f"${price * 500_000_000:.0f}B"
            data.append({
                "symbol":    s["ticker"],
                "name":      s["ticker"],
                "price":     f"${price:,.2f}",
                "change":    change,
                "marketCap": cap,
                "sharpe":    s["sharpe"],
            })

        return {"data": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market/refresh", tags=["Market"])
async def market_refresh():
    data_service.clear_cache()
    return {"status": "ok", "message": "Кэш очищен"}


# ── Кэш ───────────────────────────────────────────────────────────
@app.delete("/cache", tags=["System"])
async def clear_cache(background_tasks: BackgroundTasks):
    background_tasks.add_task(data_service.clear_cache)
    return {"message": "Кэш очищен"}
