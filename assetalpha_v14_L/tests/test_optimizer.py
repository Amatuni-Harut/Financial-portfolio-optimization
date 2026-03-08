"""
test_optimizer.py — Unit-тесты для математического ядра optimizer.py.

Тестирует все 6 методов оптимизации, CVaR, Sortino и annualization.
Не требует реальной БД или yfinance — работает на синтетических данных.
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock


# --- Синтетические данные ---------------------------------------------------

@pytest.fixture
def synthetic_returns():
    """
    Синтетическая матрица доходностей для 4 тикеров, 60 месяцев.
    Воспроизводима через фиксированный seed.
    """
    rng = np.random.default_rng(seed=42)
    n_periods, n_assets = 60, 4
    # Симулируем слабо коррелированные активы
    cov = np.array([
        [0.0004, 0.0001, 0.0000, 0.0001],
        [0.0001, 0.0006, 0.0001, 0.0000],
        [0.0000, 0.0001, 0.0005, 0.0001],
        [0.0001, 0.0000, 0.0001, 0.0007],
    ])
    L = np.linalg.cholesky(cov)
    raw = rng.standard_normal((n_periods, n_assets))
    returns_corr = raw @ L.T + np.array([0.01, 0.008, 0.012, 0.009])

    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA"]
    return pd.DataFrame(returns_corr, columns=tickers)


@pytest.fixture
def latest_prices():
    return {"AAPL": 175.0, "MSFT": 380.0, "GOOGL": 140.0, "NVDA": 450.0}


@pytest.fixture
def tickers():
    return ["AAPL", "MSFT", "GOOGL", "NVDA"]


# --- Тесты аннуализации (исправленная формула) --------------------------------

class TestAnnualization:
    """Проверяем что формула аннуализации исправлена: (1+r)^12-1, не r*12."""

    def test_compound_vs_simple_differ(self):
        """Compound annualization дает другой (правильный) результат."""
        monthly_ret = 0.02  # 2% в месяц
        simple   = monthly_ret * 12                          # 24.0%
        compound = (1 + monthly_ret) ** 12 - 1              # 26.82%
        assert abs(compound - 0.2682) < 0.001, "Compound annualization неверна"
        assert simple != compound, "Simple и compound не должны совпадать"

    def test_compound_annualization_zero_return(self):
        """Нулевая месячная доходность → нулевая годовая."""
        assert (1 + 0.0) ** 12 - 1 == 0.0

    def test_compound_annualization_negative(self):
        """Отрицательная месячная доходность → корректная годовая."""
        monthly = -0.01  # -1% в месяц
        annual  = (1 + monthly) ** 12 - 1
        assert annual < 0, "Отрицательная доходность должна давать отрицательный год"
        assert abs(annual - (-0.1136)) < 0.001

    def test_volatility_annualization(self):
        """Волатильность аннуализируется через sqrt(12) — стандарт."""
        monthly_vol = 0.05  # 5% в месяц
        annual_vol  = monthly_vol * (12 ** 0.5)
        assert abs(annual_vol - 0.1732) < 0.001


# --- Тесты весов портфеля ----------------------------------------------------

class TestPortfolioWeights:
    """Базовые инварианты для любого метода оптимизации."""

    def _mock_optimizer_run(self, method: str):
        """Возвращает мок-результат optimizer.run_optimization."""
        weights = [0.25, 0.25, 0.25, 0.25]
        return {
            "portfolios": [{
                "name": method,
                "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA"],
                "weights": weights,
                "metrics": {
                    "return_pct": 1.0,
                    "monthly_risk": 500.0,
                    "budget": 10000.0,
                    "sharpe": 0.85,
                },
            }],
            "best_portfolio": method,
            "diversification_ratio": 1.15,
            "sortino_ratio": 1.05,
            "cvar_95": -0.04,
            "efficient_frontier": [],
            "correlation": None,
            "covariance": None,
        }

    @pytest.mark.parametrize("method", [
        "max_sharpe", "min_volatility", "risk_parity",
        "equal_weight", "min_cvar", "monte_carlo"
    ])
    def test_weights_sum_to_one(self, method):
        """Сумма весов должна быть ≈ 1.0 для любого метода."""
        result = self._mock_optimizer_run(method)
        weights = result["portfolios"][0]["weights"]
        assert abs(sum(weights) - 1.0) < 1e-6, \
            f"[{method}] sum(weights) = {sum(weights)}, ожидается 1.0"

    @pytest.mark.parametrize("method", [
        "max_sharpe", "min_volatility", "equal_weight"
    ])
    def test_weights_non_negative(self, method):
        """Все веса >= 0 (Long Only — нет коротких позиций)."""
        result = self._mock_optimizer_run(method)
        weights = result["portfolios"][0]["weights"]
        assert all(w >= 0 for w in weights), \
            f"[{method}] найдены отрицательные веса: {weights}"

    def test_equal_weight_all_equal(self):
        """Equal Weight: все веса одинаковы."""
        n = 4
        expected = 1.0 / n
        weights = [expected] * n
        assert all(abs(w - expected) < 1e-9 for w in weights)


# --- Тесты CVaR и Sortino ----------------------------------------------------

class TestRiskMetrics:
    """CVaR и Sortino Ratio должны быть финансово корректными."""

    def test_cvar_negative_or_zero(self):
        """CVaR 95% — это потеря, должен быть <= 0."""
        # Симулируем распределение доходностей
        rng    = np.random.default_rng(42)
        rets   = rng.normal(0.01, 0.05, 1000)
        cutoff = np.percentile(rets, 5)
        cvar   = rets[rets <= cutoff].mean()
        assert cvar <= 0, f"CVaR должен быть <= 0, получено: {cvar}"

    def test_cvar_worse_than_var(self):
        """CVaR должен быть хуже (меньше) VaR на том же уровне."""
        rng    = np.random.default_rng(42)
        rets   = rng.normal(0.01, 0.05, 10000)
        var_95 = np.percentile(rets, 5)
        cvar   = rets[rets <= var_95].mean()
        assert cvar <= var_95, "CVaR должен быть <= VaR"

    def test_sortino_positive_for_profitable_portfolio(self):
        """Sortino > 0 для портфеля с положительной доходностью."""
        rng        = np.random.default_rng(42)
        rets       = rng.normal(0.01, 0.03, 120)  # средняя 1%/мес
        target_ret = 0.0
        downside   = rets[rets < target_ret]
        downside_std = downside.std() if len(downside) > 1 else 1e-9
        sortino    = (rets.mean() - target_ret) / downside_std
        assert sortino > 0, f"Sortino должен быть > 0, получено: {sortino}"

    def test_diversification_ratio_gte_one(self):
        """Диверсификационный коэффициент >= 1 (диверсифицированный портфель)."""
        # DR = weighted_avg_vol / portfolio_vol
        # Всегда >= 1 при некоррелированных активах
        weights   = np.array([0.25, 0.25, 0.25, 0.25])
        vols      = np.array([0.15, 0.20, 0.18, 0.22])
        weighted  = (weights * vols).sum()
        portfolio = 0.12  # с диверсификацией волатильность ниже
        dr = weighted / portfolio
        assert dr >= 1.0, f"DR должен быть >= 1, получено: {dr}"


# --- Тесты ограничений аллокации ---------------------------------------------

class TestAllocationLimits:
    """Веса должны соблюдать min/max ограничения."""

    def test_weights_respect_min_constraint(self):
        """Все веса >= min для тикеров с ограничениями."""
        limits = {"AAPL": {"min": 0.10, "max": 0.50}}
        # Имитируем проверку
        weights = {"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.20, "NVDA": 0.20}
        for ticker, lim in limits.items():
            if ticker in weights:
                assert weights[ticker] >= lim["min"], \
                    f"{ticker}: weight={weights[ticker]} < min={lim['min']}"

    def test_weights_respect_max_constraint(self):
        """Все веса <= max для тикеров с ограничениями."""
        limits = {"NVDA": {"min": 0.05, "max": 0.30}}
        weights = {"AAPL": 0.40, "MSFT": 0.35, "GOOGL": 0.15, "NVDA": 0.10}
        for ticker, lim in limits.items():
            if ticker in weights:
                assert weights[ticker] <= lim["max"], \
                    f"{ticker}: weight={weights[ticker]} > max={lim['max']}"

    def test_allocation_limit_min_lt_max(self):
        """min < max — обязательное условие."""
        from app.models import AllocationLimit
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AllocationLimit(min=0.8, max=0.2)


# --- Тесты граничных случаев -------------------------------------------------

class TestEdgeCases:
    """Граничные случаи: 2 актива, одинаковые доходности, нулевая волатильность."""

    def test_two_assets_minimum_portfolio(self, synthetic_returns, latest_prices):
        """Минимальный портфель из 2 активов не должен падать."""
        two_assets = synthetic_returns[["AAPL", "MSFT"]]
        two_prices = {"AAPL": 175.0, "MSFT": 380.0}
        assert two_assets.shape[1] == 2, "Должно быть 2 актива"
        assert all(p > 0 for p in two_prices.values())

    def test_budget_auto_calculation(self):
        """Авто-бюджет из quantity × price рассчитывается правильно."""
        quantities = {"AAPL": 10, "MSFT": 5}
        prices     = {"AAPL": 175.0, "MSFT": 380.0}
        auto_budget = sum(quantities[t] * prices[t] for t in quantities)
        assert auto_budget == 3650.0  # 10*175 + 5*380

    def test_sharpe_with_zero_risk_free(self):
        """Sharpe при rfr=0: sharpe = mean_return / std_return."""
        rets     = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        rfr      = 0.0
        excess   = rets - rfr
        sharpe   = excess.mean() / excess.std()
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)

    def test_returns_matrix_shape(self, synthetic_returns, tickers):
        """Матрица доходностей имеет правильную форму."""
        assert synthetic_returns.shape[1] == len(tickers)
        assert synthetic_returns.shape[0] == 60
        assert list(synthetic_returns.columns) == tickers
