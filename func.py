"""
Portfolio Analysis Library
Этапы 1–3: анализ акций, портфельная математика, целочисленное распределение
Использует scipy для матричных вычислений и оптимизации.
"""

import math
import numpy as np
from scipy import stats
from scipy.optimize import minimize


# ──────────────────────────────────────────────
# ЭТАП 1 — Анализ одной акции
# ──────────────────────────────────────────────

def calculate_returns(prices: list[float]) -> list[float]:
    """Дневные доходности из списка цен."""
    prices_arr = np.array(prices, dtype=float)
    returns = np.diff(prices_arr) / prices_arr[:-1]
    return returns.tolist()


def calculate_mean(values: list[float]) -> float:
    """Среднее значение (scipy/numpy)."""
    return float(np.mean(values))


def calculate_variance(values: list[float]) -> float:
    """Выборочная дисперсия (ddof=1)."""
    return float(np.var(values, ddof=1))


def calculate_volatility(values: list[float]) -> float:
    """Стандартное отклонение (выборочное)."""
    return float(np.std(values, ddof=1))


# ──────────────────────────────────────────────
# ЭТАП 2 — Портфельная математика
# ──────────────────────────────────────────────

def calculate_covariance(values1: list[float], values2: list[float]) -> float:
    """Ковариация двух активов (выборочная)."""
    cov_matrix = np.cov(values1, values2, ddof=1)
    return float(cov_matrix[0, 1])


def calculate_covariance_matrix(returns_matrix: list[list[float]]) -> list[list[float]]:
    """
    Матрица ковариации.
    returns_matrix: список строк [день × актив].
    """
    arr = np.array(returns_matrix, dtype=float)   # shape: (days, assets)
    cov = np.cov(arr.T, ddof=1)                   # shape: (assets, assets)
    return cov.tolist()


def calculate_correlation_matrix(returns_matrix: list[list[float]]) -> list[list[float]]:
    """Матрица корреляции (scipy.stats)."""
    arr = np.array(returns_matrix, dtype=float)   # (days, assets)
    corr = np.corrcoef(arr.T)                     # (assets, assets)
    return corr.tolist()


def portfolio_return(weights: list[float], mean_returns: list[float]) -> float:
    """Ожидаемая доходность портфеля."""
    return float(np.dot(weights, mean_returns))


def portfolio_volatility(weights: list[float], covariance_matrix: list[list[float]]) -> float:
    """Риск портфеля (стандартное отклонение)."""
    w = np.array(weights, dtype=float)
    cov = np.array(covariance_matrix, dtype=float)
    variance = w @ cov @ w
    return float(math.sqrt(variance))


def portfolio_sharpe_ratio(
    weights: list[float],
    mean_returns: list[float],
    covariance_matrix: list[list[float]],
    risk_free_rate: float,
) -> float:
    """Коэффициент Шарпа портфеля."""
    r = portfolio_return(weights, mean_returns)
    sigma = portfolio_volatility(weights, covariance_matrix)
    return (r - risk_free_rate) / sigma


# ──────────────────────────────────────────────
# ЭТАП 2 — Бонус: оптимизация весов через scipy
# ──────────────────────────────────────────────

def optimize_max_sharpe(
    mean_returns: list[float],
    covariance_matrix: list[list[float]],
    risk_free_rate: float = 0.0,
) -> dict:
    """
    Находит веса портфеля с максимальным коэффициентом Шарпа
    с помощью scipy.optimize.minimize.
    Возвращает dict с ключами 'weights', 'sharpe', 'return', 'volatility'.
    """
    n = len(mean_returns)

    def neg_sharpe(w):
        return -portfolio_sharpe_ratio(w, mean_returns, covariance_matrix, risk_free_rate)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = [(0, 1)] * n
    x0 = np.ones(n) / n

    result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    optimal_w = result.x.tolist()

    return {
        "weights": optimal_w,
        "sharpe": portfolio_sharpe_ratio(optimal_w, mean_returns, covariance_matrix, risk_free_rate),
        "return": portfolio_return(optimal_w, mean_returns),
        "volatility": portfolio_volatility(optimal_w, covariance_matrix),
    }


# ──────────────────────────────────────────────
# ЭТАП 3 — Целочисленное распределение
# ──────────────────────────────────────────────

def initial_integer_allocation(
    weights: list[float], prices: list[float], budget: float
) -> list[int]:
    """Начальное распределение: количество акций по идеальным весам."""
    w = np.array(weights, dtype=float)
    p = np.array(prices, dtype=float)
    ideal_money = w * budget
    shares = (ideal_money // p).astype(int)
    return shares.tolist()


def calculate_remaining_cash(
    shares: list[int], prices: list[float], budget: float
) -> float:
    """Остаток бюджета после покупки акций."""
    invested = float(np.dot(shares, prices))
    return budget - invested


def calculate_total_invested(shares: list[int], prices: list[float]) -> float:
    """Общая стоимость портфеля."""
    return float(np.dot(shares, prices))


def calculate_actual_weights(shares: list[int], prices: list[float]) -> list[float]:
    """Фактические веса портфеля."""
    total = calculate_total_invested(shares, prices)
    w = (np.array(shares, dtype=float) * np.array(prices, dtype=float)) / total
    return w.tolist()


def calculate_weight_error(
    actual_weights: list[float], ideal_weights: list[float]
) -> float:
    """Среднеквадратичная ошибка между фактическими и идеальными весами."""
    diff = np.array(actual_weights) - np.array(ideal_weights)
    return float(np.dot(diff, diff))


def greedy_improvement(
    shares: list[int],
    prices: list[float],
    ideal_weights: list[float],
    budget: float,
) -> list[int]:
    """
    Жадное улучшение: покупаем по одной акции, которая сильнее всего
    уменьшает ошибку весов, пока хватает остатка бюджета.
    """
    shares = list(shares)
    prices_arr = np.array(prices, dtype=float)
    ideal_arr = np.array(ideal_weights, dtype=float)
    remaining_cash = calculate_remaining_cash(shares, prices, budget)

    while remaining_cash >= prices_arr.min():
        best_error = None
        best_index = None

        for i, price in enumerate(prices_arr):
            if price <= remaining_cash:
                temp = shares[:]
                temp[i] += 1
                actual_w = np.array(calculate_actual_weights(temp, prices))
                error = float(np.dot(actual_w - ideal_arr, actual_w - ideal_arr))

                if best_error is None or error < best_error:
                    best_error = error
                    best_index = i

        if best_index is None:
            break

        shares[best_index] += 1
        remaining_cash -= prices_arr[best_index]

    return shares


# ──────────────────────────────────────────────
# Пример использования
# ──────────────────────────────────────────────

if __name__ == "__main__":
    prices_a = [100, 102, 101, 105, 107]
    prices_b = [50, 51, 49, 52, 54]

    ret_a = calculate_returns(prices_a)
    ret_b = calculate_returns(prices_b)

    print("Доходности A:", [round(r, 4) for r in ret_a])
    print("Среднее A:   ", round(calculate_mean(ret_a), 6))
    print("Волатильность A:", round(calculate_volatility(ret_a), 6))

    returns_matrix = [[a, b] for a, b in zip(ret_a, ret_b)]
    cov_m = calculate_covariance_matrix(returns_matrix)
    corr_m = calculate_correlation_matrix(returns_matrix)
    print("\nМатрица ковариации:", cov_m)
    print("Матрица корреляции:", corr_m)

    mean_returns = [calculate_mean(ret_a), calculate_mean(ret_b)]
    weights = [0.6, 0.4]
    print("\nДоходность портфеля:", round(portfolio_return(weights, mean_returns), 6))
    print("Риск портфеля:      ", round(portfolio_volatility(weights, cov_m), 6))
    print("Шарп (rf=0):        ", round(portfolio_sharpe_ratio(weights, mean_returns, cov_m, 0.0), 4))

    opt = optimize_max_sharpe(mean_returns, cov_m)
    print("\nОптимальные веса (max Sharpe):", [round(w, 4) for w in opt["weights"]])
    print("Sharpe:", round(opt["sharpe"], 4))

    budget = 10_000
    asset_prices = [107.0, 54.0]
    ideal_w = opt["weights"]
    shares = initial_integer_allocation(ideal_w, asset_prices, budget)
    shares = greedy_improvement(shares, asset_prices, ideal_w, budget)
    actual_w = calculate_actual_weights(shares, asset_prices)
    print("\nАкций:", shares)
    print("Фактические веса:", [round(w, 4) for w in actual_w])
    print("Остаток:", round(calculate_remaining_cash(shares, asset_prices, budget), 2))
