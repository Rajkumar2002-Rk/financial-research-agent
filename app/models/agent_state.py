from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator


class AgentState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    ticker: str
    tickers: List[str]
    session_id: str
    include_news: bool
    time_horizon: str                            # "short_term" | "long_term" | "default"

    # ── Raw data from tools ───────────────────────────────────────────────────
    raw_market_data: Optional[Dict[str, Any]]
    raw_news_data: Optional[List[Dict[str, Any]]]
    fundamental_data: Optional[Dict[str, Any]]   # from fundamental_tool
    news_articles: Optional[List[Dict[str, Any]]]  # validated

    # ── Validated data ────────────────────────────────────────────────────────
    validated_market_data: Optional[Dict[str, Any]]
    validated_news_data: Optional[List[Dict[str, Any]]]

    # ── Technical analysis ────────────────────────────────────────────────────
    technical_indicators: Optional[Dict[str, Any]]
    trend_direction: Optional[str]
    news_summary: Optional[str]

    # ── Scoring ───────────────────────────────────────────────────────────────
    news_analysis: Optional[Dict[str, Any]]        # classify_news_sentiment result
    tech_result: Optional[Dict[str, Any]]
    fund_result: Optional[Dict[str, Any]]
    sent_result: Optional[Dict[str, Any]]
    risk_result: Optional[Dict[str, Any]]
    time_horizon_weights: Optional[Dict[str, Any]]
    total_score: Optional[int]
    max_score: Optional[int]
    normalized_score: Optional[float]
    conflict_detected: bool
    confidence_result: Optional[Dict[str, Any]]

    # ── Final decision ────────────────────────────────────────────────────────
    recommendation: Optional[str]
    confidence_score: Optional[float]
    reasoning: Optional[str]
    risk_assessment: Optional[str]
    explanation_data: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]       # serialised AnalysisResponse

    # ── Metadata (reducers accumulate across parallel branches) ───────────────
    errors: Annotated[List[str], operator.add]
    tool_calls_log: Annotated[List[Dict[str, Any]], operator.add]
    current_step: str
    retry_count: int


def create_initial_state(
    ticker: str,
    session_id: str,
    include_news: bool = True,
    time_horizon: str = "default",
    tickers: Optional[List[str]] = None,
) -> AgentState:
    return AgentState(
        ticker=ticker,
        tickers=tickers or [ticker],
        session_id=session_id,
        include_news=include_news,
        time_horizon=time_horizon,
        raw_market_data=None,
        raw_news_data=None,
        fundamental_data=None,
        news_articles=None,
        validated_market_data=None,
        validated_news_data=None,
        technical_indicators=None,
        trend_direction=None,
        news_summary=None,
        news_analysis=None,
        tech_result=None,
        fund_result=None,
        sent_result=None,
        risk_result=None,
        time_horizon_weights=None,
        total_score=None,
        max_score=None,
        normalized_score=None,
        conflict_detected=False,
        confidence_result=None,
        recommendation=None,
        confidence_score=None,
        reasoning=None,
        risk_assessment=None,
        explanation_data=None,
        final_response=None,
        errors=[],
        tool_calls_log=[],
        current_step="initializing",
        retry_count=0,
    )
