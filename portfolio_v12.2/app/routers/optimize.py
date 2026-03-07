"""
routers/optimize.py — Эндпоинт оптимизации портфеля.

API-контракт сохранён полностью.
Изменения v7:
- risk_free_rate передаётся явно, без глобальной мутации
- логика выделена из main.py для лучшей читаемости
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from app.models import KnowledgeLevel, OptimizeRequest
from app.services import data_service, optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Optimization"])


@router.post("/optimize")
async def optimize(request: Request, body: OptimizeRequest):
    """
    Оптимизирует портфель по заданным тикерам и параметрам.
    Возвращает веса, метрики и сравнение всех методов.
    """
    tickers = [a.ticker for a in body.assets]
    is_pro  = (body.knowledge_level == KnowledgeLevel.professional)

    logger.info(
        f"Optimize: tickers={tickers}, model={body.optimization_model}, "
        f"budget={body.budget}, level={body.knowledge_level}"
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

    # Запуск оптимизации
    try:
        result = optimizer.run_optimization(
            tickers=available,
            returns_wide=returns_wide,
            latest_prices=latest_prices,
            budget=effective_budget,
            risk_free_rate=body.risk_free_rate,
            optimization_model=effective_model,
            allocation_limits=alloc_limits,
            max_assets=body.max_assets,
            knowledge_level=body.knowledge_level.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"Ошибка оптимизации: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка оптимизации: {exc}")

    # Формируем ответ (контракт сохранён)
    best          = next(p for p in result["portfolios"] if p["name"] == result["best_portfolio"])
    weights_dict  = dict(zip(best["tickers"], best["weights"]))
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
        "diversification_ratio":  round(n / max(n, 10), 4),
        "metrics": {
            "sortino_ratio": round(sharpe * 1.1, 4),   # TODO: заменить на реальный Sortino
            "cvar_95":       round(annual_risk * 1.3, 4),  # TODO: заменить на реальный CVaR
        },
        "efficient_frontier": result["efficient_frontier"][:50],
        "stock_stats":        result.get("stock_stats") or [],
        "all_portfolios":     result["portfolios"],
        "best_portfolio":     result["best_portfolio"],
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

    return response
