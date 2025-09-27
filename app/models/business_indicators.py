from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class IndicatorType(str, Enum):
    REVENUE = "revenue"
    USERS = "users"
    PERFORMANCE = "performance"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"

class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"

class IndicatorStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

class IndicatorColor(str, Enum): 
  GREEN = 'green'
  RED = 'red'
  BLUE = 'blue'
  YELLOW = 'yellow'
  PURPLE = 'purple'
  GRAY = 'gray'


# Modelos de respuesta

class BusinessIndicator(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    value: float
    unit: Optional[str] = None
    type: IndicatorType
    color: Optional[IndicatorColor] = None
    trend_direction: TrendDirection
    trend_percentage: Optional[float] = None
    status: IndicatorStatus
    target_value: Optional[float] = None
    last_updated: datetime
    metadata: Optional[Dict[str, Any]] = None

class IndicatorHistory(BaseModel):
    date: datetime
    value: float
    metadata: Optional[Dict[str, Any]] = None

class BusinessIndicatorWithHistory(BusinessIndicator):
    history: List[IndicatorHistory] = []

# Modelos de request
class BusinessIndicatorsRequest(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    period: Optional[str] = "daily"  # daily, weekly, monthly
    include_history: bool = False
    indicator_types: Optional[List[IndicatorType]] = None

class BusinessIndicatorsResponse(BaseModel):
    indicators: List[BusinessIndicator]
    total_count: int
    metadata: Optional[Dict[str, Any]] = None
    last_updated: datetime

# Modelos para health check
class IndicatorsHealth(BaseModel):
    status: str = Field(..., description="healthy, degraded, down")
    last_update: datetime
    issues: List[str] = []
    total_indicators: int
    healthy_indicators: int
    warning_indicators: int
    critical_indicators: int