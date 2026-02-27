"""
optimizer.py — Движок оптимизации портфеля.
Поддерживает: max_sharpe, min_volatility, risk_parity, min_cvar, equal_weight, monte_carlo.
Принимает constraints: min/max вес на актив, max_assets, budget.
"""
import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

RISK_FREE_ANNUAL = 0.02
RISK_FREE_MONTHLY = RISK_FREE_ANNUAL / 12
MC_ITERATIONS = 10_000
MC_SEED = 42


# ================================================================
# СТРУКТУРЫ ДАННЫХ
# ================================================================

@dataclass
class PortfolioMetrics:
    budget: float
    monthly_profit: float
    monthly_risk: float
    sharpe: float
    payback_months: float
    return_pct: float

    def to_dict(self):
        return asdict(self)


@dataclass
class PortfolioResult:
    name: str
    metrics: PortfolioMetrics
    tickers: List[str]
    shares: List[int]
    weights: List[float]

    def to_dict(self):
        return {
            "name": self.name,
            "metrics": self.metrics.to_dict(),
            "tickers": self.tickers,
            "shares": self.shares,
            "weights": [round(w, 4) for w in self.weights],
        }


# ================================================================
# БАЗОВЫЕ ВЫЧИСЛЕНИЯ
# ================================================================

def _portfolio_performance(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free: float = None
) -> Tuple[float, float, float]:
    if risk_free is None:
        risk_free = RISK_FREE_MONTHLY
    port_return = float(np.dot(weights, mean_returns))
    port_std = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
    sharpe = (port_return - risk_free) / port_std if port_std > 0 else 0.0
    return port_return, port_std, sharpe


def _calc_metrics(
    shares: np.ndarray,
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray
) -> PortfolioMetrics:
    p = np.array([prices[t] for t in tickers])
    budget = float(np.sum(shares * p))
    if budget <= 0:
        return PortfolioMetrics(0, 0, 0, 0, float("inf"), 0)
    weights = (shares * p) / budget
    ret_rel = float(np.dot(weights, mean_returns))
    risk_rel = float(math.sqrt(max(float(weights @ cov_matrix @ weights), 0)))
    abs_profit = ret_rel * budget
    abs_risk = risk_rel * budget
    sharpe = (ret_rel - RISK_FREE_MONTHLY) / risk_rel if risk_rel > 0 else 0.0
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
    budget: float
) -> PortfolioResult:
    """Конвертирует веса в PortfolioResult с реальным количеством акций."""
    p = np.array([prices[t] for t in tickers])
    shares = np.floor(weights * budget / p)
    shares = _fill_budget(shares, tickers, prices, mean_returns, cov_matrix, budget)
    metrics = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix)
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
    target: float
) -> np.ndarray:
    """Добирает акции на остаток бюджета, максимизируя Sharpe."""
    p = np.array([prices[t] for t in tickers])
    shares = shares.copy()
    for _ in range(5000):
        remaining = target - float(np.sum(shares * p))
        if remaining < p.min():
            break
        current_sh = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix).sharpe
        best_delta, best_i = -np.inf, -1
        for i in range(len(tickers)):
            if p[i] > remaining:
                continue
            test = shares.copy()
            test[i] += 1
            d = _calc_metrics(test, tickers, prices, mean_returns, cov_matrix).sharpe - current_sh
            if d > best_delta:
                best_delta, best_i = d, i
        if best_i == -1:
            break
        shares[best_i] += 1
    return shares


# ================================================================
# ВАЛИДАЦИЯ ОГРАНИЧЕНИЙ
# ================================================================

def validate_constraints(
    tickers: List[str],
    allocation_limits: Optional[Dict[str, Dict[str, float]]],
    max_assets: Optional[int]
) -> Tuple[bool, str]:
    """
    Проверяет математическую выполнимость ограничений.
    Возвращает (ok, error_message).
    """
    if not allocation_limits:
        return True, ""

    total_min = 0.0
    for ticker in tickers:
        limits = allocation_limits.get(ticker, {})
        min_w = limits.get("min", 0.0)
        max_w = limits.get("max", 1.0)

        if min_w < 0 or min_w > 1:
            return False, f"min для {ticker} должен быть от 0 до 1"
        if max_w < 0 or max_w > 1:
            return False, f"max для {ticker} должен быть от 0 до 1"
        if min_w > max_w:
            return False, f"min > max для {ticker}: {min_w} > {max_w}"

        total_min += min_w

    if total_min > 1.0:
        return False, (
            f"Сумма минимальных весов ({total_min:.1%}) превышает 100%. "
            f"Ограничения математически невыполнимы."
        )

    if max_assets and max_assets < len(tickers):
        # Проверяем что хватит активов
        pass

    return True, ""


def _build_bounds(
    tickers: List[str],
    allocation_limits: Optional[Dict[str, Dict[str, float]]]
) -> List[Tuple[float, float]]:
    """Строит bounds для scipy из allocation_limits."""
    bounds = []
    for t in tickers:
        if allocation_limits and t in allocation_limits:
            lo = allocation_limits[t].get("min", 0.0)
            hi = allocation_limits[t].get("max", 1.0)
        else:
            lo, hi = 0.0, 1.0
        bounds.append((lo, hi))
    return bounds


def _apply_max_assets(weights: np.ndarray, max_assets: int) -> np.ndarray:
    """Обнуляет активы ниже порога, оставляя max_assets лучших."""
    if max_assets >= len(weights):
        return weights
    threshold_indices = np.argsort(weights)[:-max_assets]
    weights = weights.copy()
    weights[threshold_indices] = 0.0
    total = weights.sum()
    if total > 0:
        weights /= total
    return weights


# ================================================================
# МЕТОДЫ ОПТИМИЗАЦИИ (scipy-based)
# ================================================================

def max_sharpe_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free: float = None,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None
) -> PortfolioResult:
    """Максимальный коэффициент Шарпа через scipy minimize."""
    if risk_free is None:
        risk_free = RISK_FREE_MONTHLY
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def neg_sharpe(w):
        ret, std, _ = _portfolio_performance(w, mean_returns, cov_matrix, risk_free)
        return -(ret - risk_free) / std if std > 0 else 0.0

    w0 = np.array([1 / n] * n)
    result = minimize(neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Max Sharpe", weights, tickers, prices, mean_returns, cov_matrix, budget)


def min_volatility_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None
) -> PortfolioResult:
    """Минимальная волатильность через scipy minimize."""
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def portfolio_vol(w):
        return float(np.sqrt(np.dot(w.T, np.dot(cov_matrix, w))))

    w0 = np.array([1 / n] * n)
    result = minimize(portfolio_vol, w0, method="SLSQP", bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Min Volatility", weights, tickers, prices, mean_returns, cov_matrix, budget)


def risk_parity_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None
) -> PortfolioResult:
    """
    Risk Parity: каждый актив вносит равный вклад в общий риск.
    Минимизируем отклонение вкладов рисков от равного.
    """
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def risk_parity_obj(w):
        port_var = float(w @ cov_matrix @ w)
        if port_var <= 0:
            return 1e10
        marginal_contrib = cov_matrix @ w
        risk_contrib = w * marginal_contrib / port_var
        target = 1.0 / n
        return float(np.sum((risk_contrib - target) ** 2))

    w0 = np.array([1 / n] * n)
    result = minimize(risk_parity_obj, w0, method="SLSQP", bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Risk Parity", weights, tickers, prices, mean_returns, cov_matrix, budget)


def min_cvar_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    confidence: float = 0.95,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
    n_scenarios: int = 10000
) -> PortfolioResult:
    """
    Минимальный CVaR (Conditional Value at Risk) через сценарное моделирование.
    CVaR = среднее потерь в худших (1-confidence)% сценариев.
    """
    n = len(tickers)
    np.random.seed(MC_SEED)

    # Генерируем сценарии доходностей
    try:
        scenarios = np.random.multivariate_normal(mean_returns, cov_matrix, n_scenarios)
    except Exception:
        # Если матрица вырождена — используем диагональную
        scenarios = np.random.normal(0, np.sqrt(np.diag(cov_matrix)), (n_scenarios, n))

    bounds = _build_bounds(tickers, allocation_limits)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    def cvar_objective(w):
        port_returns = scenarios @ w
        var_threshold = np.percentile(port_returns, (1 - confidence) * 100)
        tail_losses = port_returns[port_returns <= var_threshold]
        return -float(np.mean(tail_losses)) if len(tail_losses) > 0 else 0.0

    w0 = np.array([1 / n] * n)
    result = minimize(cvar_objective, w0, method="SLSQP", bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    weights = result.x
    if max_assets:
        weights = _apply_max_assets(weights, max_assets)
        weights /= weights.sum()
    return _weights_to_result("Min CVaR", weights, tickers, prices, mean_returns, cov_matrix, budget)


def monte_carlo_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    risk_free: float = None,
    allocation_limits: Optional[Dict] = None,
    max_assets: Optional[int] = None,
    n_iter: int = MC_ITERATIONS
) -> PortfolioResult:
    """Monte Carlo: случайный поиск с учётом bounds."""
    if risk_free is None:
        risk_free = RISK_FREE_MONTHLY
    n = len(tickers)
    bounds = _build_bounds(tickers, allocation_limits)

    np.random.seed(MC_SEED)
    best_sharpe, best_w = -np.inf, None

    for _ in range(n_iter):
        # Генерируем случайные веса в пределах bounds
        w = np.random.dirichlet(np.ones(n))
        # Применяем bounds через clipping
        lo = np.array([b[0] for b in bounds])
        hi = np.array([b[1] for b in bounds])
        w = np.clip(w, lo, hi)
        total = w.sum()
        if total <= 0:
            continue
        w /= total

        _, _, sh = _portfolio_performance(w, mean_returns, cov_matrix, risk_free)
        if sh > best_sharpe:
            best_sharpe, best_w = sh, w

    if best_w is None:
        best_w = np.array([1 / n] * n)

    if max_assets:
        best_w = _apply_max_assets(best_w, max_assets)
        best_w /= best_w.sum()

    return _weights_to_result("Monte Carlo", best_w, tickers, prices, mean_returns, cov_matrix, budget)


def equal_weight_opt(
    tickers: List[str],
    prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    budget: float,
    max_assets: Optional[int] = None
) -> PortfolioResult:
    """Равновесный портфель."""
    n = len(tickers)
    if max_assets and max_assets < n:
        # Берём топ-N по Sharpe
        individual_sharpes = []
        for i, t in enumerate(tickers):
            sr = mean_returns[i] / np.sqrt(cov_matrix[i, i]) if cov_matrix[i, i] > 0 else 0
            individual_sharpes.append((sr, i))
        top_indices = [idx for _, idx in sorted(individual_sharpes, reverse=True)[:max_assets]]
        weights = np.zeros(n)
        weights[top_indices] = 1.0 / max_assets
    else:
        weights = np.array([1 / n] * n)
    return _weights_to_result("Equal Weight", weights, tickers, prices, mean_returns, cov_matrix, budget)


# ================================================================
# ВСПОМОГАТЕЛЬНЫЕ АНАЛИТИЧЕСКИЕ ФУНКЦИИ
# ================================================================

def compute_efficient_frontier(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_portfolios: int = 2000
) -> List[Dict]:
    np.random.seed(0)
    n = len(mean_returns)
    results = []
    for _ in range(n_portfolios):
        w = np.random.dirichlet(np.ones(n))
        ret, std, sh = _portfolio_performance(w, mean_returns, cov_matrix)
        results.append({
            "return": round(ret * 100, 4),
            "risk": round(std * 100, 4),
            "sharpe": round(sh, 4)
        })
    return results


def analyze_stocks(
    returns_wide: pd.DataFrame,
    latest_prices: Dict[str, float]
) -> List[Dict]:
    stats = []
    for t in returns_wide.columns:
        rets = returns_wide[t].dropna()
        price = latest_prices[t]
        mr = float(rets.mean())
        sr = float(rets.std())
        sharpe = (mr - RISK_FREE_MONTHLY) / sr if sr > 0 else 0.0
        stats.append({
            "ticker": t,
            "price": round(price, 2),
            "mean_ret_pct": round(mr * 100, 4),
            "std_ret_pct": round(sr * 100, 4),
            "abs_profit": round(mr * price, 4),
            "abs_risk": round(sr * price, 4),
            "sharpe": round(sharpe, 4),
        })
    return stats


def compute_correlation(returns_wide: pd.DataFrame) -> Dict:
    corr = returns_wide.corr().round(4)
    return {"tickers": corr.columns.tolist(), "matrix": corr.values.tolist()}


# ================================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# ================================================================

def run_optimization(
    tickers: List[str],
    returns_wide: pd.DataFrame,
    latest_prices: Dict[str, float],
    budget: float,
    risk_free_rate: float = 0.02,
    methods: Optional[List[str]] = None,
    optimization_model: str = "all",
    allocation_limits: Optional[Dict[str, Dict[str, float]]] = None,
    max_assets: Optional[int] = None,
    knowledge_level: str = "beginner"
) -> Dict:
    """
    Главная функция оптимизации.

    Параметры:
        tickers: список тикеров
        returns_wide: DataFrame с месячными доходностями
        latest_prices: последние цены
        budget: бюджет в USD
        risk_free_rate: безрисковая ставка (годовая)
        methods: список методов (устаревший параметр, используйте optimization_model)
        optimization_model: 'max_sharpe'|'min_volatility'|'risk_parity'|'min_cvar'|
                           'monte_carlo'|'equal_weight'|'all'
        allocation_limits: {ticker: {min: 0.05, max: 0.30}}
        max_assets: максимальное количество активов в портфеле
        knowledge_level: 'beginner'|'professional' — влияет на доступные методы
    """
    global RISK_FREE_MONTHLY
    RISK_FREE_MONTHLY = risk_free_rate / 12

    # Определяем доступные тикеры
    available = [t for t in tickers if t in returns_wide.columns and t in latest_prices]
    if len(available) < 2:
        raise ValueError(f"Нужно минимум 2 тикера, доступно: {available}")

    # Валидация ограничений
    ok, err = validate_constraints(available, allocation_limits, max_assets)
    if not ok:
        raise ValueError(err)

    returns = returns_wide[available].dropna()
    mean_ret = returns.mean().values
    cov_mat = returns.cov().values
    prices = {t: latest_prices[t] for t in available}

    # Определяем какие модели запускать
    # Для beginner: только equal_weight + max_sharpe
    # Для professional: все методы
    if knowledge_level == "beginner":
        allowed_models = {"equal_weight", "max_sharpe"}
    else:
        allowed_models = {"max_sharpe", "min_volatility", "risk_parity", "min_cvar",
                          "monte_carlo", "equal_weight"}

    # Какие методы запускать
    if optimization_model == "all":
        models_to_run = allowed_models
    elif optimization_model in allowed_models:
        models_to_run = {optimization_model}
    else:
        # Если beginner запросил недоступную модель — используем max_sharpe
        models_to_run = {"max_sharpe"}

    common_kwargs = dict(
        tickers=available,
        prices=prices,
        mean_returns=mean_ret,
        cov_matrix=cov_mat,
        budget=budget,
        allocation_limits=allocation_limits,
        max_assets=max_assets
    )

    portfolios = []

    if "max_sharpe" in models_to_run:
        portfolios.append(max_sharpe_opt(
            **common_kwargs, risk_free=RISK_FREE_MONTHLY
        ).to_dict())

    if "min_volatility" in models_to_run:
        portfolios.append(min_volatility_opt(**common_kwargs).to_dict())

    if "risk_parity" in models_to_run:
        portfolios.append(risk_parity_opt(**common_kwargs).to_dict())

    if "min_cvar" in models_to_run:
        portfolios.append(min_cvar_opt(**common_kwargs).to_dict())

    if "monte_carlo" in models_to_run:
        # Для режима "all" уменьшаем итерации чтобы не тормозило
        n_iter = 3000 if optimization_model == "all" else MC_ITERATIONS
        portfolios.append(monte_carlo_opt(
            **common_kwargs, risk_free=RISK_FREE_MONTHLY, n_iter=n_iter
        ).to_dict())

    if "equal_weight" in models_to_run:
        portfolios.append(equal_weight_opt(
            tickers=available, prices=prices,
            mean_returns=mean_ret, cov_matrix=cov_mat,
            budget=budget, max_assets=max_assets
        ).to_dict())

    if not portfolios:
        raise ValueError("Не удалось запустить ни одного метода оптимизации")

    frontier = compute_efficient_frontier(mean_ret, cov_mat)
    stock_stats = analyze_stocks(returns, prices)
    correlation = compute_correlation(returns)

    # Ковариационная матрица (для продвинутых)
    cov_df = returns.cov().round(6)
    covariance = {
        "tickers": cov_df.columns.tolist(),
        "matrix": cov_df.values.tolist(),
    }

    best = max(portfolios, key=lambda p: p["metrics"]["sharpe"])

    return {
        "tickers_used": available,
        "portfolios": portfolios,
        "best_portfolio": best["name"],
        "efficient_frontier": frontier,
        "stock_stats": stock_stats,
        "correlation": correlation,
        "covariance": covariance,
    }


# ================================================================
# МЕТРИКИ ВВЕДЁННОГО ПОРТФЕЛЯ
# ================================================================

def analyze_input_portfolio(
    tickers: List[str],
    quantities: Dict[str, int],
    latest_prices: Dict[str, float],
    returns_wide: pd.DataFrame,
) -> Optional[Dict]:
    """
    Считает метрики портфеля введённого пользователем
    на основе указанных количеств акций.
    Возвращает None если данных недостаточно.
    """
    available = [t for t in tickers if t in returns_wide.columns and t in latest_prices and quantities.get(t, 0) > 0]
    if len(available) < 1:
        return None

    returns = returns_wide[available].dropna()
    mean_ret = returns.mean().values
    cov_mat = returns.cov().values
    prices_arr = np.array([latest_prices[t] for t in available])
    shares_arr = np.array([float(quantities.get(t, 0)) for t in available])

    budget = float(np.sum(shares_arr * prices_arr))
    if budget <= 0:
        return None

    weights = (shares_arr * prices_arr) / budget
    ret_rel = float(np.dot(weights, mean_ret))
    risk_rel = float(np.sqrt(max(float(weights @ cov_mat @ weights), 0)))
    sharpe = (ret_rel - RISK_FREE_MONTHLY) / risk_rel if risk_rel > 0 else 0.0
    payback = budget / (ret_rel * budget) if ret_rel > 0 else float("inf")

    return {
        "tickers": available,
        "shares": [int(quantities.get(t, 0)) for t in available],
        "weights": [round(float(w), 4) for w in weights],
        "metrics": {
            "budget": round(budget, 2),
            "monthly_profit": round(ret_rel * budget, 2),
            "monthly_risk": round(risk_rel * budget, 2),
            "sharpe": round(sharpe, 4),
            "payback_months": round(min(payback, 9999), 1),
            "return_pct": round(ret_rel * 100, 4),
        },
    }
