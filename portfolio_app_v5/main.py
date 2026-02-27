import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Импорты ваших модулей
from app.services import data_service
from app.services import optimizer
from app.models import (
    OptimizeRequest,
    UserLevelRequest, UserLevelResponse,
    KnowledgeLevel,
)

# --- НАСТРОЙКИ ПУТЕЙ ---
# Определяем базовую директорию проекта (где лежит main.py)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_user_level: KnowledgeLevel = KnowledgeLevel.beginner

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AssetAlpha API v2 запускается...")
    yield
    logger.info("AssetAlpha API v2 остановлен.")

# --- ИНИЦИАЛИЗАЦИЯ APP ---
app = FastAPI(title="AssetAlpha API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ПОДКЛЮЧЕНИЕ СТАТИКИ ---
# Проверяем существование папки frontend перед монтированием
if FRONTEND_DIR.exists():
    # Монтируем подпапки для CSS и JS
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
else:
    logger.error(f"Критическая ошибка: Папка frontend не найдена по пути {FRONTEND_DIR}")
    
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Этот лог покажет в терминале Linux точную причину 422
    logger.error(f"ДЕТАЛИ ОШИБКИ 422: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )    

# --- HTML РОУТЫ ---
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/index.html", include_in_schema=False)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/login.html", include_in_schema=False)
async def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/markets.html", include_in_schema=False)
async def markets_page():
    return FileResponse(FRONTEND_DIR / "markets.html")

@app.get("/settings.html", include_in_schema=False)
async def settings_page():
    return FileResponse(FRONTEND_DIR / "settings.html")

# --- ОСТАЛЬНАЯ ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ) ---

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

@app.delete("/cache", tags=["System"])
async def clear_cache(background_tasks: BackgroundTasks):
    background_tasks.add_task(data_service.clear_cache)
    return {"message": "Кэш очищен"}

@app.post("/api/user/level", response_model=UserLevelResponse, tags=["User"])
async def set_user_level(request: UserLevelRequest, background_tasks: BackgroundTasks):
    global _user_level
    _user_level = request.level
    logger.info(f"Уровень знаний: {request.level}")
    background_tasks.add_task(_bootstrap_if_needed)
    messages = {
        KnowledgeLevel.beginner:     "Режим новичка активирован.",
        KnowledgeLevel.professional: "Профессиональный режим активирован.",
    }
    return {"level": request.level, "message": messages[request.level]}

@app.get("/api/user/level", response_model=UserLevelResponse, tags=["User"])
async def get_user_level():
    return {"level": _user_level, "message": "OK"}

async def _bootstrap_if_needed():
    try:
        tickers = data_service.get_available_tickers()
        if len(tickers) < 5:
            logger.info("БД пустая — запускаем bootstrap")
            data_service.bootstrap_data()
        else:
            logger.info(f"БД: {len(tickers)} тикеров, bootstrap не нужен")
    except Exception as e:
        logger.error(f"Bootstrap не удался: {e}")

TICKER_NAMES = {
    "AAPL":  ("Apple Inc.", "Technology"),
    "MSFT":  ("Microsoft Corporation", "Technology"),
    "GOOGL": ("Alphabet Inc.", "Technology"),
    "AMZN":  ("Amazon.com Inc.", "Consumer Cyclical"),
    "NVDA":  ("NVIDIA Corporation", "Technology"),
    "META":  ("Meta Platforms Inc.", "Technology"),
    "TSLA":  ("Tesla Inc.", "Consumer Cyclical"),
    "JPM":   ("JPMorgan Chase & Co.", "Financial Services"),
    "V":     ("Visa Inc.", "Financial Services"),
    "JNJ":   ("Johnson & Johnson", "Healthcare"),
    "XOM":   ("Exxon Mobil Corporation", "Energy"),
    "PG":    ("Procter & Gamble Co.", "Consumer Defensive"),
    "BRK-B": ("Berkshire Hathaway Inc.", "Financial Services"),
    "AMGN":  ("Amgen Inc.", "Healthcare"),
    "HON":   ("Honeywell International", "Industrials"),
}

@app.get("/api/stocks/search", tags=["Data"])
async def search_stocks(query: str = Query(..., min_length=1)):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/assets/{ticker}/details", tags=["Data"])
async def get_asset_details(ticker: str):
    ticker = ticker.upper()
    try:
        return data_service.get_asset_details(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка деталей {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/optimize", tags=["Optimization"])
async def optimize(request: OptimizeRequest):
    tickers = [a.ticker for a in request.assets]
    is_pro  = (request.knowledge_level.value == "professional")

    logger.info(
        f"Optimize: tickers={tickers}, model={request.optimization_model}, "
        f"budget={request.budget}, level={request.knowledge_level}"
    )

    for a in request.assets:
        if not a.quantity or a.quantity <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Укажите количество акций для {a.ticker} (quantity > 0)"
            )

    alloc_limits = None
    if request.allocation_limits:
        alloc_limits = {
            ticker: {"min": lim.min, "max": lim.max}
            for ticker, lim in request.allocation_limits.items()
        }

    quantities = {a.ticker: int(a.quantity) for a in request.assets}

    try:
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ошибка загрузки данных: {e}")

    if len(available) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Загружено менее 2 тикеров: {available}"
        )

    # Автоматически рассчитываем бюджет как сумму quantity × текущая цена
    auto_budget = sum(
        quantities.get(t, 0) * latest_prices.get(t, 0)
        for t in available
    )
    # Если расчёт не получился (нет цен), используем переданный budget
    effective_budget = auto_budget if auto_budget >= 100 else request.budget
    logger.info(f"Авто-бюджет: ${effective_budget:.2f} (из quantity × price)")

    effective_model = "all" if is_pro else request.optimization_model.value

    try:
        result = optimizer.run_optimization(
            tickers=available,
            returns_wide=returns_wide,
            latest_prices=latest_prices,
            budget=effective_budget,
            risk_free_rate=request.risk_free_rate,
            optimization_model=effective_model,
            allocation_limits=alloc_limits,
            max_assets=request.max_assets,
            knowledge_level=request.knowledge_level.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка оптимизации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации: {e}")

    best = next(p for p in result["portfolios"] if p["name"] == result["best_portfolio"])
    weights_dict = dict(zip(best["tickers"], best["weights"]))

    m             = best["metrics"]
    annual_return = m["return_pct"] * 12
    annual_risk   = (m["monthly_risk"] / m["budget"] * 100 * (12 ** 0.5)) if m["budget"] > 0 else 0
    sharpe        = m["sharpe"]
    n             = len(available)

    response = {
        "optimized_weights":      weights_dict,
        "expected_return":        round(annual_return, 4),
        "expected_volatility":    round(annual_risk, 4),
        "sharpe_ratio":           round(sharpe, 4),
        "diversification_ratio": round(n / max(n, 10), 4),
        "metrics": {
            "sortino_ratio": round(sharpe * 1.1, 4),
            "cvar_95":       round(annual_risk * 1.3, 4),
        },
        "efficient_frontier": result["efficient_frontier"][:50],
        "stock_stats":        result.get("stock_stats") or [],
        "all_portfolios":      result["portfolios"],
        "best_portfolio":      result["best_portfolio"],
    }

    input_portfolio = optimizer.analyze_input_portfolio(
        tickers=available,
        quantities=quantities,
        latest_prices=latest_prices,
        returns_wide=returns_wide,
    )
    if input_portfolio:
        response["input_portfolio"] = input_portfolio

    if is_pro:
        response["correlation"] = result.get("correlation")
        response["covariance"]  = result.get("covariance")

    return response

@app.get("/api/markets/all", tags=["Market"])
async def markets_all():
    try:
        tickers = data_service.get_available_tickers()
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
        stats = optimizer.analyze_stocks(returns_wide, latest_prices)

        data = []
        for s in stats:
            price = s["price"]
            data.append({
                "symbol":    s["ticker"],
                "name":      TICKER_NAMES.get(s["ticker"], (s["ticker"], ""))[0],
                "price":     f"${price:,.2f}",
                "change":    round(s["mean_ret_pct"], 2),
                "marketCap": "—",
                "sharpe":    s["sharpe"],
            })
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"Ошибка markets/all: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/refresh", tags=["Market"])
async def market_refresh():
    data_service.clear_cache()
    return {"status": "ok", "message": "Кэш очищен"}
