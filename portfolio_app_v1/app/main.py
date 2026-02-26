import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.models import (
    OptimizeRequest,
    OptimizeResponse,
    AssetListResponse,
    HealthResponse,
)
from app.services import data_service
from app.services import optimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Portfolio Optimizer API starting...")
    yield
    logger.info("Portfolio Optimizer API stopped.")


app = FastAPI(
    title="Portfolio Optimizer API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Portfolio Optimizer API", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
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
    return HealthResponse(status="ok", db_connected=db_ok)


@app.get("/assets", response_model=AssetListResponse, tags=["Data"])
async def get_assets():
    try:
        tickers = data_service.get_available_tickers()
        if not tickers:
            tickers = ["AAPL", "AMGN", "GOOGL", "HON", "JPM",
                       "META", "MSFT", "NVDA", "TSLA", "XOM"]
        return AssetListResponse(tickers=sorted(tickers), count=len(tickers))
    except Exception as e:
        logger.exception("Failed to fetch asset list")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize", response_model=OptimizeResponse, tags=["Optimization"])
async def optimize_portfolio(request: OptimizeRequest):
    logger.info(f"Optimize: tickers={request.tickers}, budget={request.budget}")

    try:
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(
            request.tickers
        )
    except Exception as e:
        logger.exception("Data loading failed")
        raise HTTPException(status_code=422, detail=f"Ошибка загрузки данных: {e}")

    if len(available) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Нужно минимум 2 тикера. Загружено: {available}",
        )

    try:
        result = optimizer.run_optimization(
            tickers=available,
            returns_wide=returns_wide,
            latest_prices=latest_prices,
            budget=request.budget,
            risk_free_rate=request.risk_free_rate,
            methods=request.methods,
        )
    except Exception as e:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации: {e}")

    return result


@app.delete("/cache", tags=["System"])
async def clear_cache(background_tasks: BackgroundTasks):
    background_tasks.add_task(data_service.clear_cache)
    return {"message": "Кэш очищен"}
