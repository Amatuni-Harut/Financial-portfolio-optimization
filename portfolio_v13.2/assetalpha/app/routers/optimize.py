"""
routers/optimize.py — Эндпоинт оптимизации портфеля.

Исправления v13.1:
- ИСПРАВЛЕНА формула аннуализации: (1 + r_monthly)^12 - 1 вместо r * 12
- knowledge_level читается из JWT через get_current_level (не app.state)
- CPU-bound оптимизация по-прежнему в ThreadPoolExecutor
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from typing import Optional

from app.routers.markets import _CURRENCY_RATES, _CURRENCY_SYMBOLS
from app.routers.auth import get_current_user, get_current_level
from app.models import KnowledgeLevel, OptimizeRequest
from app.services import data_service, optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Optimization"])

_executor = ThreadPoolExecutor(max_workers=4)


@router.post("/optimize")
async def optimize(
    request: Request,
    body: OptimizeRequest,
    x_settings_currency: Optional[str] = Header(default="usd"),
    current_user:  Optional[str]  = Depends(get_current_user),
    current_level: KnowledgeLevel = Depends(get_current_level),
):
    """
    Оптимизирует портфель по заданным тикерам и параметрам.

    knowledge_level берётся из JWT (per-user), не из app.state.
    Если передан в body — body имеет приоритет (для анонимных пользователей).
    """
    # body.knowledge_level имеет приоритет; для авторизованных — из JWT
    effective_level = body.knowledge_level if current_user is None else current_level
    is_pro = (effective_level == KnowledgeLevel.professional)

    tickers = [a.ticker for a in body.assets]

    logger.info(
        f"Optimize: user={current_user or 'anon'}, tickers={tickers}, "
        f"model={body.optimization_model}, budget={body.budget}, level={effective_level}"
    )

    # Валидация количества акций
    for asset in body.assets:
        if not asset.quantity or asset.quantity <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Укажите количество акций для {asset.ticker} (quantity > 0)",
            )

    alloc_limits = None
    if body.allocation_limits:
        alloc_limits = {
            ticker: {"min": lim.min, "max": lim.max}
            for ticker, lim in body.allocation_limits.items()
        }

    quantities = {a.ticker: int(a.quantity) for a in body.assets}

    # Загрузка данных
    try:
        returns_wide, latest_prices, available = data_service.build_returns_and_prices(tickers)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Ошибка загрузки данных: {exc}")

    if len(available) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Загружено менее 2 тикеров: {available}",
        )

    # Автоматический расчёт бюджета из quantity × цена
    auto_budget = sum(
        quantities.get(t, 0) * latest_prices.get(t, 0)
        for t in available
    )
    effective_budget = auto_budget if auto_budget >= 100 else body.budget
    logger.info(f"Авто-бюджет: ${effective_budget:.2f}")

    effective_model = "all" if is_pro else body.optimization_model.value

    # Запуск оптимизации в ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            _executor,
            lambda: optimizer.run_optimization(
                tickers=available,
                returns_wide=returns_wide,
                latest_prices=latest_prices,
                budget=effective_budget,
                risk_free_rate=body.risk_free_rate,
                optimization_model=effective_model,
                allocation_limits=alloc_limits,
                max_assets=body.max_assets,
                knowledge_level=effective_level.value,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"Ошибка оптимизации: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации: {exc}")

    best         = next(p for p in result["portfolios"] if p["name"] == result["best_portfolio"])
    weights_dict = dict(zip(best["tickers"], best["weights"]))
    m            = best["metrics"]

    # --- ИСПРАВЛЕНО: compound annualization вместо simple multiplication ---
    # Было:   annual_return = m["return_pct"] * 12  (некорректно)
    # Стало:  (1 + r_monthly/100)^12 - 1            (финансово корректно)
    monthly_ret_frac = m["return_pct"] / 100.0
    annual_return    = round(((1 + monthly_ret_frac) ** 12 - 1) * 100, 4)

    # Волатильность аннуализируется через sqrt(12) — это стандарт
    annual_risk = (
        (m["monthly_risk"] / m["budget"] * 100 * (12 ** 0.5))
        if m["budget"] > 0 else 0
    )

    response = {
        "optimized_weights":     weights_dict,
        "expected_return":       annual_return,           # compound annualized
        "expected_volatility":   round(annual_risk, 4),
        "sharpe_ratio":          round(m["sharpe"], 4),
        "diversification_ratio": result["diversification_ratio"],
        "metrics": {
            "sortino_ratio": result["sortino_ratio"],
            "cvar_95":       result["cvar_95"],
        },
        "efficient_frontier": result["efficient_frontier"][:100],
        "stock_stats":        result.get("stock_stats") or [],
        "all_portfolios":     result["portfolios"],
        "best_portfolio":     result["best_portfolio"],
        "knowledge_level":    effective_level.value,  # отдаём клиенту для отладки
    }

    # Анализ введённого портфеля
    input_portfolio = optimizer.analyze_input_portfolio(
        tickers=available,
        quantities=quantities,
        latest_prices=latest_prices,
        returns_wide=returns_wide,
        risk_free_monthly=body.risk_free_rate / 12,
    )
    if input_portfolio:
        response["input_portfolio"] = input_portfolio

    # Дополнительные данные для профессионального режима
    if is_pro:
        response["correlation"] = result.get("correlation")
        response["covariance"]  = result.get("covariance")

    # Конвертируем денежные метрики согласно валюте пользователя
    cur  = (x_settings_currency or "usd").lower()
    rate = _CURRENCY_RATES.get(cur, 1.0)

    def apply_rate(portfolios_list):
        for p in portfolios_list:
            pm = p.get("metrics", {})
            for key in ("budget", "monthly_profit", "monthly_risk"):
                if key in pm and pm[key] is not None:
                    pm[key] = round(pm[key] * rate, 2)
        return portfolios_list

    if rate != 1.0:
        response["all_portfolios"] = apply_rate(response["all_portfolios"])
        if response.get("input_portfolio"):
            apply_rate([response["input_portfolio"]])

    return response
