from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    session_id: Optional[str] = None
    include_news: bool = True
    time_horizon: str = Field(
        default="default",
        description="Investment horizon: 'short_term' (1–4 weeks), 'long_term' (1–5 years), or 'default' (balanced)",
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        ticker = v.strip().upper()
        if not re.match(r'^[A-Z]{1,5}([.\-][A-Z]{1,2})?$', ticker):
            raise ValueError(f"'{ticker}' is not a valid ticker symbol.")
        return ticker


class ComparisonRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=2, max_length=5)
    session_id: Optional[str] = None

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, v: List[str]) -> List[str]:
        seen = set()
        result = []
        for ticker in v:
            clean = ticker.strip().upper()
            if clean not in seen:
                seen.add(clean)
                result.append(clean)
        if len(result) < 2:
            raise ValueError("Need at least 2 unique tickers.")
        return result


class PortfolioHolding(BaseModel):
    ticker: str
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()


class PortfolioRequest(BaseModel):
    holdings: List[PortfolioHolding] = Field(..., min_length=1, max_length=20)
    session_id: Optional[str] = None


class BacktestRequest(BaseModel):
    ticker: str
    days: int = Field(default=90, ge=30, le=365)
    initial_investment: float = Field(default=10000.0, ge=100.0)
    session_id: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()