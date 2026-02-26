from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class OptimizeRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=2, max_length=20)
    budget: float = Field(..., gt=100, le=100_000_000)
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=0.20)
    methods: List[str] = Field(default=["monte_carlo", "greedy", "equal_weight"])
    period: str = Field(default="5y")

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, v):
        return [t.strip().upper() for t in v if t.strip()]

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, v):
        valid = {"monte_carlo", "greedy", "equal_weight"}
        for m in v:
            if m not in valid:
                raise ValueError(f"Unknown method '{m}'. Valid: {valid}")
        return v


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


class StockStatSchema(BaseModel):
    ticker: str
    price: float
    mean_ret_pct: float
    std_ret_pct: float
    abs_profit: float
    abs_risk: float
    sharpe: float


class CorrelationSchema(BaseModel):
    tickers: List[str]
    matrix: List[List[float]]


class OptimizeResponse(BaseModel):
    tickers_used: List[str]
    portfolios: List[PortfolioResultSchema]
    best_portfolio: str
    efficient_frontier: List[Dict[str, Any]]
    stock_stats: List[StockStatSchema]
    correlation: CorrelationSchema


class AssetListResponse(BaseModel):
    tickers: List[str]
    count: int


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str = "1.0.0"
