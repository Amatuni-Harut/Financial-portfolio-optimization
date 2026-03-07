"""
test_models.py — Юнит-тесты Pydantic моделей (валидация данных).
"""
import pytest
from pydantic import ValidationError

from app.models import (
    AllocationLimit,
    AssetInput,
    OptimizeRequest,
    OptimizationModel,
    KnowledgeLevel,
)


# ─── AllocationLimit ─────────────────────────────────────────────────────────

class TestAllocationLimit:
    def test_default_values(self):
        limit = AllocationLimit()
        assert limit.min == 0.0
        assert limit.max == 1.0

    def test_valid_limit(self):
        limit = AllocationLimit(min=0.1, max=0.5)
        assert limit.min == 0.1
        assert limit.max == 0.5

    def test_max_less_than_min_raises(self):
        with pytest.raises(ValidationError):
            AllocationLimit(min=0.8, max=0.2)

    def test_boundary_values(self):
        limit = AllocationLimit(min=0.0, max=1.0)
        assert limit.min == 0.0
        assert limit.max == 1.0

    def test_min_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AllocationLimit(min=-0.1, max=1.0)

    def test_max_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AllocationLimit(min=0.0, max=1.5)


# ─── AssetInput ──────────────────────────────────────────────────────────────

class TestAssetInput:
    def test_ticker_normalized_to_uppercase(self):
        asset = AssetInput(ticker="  aapl  ")
        assert asset.ticker == "AAPL"

    def test_optional_weight_and_quantity(self):
        asset = AssetInput(ticker="AAPL")
        assert asset.weight is None
        assert asset.quantity is None

    def test_with_weight(self):
        asset = AssetInput(ticker="AAPL", weight=0.25)
        assert asset.weight == 0.25

    def test_with_quantity(self):
        asset = AssetInput(ticker="AAPL", quantity=10)
        assert asset.quantity == 10

    def test_negative_quantity_raises(self):
        with pytest.raises(ValidationError):
            AssetInput(ticker="AAPL", quantity=-1)

    def test_weight_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AssetInput(ticker="AAPL", weight=1.5)


# ─── OptimizeRequest ─────────────────────────────────────────────────────────

class TestOptimizeRequest:
    def _make_request(self, **kwargs):
        defaults = dict(
            assets=[AssetInput(ticker="AAPL"), AssetInput(ticker="GOOGL")],
            budget=10000.0,
        )
        defaults.update(kwargs)
        return OptimizeRequest(**defaults)

    def test_valid_request(self):
        req = self._make_request()
        assert len(req.assets) == 2
        assert req.budget == 10000.0

    def test_default_optimization_model(self):
        req = self._make_request()
        assert req.optimization_model == OptimizationModel.max_sharpe

    def test_default_knowledge_level(self):
        req = self._make_request()
        assert req.knowledge_level == KnowledgeLevel.beginner

    def test_single_asset_raises(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(
                assets=[AssetInput(ticker="AAPL")],
                budget=10000.0,
            )

    def test_empty_assets_raises(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(assets=[], budget=10000.0)

    def test_budget_too_small_raises(self):
        with pytest.raises(ValidationError):
            self._make_request(budget=50.0)

    def test_budget_too_large_raises(self):
        with pytest.raises(ValidationError):
            self._make_request(budget=1_000_000_000.0)

    def test_risk_free_rate_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            self._make_request(risk_free_rate=0.5)

    def test_all_optimization_models_valid(self):
        for model in OptimizationModel:
            req = self._make_request(optimization_model=model)
            assert req.optimization_model == model

    def test_all_knowledge_levels_valid(self):
        for level in KnowledgeLevel:
            req = self._make_request(knowledge_level=level)
            assert req.knowledge_level == level


# ─── Enum тесты ──────────────────────────────────────────────────────────────

class TestEnums:
    def test_optimization_model_values(self):
        expected = {"max_sharpe", "min_volatility", "risk_parity", "min_cvar",
                    "monte_carlo", "equal_weight", "all"}
        assert {m.value for m in OptimizationModel} == expected

    def test_knowledge_level_values(self):
        assert set(KnowledgeLevel) == {KnowledgeLevel.beginner, KnowledgeLevel.professional}
