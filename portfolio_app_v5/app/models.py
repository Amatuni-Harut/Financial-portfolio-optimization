"""
models.py — Pydantic схемы для всего API.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum


# ================================================================
# ENUMS
# ================================================================

class OptimizationModel(str, Enum):
    max_sharpe = "max_sharpe"
    min_volatility = "min_volatility"
    risk_parity = "risk_parity"
    min_cvar = "min_cvar"
    monte_carlo = "monte_carlo"
    equal_weight = "equal_weight"
    all = "all"


class KnowledgeLevel(str, Enum):
    beginner = "beginner"
    professional = "professional"


# ================================================================
# ЗАПРОС ОПТИМИЗАЦИИ
# ================================================================

class AllocationLimit(BaseModel):
    """Ограничения на долю одного актива в портфеле."""
    min: float = Field(default=0.0, ge=0.0, le=1.0, description="Минимальная доля (0..1)")
    max: float = Field(default=1.0, ge=0.0, le=1.0, description="Максимальная доля (0..1)")

    @field_validator("max")
    @classmethod
    def max_gte_min(cls, v, info):
        if "min" in info.data and v < info.data["min"]:
            raise ValueError("max должен быть >= min")
        return v


class AssetInput(BaseModel):
    ticker: str
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    quantity: Optional[int] = Field(default=None, ge=0, description="Количество акций")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v):
        return v.strip().upper()


class OptimizeRequest(BaseModel):
    assets: List[AssetInput] = Field(..., min_length=2)
    budget: float = Field(default=10000.0, ge=100, le=999_999_999,
                          description="Бюджет в USD")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    optimization_model: OptimizationModel = Field(
        default=OptimizationModel.max_sharpe,
        description="Модель оптимизации"
    )
    risk_free_rate: float = Field(
        default=0.02, ge=0.0, le=0.20,
        description="Годовая безрисковая ставка (доля, не %)"
    )
    max_assets: Optional[int] = Field(
        default=None, ge=2,
        description="Максимальное количество активов в портфеле"
    )
    allocation_limits: Optional[Dict[str, AllocationLimit]] = Field(
        default=None,
        description="Ограничения по долям: {AAPL: {min: 0.05, max: 0.30}}"
    )
    manual_weights: bool = Field(
        default=False,
        description="Ручные веса (только для professional)"
    )
    knowledge_level: KnowledgeLevel = Field(
        default=KnowledgeLevel.beginner,
        description="Уровень знаний пользователя"
    )

    @field_validator("assets")
    @classmethod
    def check_min_assets(cls, v):
        if len(v) < 2:
            raise ValueError("Нужно минимум 2 актива")
        return v


# ================================================================
# ОТВЕТ ОПТИМИЗАЦИИ
# ================================================================

class PortfolioMetricsSchema(BaseModel):
    budget: float
    monthly_profit: float
    monthly_risk: float
    sharpe: float
    payback_months: float
    return_pct: float


class PortfolioResultSchema(BaseModel):
    name: str
    metrics: PortfolioMetricsSchema
    tickers: List[str]
    shares: List[int]
    weights: List[float]


class OptimizeResponse(BaseModel):
    optimized_weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    metrics: Dict[str, float]
    efficient_frontier: List[Dict[str, Any]]
    all_portfolios: Optional[List[PortfolioResultSchema]] = None


# ================================================================
# ДЕТАЛИ АКТИВА (для модального окна скринера)
# ================================================================

class PricePoint(BaseModel):
    date: str
    price: float


class AssetDetailsResponse(BaseModel):
    ticker: str
    name: str
    price: str
    change: str
    max_price: str
    mean_return: str
    risk: str
    sharpe: float
    history: List[PricePoint]


# ================================================================
# РЫНОК
# ================================================================

class MarketItem(BaseModel):
    symbol: str
    name: str
    price: str
    change: float
    marketCap: str
    sharpe: float


class MarketResponse(BaseModel):
    data: List[MarketItem]
    count: int


# ================================================================
# УРОВЕНЬ ЗНАНИЙ
# ================================================================

class UserLevelRequest(BaseModel):
    level: KnowledgeLevel


class UserLevelResponse(BaseModel):
    level: KnowledgeLevel
    message: str


# ================================================================
# СИСТЕМНЫЕ
# ================================================================

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str = "2.0.0"


class SearchResultItem(BaseModel):
    ticker: str
    name: str
    sector: str
