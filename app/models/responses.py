from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Recommendation(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrendDirection(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"
    VOLATILE = "Volatile"


class TechnicalIndicators(BaseModel):
    ma_50: Optional[float] = None
    ma_200: Optional[float] = None
    rsi: Optional[float] = Field(None, ge=0, le=100)
    volatility_30d: Optional[float] = None
    price_change_pct: Optional[float] = None
    volume_avg_30d: Optional[float] = None
    golden_cross: Optional[bool] = None
    death_cross: Optional[bool] = None


class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str = "Unknown"
    current_price: Optional[float] = None
    currency: str = "USD"
    price_history: List[Dict[str, Any]] = []
    trend_analysis: TrendDirection = TrendDirection.NEUTRAL
    technical_indicators: TechnicalIndicators = TechnicalIndicators()
    news_summary: str = ""
    risk_assessment: str = ""
    recommendation: Recommendation = Recommendation.INSUFFICIENT_DATA
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    session_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    cached: bool = False
    # Deterministic scoring fields
    total_score: Optional[int] = None
    technical_score: Optional[int] = None
    fundamental_score: Optional[int] = None
    sentiment_score: Optional[int] = None
    risk_penalty: Optional[int] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    confidence_breakdown: Optional[Dict[str, Any]] = None
    key_factors: Optional[List[str]] = None
    data_gaps: Optional[List[str]] = None
    fundamental_data: Optional[Dict[str, Any]] = None


class CompanyRanking(BaseModel):
    rank: int
    ticker: str
    recommendation: Recommendation
    confidence_score: float
    summary: str


class ComparisonResponse(BaseModel):
    tickers: List[str]
    analyses: List[AnalysisResponse]
    rankings: List[CompanyRanking]
    comparative_insights: str
    session_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)


class PortfolioResponse(BaseModel):
    holdings: List[str]
    individual_analyses: List[AnalysisResponse]
    portfolio_trend: TrendDirection
    diversification_score: float = Field(ge=0.0, le=1.0)
    sector_exposure: List[Dict[str, Any]]
    correlation_risk: str
    overall_health: str
    key_risks: List[str]
    recommendations: List[str]
    session_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)


class BacktestDataPoint(BaseModel):
    date: str
    portfolio_value: float
    recommendation_at_date: Recommendation
    actual_price: float


class BacktestResponse(BaseModel):
    ticker: str
    period_days: int
    initial_investment: float
    final_value: float
    total_return_pct: float
    buy_and_hold_return_pct: float
    alpha: float
    timeline: List[BacktestDataPoint]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float = Field(ge=0.0, le=1.0)
    narrative: str
    session_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)