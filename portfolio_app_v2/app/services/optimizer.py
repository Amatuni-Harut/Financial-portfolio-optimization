import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import List, Dict

RISK_FREE_ANNUAL = 0.02
RISK_FREE_MONTHLY = RISK_FREE_ANNUAL / 12
MC_ITERATIONS = 10_000
MC_SEED = 42


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


def _portfolio_performance(weights, mean_returns, cov_matrix):
    port_return = float(np.dot(weights, mean_returns))
    port_std = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
    sharpe = (port_return - RISK_FREE_MONTHLY) / port_std if port_std > 0 else 0.0
    return port_return, port_std, sharpe


def _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix):
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


def _fill_budget(shares, tickers, prices, mean_returns, cov_matrix, target):
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


def monte_carlo_opt(tickers, prices, mean_returns, cov_matrix, target_budget):
    np.random.seed(MC_SEED)
    best_sharpe, best_w = -np.inf, None
    for _ in range(MC_ITERATIONS):
        w = np.random.dirichlet(np.ones(len(tickers)))
        _, _, sh = _portfolio_performance(w, mean_returns, cov_matrix)
        if sh > best_sharpe:
            best_sharpe, best_w = sh, w
    p = np.array([prices[t] for t in tickers])
    shares = np.floor(best_w * target_budget / p)
    shares = _fill_budget(shares, tickers, prices, mean_returns, cov_matrix, target_budget)
    metrics = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix)
    budget = metrics.budget
    weights = [(int(shares[i]) * p[i]) / budget if budget > 0 else 0 for i in range(len(tickers))]
    return PortfolioResult("Monte Carlo", metrics, tickers, [int(s) for s in shares], weights)


def greedy_opt(tickers, prices, mean_returns, cov_matrix, target_budget):
    p = np.array([prices[t] for t in tickers])
    shares = np.zeros(len(tickers))
    for _ in range(100_000):
        remaining = target_budget - float(np.sum(shares * p))
        if remaining < p.min():
            break
        best_sh, best_i = -np.inf, -1
        for i in range(len(tickers)):
            if p[i] > remaining:
                continue
            test = shares.copy()
            test[i] += 1
            total = float(np.sum(test * p))
            w = (test * p) / total
            _, _, sh = _portfolio_performance(w, mean_returns, cov_matrix)
            if sh > best_sh:
                best_sh, best_i = sh, i
        if best_i == -1:
            break
        shares[best_i] += 1
    metrics = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix)
    budget = metrics.budget
    weights = [(int(shares[i]) * p[i]) / budget if budget > 0 else 0 for i in range(len(tickers))]
    return PortfolioResult("Greedy", metrics, tickers, [int(s) for s in shares], weights)


def equal_weight_opt(tickers, prices, mean_returns, cov_matrix, target_budget):
    p = np.array([prices[t] for t in tickers])
    target_per = target_budget / len(tickers)
    shares = np.floor(target_per / p)
    shares = _fill_budget(shares, tickers, prices, mean_returns, cov_matrix, target_budget)
    metrics = _calc_metrics(shares, tickers, prices, mean_returns, cov_matrix)
    budget = metrics.budget
    weights = [(int(shares[i]) * p[i]) / budget if budget > 0 else 0 for i in range(len(tickers))]
    return PortfolioResult("Equal Weight", metrics, tickers, [int(s) for s in shares], weights)


def compute_efficient_frontier(mean_returns, cov_matrix, n_portfolios=2000):
    np.random.seed(0)
    n = len(mean_returns)
    results = []
    for _ in range(n_portfolios):
        w = np.random.dirichlet(np.ones(n))
        ret, std, sh = _portfolio_performance(w, mean_returns, cov_matrix)
        results.append({"return": round(ret * 100, 4), "risk": round(std * 100, 4), "sharpe": round(sh, 4)})
    return results


def analyze_stocks(returns_wide, latest_prices):
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


def compute_correlation(returns_wide):
    corr = returns_wide.corr().round(4)
    return {"tickers": corr.columns.tolist(), "matrix": corr.values.tolist()}


def run_optimization(tickers, returns_wide, latest_prices, budget,
                     risk_free_rate=0.02, methods=None):
    global RISK_FREE_MONTHLY
    RISK_FREE_MONTHLY = risk_free_rate / 12

    if methods is None:
        methods = ["monte_carlo", "greedy", "equal_weight"]

    available = [t for t in tickers if t in returns_wide.columns and t in latest_prices]
    if len(available) < 2:
        raise ValueError(f"Нужно минимум 2 тикера, доступно: {available}")

    returns = returns_wide[available].dropna()
    mean_ret = returns.mean().values
    cov_mat = returns.cov().values
    prices = {t: latest_prices[t] for t in available}

    portfolios = []
    if "monte_carlo" in methods:
        portfolios.append(monte_carlo_opt(available, prices, mean_ret, cov_mat, budget).to_dict())
    if "greedy" in methods:
        portfolios.append(greedy_opt(available, prices, mean_ret, cov_mat, budget).to_dict())
    if "equal_weight" in methods:
        portfolios.append(equal_weight_opt(available, prices, mean_ret, cov_mat, budget).to_dict())

    frontier = compute_efficient_frontier(mean_ret, cov_mat)
    stock_stats = analyze_stocks(returns, prices)
    correlation = compute_correlation(returns)
    best = max(portfolios, key=lambda p: p["metrics"]["sharpe"])

    return {
        "tickers_used": available,
        "portfolios": portfolios,
        "best_portfolio": best["name"],
        "efficient_frontier": frontier,
        "stock_stats": stock_stats,
        "correlation": correlation,
    }
