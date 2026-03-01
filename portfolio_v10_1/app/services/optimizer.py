"""
optimizer.py — Движок оптимизации портфеля.

Изменения в v7:
- Убрана мутация глобальной переменной RISK_FREE_MONTHLY.
  risk_free теперь передаётся явно через всю цепочку вызовов.
  Это устраняет race condition при одновременных запросах.
- Математика и алгоритмы не изменены.
- Улучшена читаемость через вспомогательную функцию _resolve_risk_free().
"""
import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

# Константы — только для чтения, не мутируются
_RISK_FREE_ANNUAL_DEFAULT = 0.02
_RISK_FREE_MONTHLY_DEFAULT = _RISK_FREE_ANNUAL_DEFAULT / 12
MC_ITERATIONS = 10_000
MC_SEED = 42


def _monthly_rf(annual_rate: Optional[float]) -> float:
    """Конвертирует годовую безрисковую ставку в месячную."""
    if annual_rate is None:
        return _RISK_FREE_MONTHLY_DEFAULT
    return annual_rate / 12


# ============================================================
# СТРУКТУРЫ ДАННЫХ
# ============================================================

@dataclass
class PortfolioMetrics:
    budget: float
    monthly_profit: float
    monthly_risk: float
    sharpe: float
    payback_months: float
    return_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortfolioResult:
    name: str
    metrics: PortfolioMetrics
    tickers: List[str]
    shares: List[int]
    weights: List[float]

    def to_dict(self) -> dict:
        return {
            "name":    self.name,
            "metrics": self.metrics.to_dict(),
            "tickers": self.tickers,
            "shares":  self.shares,
            "weights": [round(w, 4) for w in self.weights],
        }


# ============================================================
# БАЗОВЫЕ ВЫЧИСЛЕНИЯ (математика не изменена)
# ============================================================

def _portfolio_performance(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_monthly: float,
) -> Tuple[float, float, float]:
    port_return = float(np.dot(weights, mean_returns))
    port_std = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
    sharpe = (port_return - risk_free_monthly) / port_std if port_std > 0 else 0.0
    return port_return, port_std, sharpe


def _calc_metrics(
    shares: np.ndarray,
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
) -> PortfolioMetrics:
    p = np.array([prices[t] for t in tickers])
    budget = float(np.sum(shares * p))
    if budget <= 0:
        return PortfolioMetrics(0, 0, 0, 0, float("inf"), 0)
    weights = (shares * p) / budget
    ret_rel  = float(np.dot(weights, mean_returns))
    risk_rel = float(math.sqrt(max(float(weights @ cov_matrix @ weights), 0)))
    abs_profit = ret_rel * budget
    abs_risk   = risk_rel * budget
    sharpe = (ret_rel - risk_free_monthly) / risk_rel if risk_rel > 0 else 0.0
    payback = budget / abs_profit if abs_profit > 0 else float("inf")
    return PortfolioMetrics(
        budget=round(budget, 2),
        monthly_profit=round(abs_profit, 2),
        monthly_risk=round(abs_risk, 2),
        sharpe=round(sharpe, 6),
        payback_months=round(min(payback, 9999), 2),
        return_pct=round(ret_rel * 100, 6),
    )


def _weights_to_result(
    name: str,
    weights: np.ndarray,
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
) -> PortfolioResult:
    p = np.array([prices[t] for t in tickers])
    shares = np.floor(weights * budget / p)
    shares = _fill_budget(shares, tickers, prices, mean_returns, cov_matrix, budget, risk_free_monthly)
    metrics = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix, risk_free_monthly)
    actual_budget = metrics.budget
    actual_weights = [
        (int(shares[i]) * p[i]) / actual_budget if actual_budget > 0 else 0
        for i in range(len(tickers))
    ]
    return PortfolioResult(name, metrics, tickers, [int(s) for s in shares], actual_weights)


def _fill_budget(
    shares: np.ndarray,
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    target: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
) -> np.ndarray:
    """Добирает акции на остаток бюджета, максимизируя Sharpe."""
    p = np.array([prices[t] for t in tickers])
    shares = shares.copy()
    for _ in range(5000):
        remaining = target - float(np.sum(shares * p))
        if remaining < p.min():
            break
        current_sh = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix, risk_free_monthly).sharpe
        best_delta, best_i = -np.inf, -1
        for i in range(len(tickers)):
            if p[i] > remaining:
                continue
            test = shares.copy()
            test[i] += 1
            delta = _calc_metrics(test, tickers, prices, mean_returns, cov_matrix, risk_free_monthly).sharpe - current_sh
            if delta > best_delta:
                best_delta, best_i = delta, i
        if best_i == -1:
            break
        shares[best_i] += 1
    return shares


# ============================================================
# ВАЛИДАЦИЯ ОГРАНИЧЕНИЙ
# ============================================================

def validate_constraints(
    tickers: List[str],
    allocation_limits: Optional[Dict[str, Dict[str, float]]],
    max_assets: Optional[int],
) -> Tuple[bool, str]:
    if not allocation_limits:
        return True, ""

    total_min = 0.0
    for ticker in tickers:
        limits = allocation_limits.get(ticker, {})
        min_w = limits.get("min", 0.0)
        max_w = limits.get("max", 1.0)

        if not (0 <= min_w <= 1):
            return False, f"min для {ticker} должен быть от 0 до 1"
        if not (0 <= max_w <= 1):
            return False, f"max для {ticker} должен быть от 0 до 1"
        if min_w > max_w:
            return False, f"min > max для {ticker}: {min_w} > {max_w}"

        total_min += min_w

    if total_min > 1.0:
        return False, (
            f"Сумма минимальных весов ({total_min:.1%}) превышает 100%. "
            "Ограничения математически невыполнимы."
        )
    return True, ""


def _build_bounds(
    tickers: List[str],
    allocation_limits: Optional[Dict[str, Dict[str, float]]],
) -> List[Tuple[float, float]]:
    return [
        (
            allocation_limits[t].get("min", 0.0) if allocation_limits and t in allocation_limits else 0.0,
            allocation_limits[t].get("max", 1.0) if allocation_limits and t in allocation_limits else 1.0,
        )
        for t in tickers
    ]


def _apply_max_assets(weights: np.ndarray, max_assets: int) -> np.ndarray:
    if max_assets >= len(weights):
        return weights
    weights = weights.copy()
    weights[np.argsort(weights)[:-max_assets]] = 0.0
    total = weights.sum()
    if total > 0:
        weights /= total
    return weights


# ============================================================
# МЕТОДЫ ОПТИМИЗАЦИИ (математика не изменена)
# ============================================================

def max_sharpe_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
) -> PortfolioResult:
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def neg_sharpe(w):
        ret, std, _ = _portfolio_performance(w, mean_returns, cov_matrix, risk_free_monthly)
        return -(ret - risk_free_monthly) / std if std > 0 else 0.0

    result = minimize(neg_sharpe, np.full(n, 1 / n), method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Max Sharpe", weights, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


def min_volatility_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
) -> PortfolioResult:
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def portfolio_vol(w):
        return float(np.sqrt(np.dot(w.T, np.dot(cov_matrix, w))))

    result = minimize(portfolio_vol, np.full(n, 1 / n), method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Min Volatility", weights, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


def risk_parity_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
) -> PortfolioResult:
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def risk_parity_obj(w):
        port_var = float(w @ cov_matrix @ w)
        if port_var <= 0:
            return 1e10
        risk_contrib = w * (cov_matrix @ w) / port_var
        target = 1.0 / n
        return float(np.sum((risk_contrib - target) ** 2))

    result = minimize(risk_parity_obj, np.full(n, 1 / n), method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Risk Parity", weights, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


def min_cvar_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    confidence: float = 0.95,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
    n_scenarios: int = 10_000,
) -> PortfolioResult:
    n = len(tickers)
    np.random.seed(MC_SEED)

    try:
        scenarios = np.random.multivariate_normal(mean_returns, cov_matrix, n_scenarios)
    except Exception:
        scenarios = np.random.normal(0, np.sqrt(np.diag(cov_matrix)), (n_scenarios, n))

    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def cvar_objective(w):
        port_returns = scenarios @ w
        var_threshold = np.percentile(port_returns, (1 - confidence) * 100)
        tail_losses = port_returns[port_returns <= var_threshold]
        return -float(np.mean(tail_losses)) if len(tail_losses) > 0 else 0.0

    result = minimize(cvar_objective, np.full(n, 1 / n), method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Min CVaR", weights, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


def monte_carlo_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
    n_iter: int = MC_ITERATIONS,
) -> PortfolioResult:
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    np.random.seed(MC_SEED)

    best_sharpe, best_w = -np.inf, None
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    for _ in range(n_iter):
        w = np.random.dirichlet(np.ones(n))
        w = np.clip(w, lo, hi)
        total = w.sum()
        if total <= 0:
            continue
        w /= total
        _, _, sh = _portfolio_performance(w, mean_returns, cov_matrix, risk_free_monthly)
        if sh > best_sharpe:
            best_sharpe, best_w = sh, w

    if best_w is None:
        best_w = np.full(n, 1 / n)

    if max_assets:
        best_w = _apply_max_assets(best_w, max_assets)
        best_w /= best_w.sum()

    return _weights_to_result("Monte Carlo", best_w, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


def equal_weight_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
    max_assets: Optional[int] = None,
) -> PortfolioResult:
    n = len(tickers)
    if max_assets and max_assets < n:
        individual_sharpes = [
            (mean_returns[i] / np.sqrt(cov_matrix[i, i]) if cov_matrix[i, i] > 0 else 0, i)
            for i in range(n)
        ]
        top_indices = [idx for _, idx in sorted(individual_sharpes, reverse=True)[:max_assets]]
        weights = np.zeros(n)
        weights[top_indices] = 1.0 / max_assets
    else:
        weights = np.full(n, 1 / n)
    return _weights_to_result("Equal Weight", weights, tickers, prices,
                               mean_returns, cov_matrix, budget, risk_free_monthly)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ АНАЛИТИЧЕСКИЕ ФУНКЦИИ
# ============================================================

def compute_efficient_frontier(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_portfolios: int = 2000,
) -> List[Dict]:
    np.random.seed(0)
    n = len(mean_returns)
    results = []
    for _ in range(n_portfolios):
        w = np.random.dirichlet(np.ones(n))
        ret, std, sh = _portfolio_performance(w, mean_returns, cov_matrix, _RISK_FREE_MONTHLY_DEFAULT)
        results.append({
            "return": round(ret * 100, 4),
            "risk":   round(std * 100, 4),
            "sharpe": round(sh, 4),
        })
    return results


def analyze_stocks(
    returns_wide: pd.DataFrame,
    latest_prices: Dict[str, float],
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
) -> List[Dict]:
    stats = []
    for ticker in returns_wide.columns:
        rets  = returns_wide[ticker].dropna()
        price = latest_prices[ticker]
        mr    = float(rets.mean())
        sr    = float(rets.std())
        sharpe = (mr - risk_free_monthly) / sr if sr > 0 else 0.0
        stats.append({
            "ticker":       ticker,
            "price":        round(price, 2),
            "mean_ret_pct": round(mr * 100, 4),
            "std_ret_pct":  round(sr * 100, 4),
            "abs_profit":   round(mr * price, 4),
            "abs_risk":     round(sr * price, 4),
            "sharpe":       round(sharpe, 4),
        })
    return stats


def compute_correlation(returns_wide: pd.DataFrame) -> Dict:
    corr = returns_wide.corr().round(4)
    return {"tickers": corr.columns.tolist(), "matrix": corr.values.tolist()}


# ============================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# ============================================================

def run_optimization(
    tickers: List[str],
    returns_wide: pd.DataFrame,
    latest_prices: Dict[str, float],
    budget: float,
    risk_free_rate: float = 0.02,
    optimization_model: str = "all",
    allocation_limits: Optional[Dict[str, Dict[str, float]]] = None,
    max_assets: Optional[int] = None,
    knowledge_level: str = "beginner",
    methods: Optional[List[str]] = None,  # устаревший параметр, оставлен для совместимости
) -> Dict:
    """
    Главная функция оптимизации.
    risk_free_rate передаётся явно — глобальная мутация устранена.
    """
    rf_monthly = _monthly_rf(risk_free_rate)

    available = [t for t in tickers if t in returns_wide.columns and t in latest_prices]
    if len(available) < 2:
        raise ValueError(f"Нужно минимум 2 тикера, доступно: {available}")

    ok, err = validate_constraints(available, allocation_limits, max_assets)
    if not ok:
        raise ValueError(err)

    returns  = returns_wide[available].dropna()
    mean_ret = returns.mean().values
    cov_mat  = returns.cov().values
    prices   = {t: latest_prices[t] for t in available}

    # Доступные модели по уровню пользователя
    if knowledge_level == "beginner":
        allowed_models = {"equal_weight", "max_sharpe"}
    else:
        allowed_models = {"max_sharpe", "min_volatility", "risk_parity",
                          "min_cvar", "monte_carlo", "equal_weight"}

    if optimization_model == "all":
        models_to_run = allowed_models
    elif optimization_model in allowed_models:
        models_to_run = {optimization_model}
    else:
        models_to_run = {"max_sharpe"}

    # Общие аргументы для всех методов
    common = dict(
        tickers=available,
        prices=prices,
        mean_returns=mean_ret,
        cov_matrix=cov_mat,
        budget=budget,
        risk_free_monthly=rf_monthly,
        allocation_limits=allocation_limits,
        max_assets=max_assets,
    )

    portfolios: List[Dict] = []

    if "max_sharpe" in models_to_run:
        portfolios.append(max_sharpe_opt(**common).to_dict())

    if "min_volatility" in models_to_run:
        portfolios.append(min_volatility_opt(**common).to_dict())

    if "risk_parity" in models_to_run:
        portfolios.append(risk_parity_opt(**common).to_dict())

    if "min_cvar" in models_to_run:
        portfolios.append(min_cvar_opt(**common).to_dict())

    if "monte_carlo" in models_to_run:
        n_iter = 3000 if optimization_model == "all" else MC_ITERATIONS
        portfolios.append(monte_carlo_opt(**common, n_iter=n_iter).to_dict())

    if "equal_weight" in models_to_run:
        portfolios.append(equal_weight_opt(
            tickers=available, prices=prices, mean_returns=mean_ret,
            cov_matrix=cov_mat, budget=budget, risk_free_monthly=rf_monthly,
            max_assets=max_assets,
        ).to_dict())

    if not portfolios:
        raise ValueError("Не удалось запустить ни одного метода оптимизации")

    frontier     = compute_efficient_frontier(mean_ret, cov_mat)
    stock_stats  = analyze_stocks(returns, prices, rf_monthly)
    correlation  = compute_correlation(returns)
    cov_df       = returns.cov().round(6)
    covariance   = {"tickers": cov_df.columns.tolist(), "matrix": cov_df.values.tolist()}

    best = max(portfolios, key=lambda p: p["metrics"]["sharpe"])

    return {
        "tickers_used":     available,
        "portfolios":       portfolios,
        "best_portfolio":   best["name"],
        "efficient_frontier": frontier,
        "stock_stats":      stock_stats,
        "correlation":      correlation,
        "covariance":       covariance,
    }


# ============================================================
# МЕТРИКИ ВВЕДЁННОГО ПОРТФЕЛЯ
# ============================================================

def analyze_input_portfolio(
    tickers: List[str],
    quantities: Dict[str, int],
    latest_prices: Dict[str, float],
    returns_wide: pd.DataFrame,
    risk_free_monthly: float = _RISK_FREE_MONTHLY_DEFAULT,
) -> Optional[Dict]:
    available = [
        t for t in tickers
        if t in returns_wide.columns and t in latest_prices and quantities.get(t, 0) > 0
    ]
    if not available:
        return None

    returns     = returns_wide[available].dropna()
    mean_ret    = returns.mean().values
    cov_mat     = returns.cov().values
    prices_arr  = np.array([latest_prices[t] for t in available])
    shares_arr  = np.array([float(quantities.get(t, 0)) for t in available])

    budget = float(np.sum(shares_arr * prices_arr))
    if budget <= 0:
        return None

    weights  = (shares_arr * prices_arr) / budget
    ret_rel  = float(np.dot(weights, mean_ret))
    risk_rel = float(np.sqrt(max(float(weights @ cov_mat @ weights), 0)))
    sharpe   = (ret_rel - risk_free_monthly) / risk_rel if risk_rel > 0 else 0.0
    payback  = budget / (ret_rel * budget) if ret_rel > 0 else float("inf")

    return {
        "tickers": available,
        "shares":  [int(quantities.get(t, 0)) for t in available],
        "weights": [round(float(w), 4) for w in weights],
        "metrics": {
            "budget":         round(budget, 2),
            "monthly_profit": round(ret_rel * budget, 2),
            "monthly_risk":   round(risk_rel * budget, 2),
            "sharpe":         round(sharpe, 4),
            "payback_months": round(min(payback, 9999), 1),
            "return_pct":     round(ret_rel * 100, 4),
        },
    }
