from app.tools.yfinance_tool import fetch_stock_data
from app.tools.tavily_tool import fetch_company_news
from app.tools.fundamental_tool import fetch_fundamental_data
from app.services.validation_service import validate_market_data, validate_news_data
from app.agents.analysis_agent import calculate_indicators
from app.agents.decision_agent import classify_news_sentiment, generate_explanation
from app.agents.scoring_engine import (
    compute_technical_score,
    compute_fundamental_score,
    compute_sentiment_score,
    compute_risk_penalty,
    compute_confidence,
    make_deterministic_decision,
)
from app.models.responses import (
    AnalysisResponse, TechnicalIndicators, TrendDirection, Recommendation
)
from app.guardrails.financial_guardrails import apply_guardrails
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_analysis(
    ticker: str,
    session_id: str,
    include_news: bool = True,
    settings=None,
) -> AnalysisResponse:

    logger.info("orchestrator_started", ticker=ticker, session_id=session_id)

    # ── Step 1: Fetch market data ─────────────────────────────────────────────
    logger.info("step_1_market_data", ticker=ticker)
    market_data = fetch_stock_data(ticker)
    validated_market = validate_market_data(market_data, session_id)

    # ── Step 2: Fetch fundamental data ────────────────────────────────────────
    logger.info("step_2_fundamental_data", ticker=ticker)
    fundamentals = fetch_fundamental_data(ticker)
    if not fundamentals.get("data_available"):
        logger.warning("fundamental_data_unavailable", ticker=ticker,
                       missing=fundamentals.get("missing_fields", []))

    # ── Step 3: Fetch news ────────────────────────────────────────────────────
    logger.info("step_3_news", ticker=ticker)
    news_articles = []
    if include_news:
        raw_news = fetch_company_news(ticker, market_data.get("company_name", ticker))
        news_articles = validate_news_data(raw_news, session_id)

    # ── Step 4: Compute technical indicators ─────────────────────────────────
    logger.info("step_4_indicators", ticker=ticker)
    analysis_result = calculate_indicators(validated_market, session_id)
    indicators = analysis_result.get("indicators", {})
    trend = analysis_result.get("trend", "Neutral")

    # ── Step 5: Compute scores ────────────────────────────────────────────────
    logger.info("step_5_scoring", ticker=ticker)

    # 5a — LLM classifies news sentiment only (no decision-making)
    news_analysis = classify_news_sentiment(news_articles, ticker)
    news_sentiment = news_analysis.get("sentiment", "neutral")

    # 5b — Deterministic scoring
    tech_score   = compute_technical_score(indicators)
    fund_score   = compute_fundamental_score(fundamentals)
    sent_score   = compute_sentiment_score(news_sentiment)
    risk         = compute_risk_penalty(indicators, news_sentiment)

    total_score = (
        tech_score["score"]
        + fund_score["score"]
        + sent_score["score"]
        + risk["penalty"]
    )

    # 5c — Confidence (no guessing — based on data completeness + signal agreement)
    confidence_result = compute_confidence(
        fundamental_available=fundamentals.get("data_available", False),
        fundamental_missing_count=len(fundamentals.get("missing_fields", [])),
        technical_score=tech_score["score"],
        fundamental_score=fund_score["score"],
        sentiment_score=sent_score["score"],
        news_sentiment=news_sentiment,
        volatility=indicators.get("volatility_30d"),
    )
    confidence = confidence_result["confidence"]

    logger.info("scores_computed", ticker=ticker,
                total=total_score, technical=tech_score["score"],
                fundamental=fund_score["score"], sentiment=sent_score["score"],
                risk_penalty=risk["penalty"], confidence=confidence)

    # ── Step 6: Deterministic decision ───────────────────────────────────────
    logger.info("step_6_decision", ticker=ticker)
    decision_str = make_deterministic_decision(total_score, confidence)

    # ── Step 7: LLM generates explanation (cannot override decision) ─────────
    logger.info("step_7_explanation", ticker=ticker)
    explanation_data = generate_explanation(
        ticker=ticker,
        decision=decision_str,
        total_score=total_score,
        confidence=confidence,
        technical=tech_score,
        fundamental=fund_score,
        sentiment=sent_score,
        risk=risk,
        fundamentals_raw=fundamentals,
    )

    # ── Build response ────────────────────────────────────────────────────────
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
        "INSUFFICIENT_DATA": Recommendation.INSUFFICIENT_DATA,
    }
    recommendation = recommendation_map.get(decision_str, Recommendation.INSUFFICIENT_DATA)

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
        news_summary=news_analysis.get("summary", ""),
        risk_assessment=explanation_data.get("risk_assessment", ""),
        recommendation=recommendation,
        confidence_score=round(confidence / 100, 2),
        reasoning=explanation_data.get("reasoning", ""),
        session_id=session_id,
        cached=False,
        # Score breakdown
        total_score=total_score,
        technical_score=tech_score["score"],
        fundamental_score=fund_score["score"],
        sentiment_score=sent_score["score"],
        risk_penalty=risk["penalty"],
        score_breakdown={
            "technical": tech_score,
            "fundamental": fund_score,
            "sentiment": {"score": sent_score["score"], "max": 15, "reason": sent_score["reason"]},
            "risk": risk,
        },
        confidence_breakdown=confidence_result["breakdown"],
        key_factors=explanation_data.get("key_factors", []),
        data_gaps=fundamentals.get("missing_fields", []),
        fundamental_data={
            "pe_ratio": fundamentals.get("pe_ratio"),
            "eps": fundamentals.get("eps"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "profit_margin": fundamentals.get("profit_margin"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "free_cash_flow": fundamentals.get("free_cash_flow"),
            "market_cap": fundamentals.get("market_cap"),
        },
    )

    response = apply_guardrails(response, session_id)
    logger.info("orchestrator_completed", ticker=ticker,
                decision=decision_str, score=total_score, confidence=confidence)
    return response
