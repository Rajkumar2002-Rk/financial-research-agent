from app.tools.yfinance_tool import fetch_stock_data
from app.tools.tavily_tool import fetch_company_news
from app.services.validation_service import validate_market_data, validate_news_data
from app.agents.analysis_agent import calculate_indicators
from app.agents.decision_agent import make_decision
from app.models.responses import (
    AnalysisResponse, TechnicalIndicators, TrendDirection, Recommendation
)
from app.utils.logger import get_logger
import uuid
from app.guardrails.financial_guardrails import apply_guardrails

logger = get_logger(__name__)


async def run_analysis(
    ticker: str,
    session_id: str,
    include_news: bool = True,
    settings=None,
) -> AnalysisResponse:

    logger.info("orchestrator_started", ticker=ticker, session_id=session_id)

    market_data = fetch_stock_data(ticker)
    validated_market = validate_market_data(market_data, session_id)

    news_articles = []
    if include_news:
        raw_news = fetch_company_news(ticker, market_data.get("company_name", ticker))
        news_articles = validate_news_data(raw_news, session_id)

    analysis_result = calculate_indicators(validated_market, session_id)
    indicators = analysis_result.get("indicators", {})
    trend = analysis_result.get("trend", "Neutral")

    decision = make_decision(
        ticker=ticker,
        market_data=validated_market,
        indicators=indicators,
        news_articles=news_articles,
        session_id=session_id,
    )

    technical = TechnicalIndicators(
        ma_50=indicators.get("ma_50"),
        ma_200=indicators.get("ma_200"),
        rsi=indicators.get("rsi"),
        volatility_30d=indicators.get("volatility_30d"),
        price_change_pct=indicators.get("price_change_pct"),
        volume_avg_30d=indicators.get("volume_avg_30d"),
        golden_cross=indicators.get("golden_cross"),
        death_cross=indicators.get("death_cross"),
    )

    recommendation_map = {
        "BUY": Recommendation.BUY,
        "SELL": Recommendation.SELL,
        "HOLD": Recommendation.HOLD,
    }
    recommendation = recommendation_map.get(
        decision.get("recommendation", "").upper(),
        Recommendation.INSUFFICIENT_DATA
    )

    trend_map = {
        "Bullish": TrendDirection.BULLISH,
        "Bearish": TrendDirection.BEARISH,
        "Volatile": TrendDirection.VOLATILE,
    }
    trend_direction = trend_map.get(trend, TrendDirection.NEUTRAL)

    response = AnalysisResponse(
        ticker=ticker,
        company_name=validated_market.get("company_name", ticker),
        current_price=validated_market.get("current_price"),
        currency=validated_market.get("currency", "USD"),
        price_history=validated_market.get("price_history", []),
        trend_analysis=trend_direction,
        technical_indicators=technical,
        news_summary=decision.get("news_summary", ""),
        risk_assessment=decision.get("risk_assessment", ""),
        recommendation=recommendation,
        confidence_score=float(decision.get("confidence_score", 0.0)),
        reasoning=decision.get("reasoning", ""),
        session_id=session_id,
        cached=False,
    )

    response = apply_guardrails(response, session_id)
    logger.info("orchestrator_completed", ticker=ticker, recommendation=response.recommendation)
    return response