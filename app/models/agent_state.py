from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator


class AgentState(TypedDict):
    # Input
    ticker: str
    tickers: List[str]
    session_id: str
    include_news: bool

    # Raw data from tools
    raw_market_data: Optional[Dict[str, Any]]
    raw_news_data: Optional[List[Dict[str, Any]]]

    # Validated data
    validated_market_data: Optional[Dict[str, Any]]
    validated_news_data: Optional[List[Dict[str, Any]]]

    # Analysis results
    technical_indicators: Optional[Dict[str, Any]]
    trend_direction: Optional[str]
    news_summary: Optional[str]

    # Final decision
    recommendation: Optional[str]
    confidence_score: Optional[float]
    reasoning: Optional[str]
    risk_assessment: Optional[str]

    # Metadata
    errors: Annotated[List[str], operator.add]
    tool_calls_log: Annotated[List[Dict[str, Any]], operator.add]
    current_step: str
    retry_count: int


def create_initial_state(
    ticker: str,
    session_id: str,
    include_news: bool = True,
    tickers: Optional[List[str]] = None,
) -> AgentState:
    return AgentState(
        ticker=ticker,
        tickers=tickers or [ticker],
        session_id=session_id,
        include_news=include_news,
        raw_market_data=None,
        raw_news_data=None,
        validated_market_data=None,
        validated_news_data=None,
        technical_indicators=None,
        trend_direction=None,
        news_summary=None,
        recommendation=None,
        confidence_score=None,
        reasoning=None,
        risk_assessment=None,
        errors=[],
        tool_calls_log=[],
        current_step="initializing",
        retry_count=0,
    )