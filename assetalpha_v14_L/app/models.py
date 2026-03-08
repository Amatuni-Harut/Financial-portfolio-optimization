"""
app/models.py — Pydantic схемы (API-контракт).

Исправления v13.1:
- KnowledgeLevel перенесён из app.state в JWT-токен (поле в пользователе)
- OptimizeRequest: валидация бюджета, risk_free_rate
- AllocationLimit: валидатор min < max
- AssetInput: нормализация тикера в uppercase
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class KnowledgeLevel(str, Enum):
    beginner     = "beginner"
    professional = "professional"


class OptimizationModel(str, Enum):
    max_sharpe      = "max_sharpe"
    min_volatility  = "min_volatility"
    risk_parity     = "risk_parity"
    min_cvar        = "min_cvar"
    monte_carlo     = "monte_carlo"
    equal_weight    = "equal_weight"
    all             = "all"


# ─── Вспомогательные модели ───────────────────────────────────────────────────

class AllocationLimit(BaseModel):
    min: float = Field(default=0.0, ge=0.0, le=1.0)
    max: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def check_min_lt_max(self) -> "AllocationLimit":
        if self.min >= self.max:
            raise ValueError(f"min ({self.min}) должен быть меньше max ({self.max})")
        return self


class AssetInput(BaseModel):
    ticker:   str            = Field(..., min_length=1, max_length=10)
    weight:   Optional[float] = Field(default=None, ge=0.0, le=1.0)
    quantity: Optional[int]   = Field(default=None, ge=0)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()


# ─── Запросы / ответы оптимизации ─────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    assets:             List[AssetInput] = Field(..., min_length=2)
    budget:             float            = Field(..., ge=100.0, le=2000000000.0)
    risk_free_rate:     float            = Field(default=0.04, ge=0.0, le=0.3)
    optimization_model: OptimizationModel = Field(default=OptimizationModel.max_sharpe)
    knowledge_level:    KnowledgeLevel   = Field(default=KnowledgeLevel.beginner)
    allocation_limits:  Optional[Dict[str, AllocationLimit]] = None
    max_assets:         Optional[int]    = Field(default=None, ge=2, le=50)


# ─── Уровень пользователя ─────────────────────────────────────────────────────

class UserLevelRequest(BaseModel):
    level: KnowledgeLevel


class UserLevelResponse(BaseModel):
    level:   KnowledgeLevel
    message: str
