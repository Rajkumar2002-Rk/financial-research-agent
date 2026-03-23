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
    apply_time_horizon_weights,
    compute_normalized_score,
    detect_conflict,
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
    time_horizon: str = "default",
    settings=None,
) -> AnalysisResponse:

    logger.info("orchestrator_started", ticker=ticker, session_id=session_id,
                time_horizon=time_horizon)

    # ── Step 1: Fetch market data ─────────────────────────────────────────────
    logger.info("step_1_market_data", ticker=ticker)
    market_data = fetch_stock_data(ticker)
    validated_market = validate_market_data(market_data, session_id)

    # ── Step 2: Fetch fundamental data ────────────────────────────────────────
    logger.info("step_2_fundamental_data", ticker=ticker)
    fundamentals = fetch_fundamental_data(ticker)
    fundamental_available = fundamentals.get("data_available", False)
    if not fundamental_available:
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

    # ── Step 5: Compute component scores ─────────────────────────────────────
    logger.info("step_5_scoring", ticker=ticker)

    # 5a — LLM classifies news sentiment only (no decision-making)
    news_analysis = classify_news_sentiment(news_articles, ticker)
    news_sentiment = news_analysis.get("sentiment", "neutral")

    # 5b — Deterministic component scoring (dynamic max — missing data excluded)
    tech_result  = compute_technical_score(indicators)
    fund_result  = compute_fundamental_score(fundamentals)
    sent_result  = compute_sentiment_score(news_sentiment)
    risk         = compute_risk_penalty(indicators)   # volatility-only, no sentiment

    tech_score_raw  = tech_result["score"]
    tech_max_raw    = tech_result["max"]
    fund_score_raw  = fund_result["score"]
    fund_max_raw    = fund_result["max"]
    sent_score_raw  = sent_result["score"]
    sent_max_raw    = sent_result["max"]

    # 5c — Apply time horizon weights
    th = apply_time_horizon_weights(
        tech_score=tech_score_raw,  tech_max=tech_max_raw,
        fund_score=fund_score_raw,  fund_max=fund_max_raw,
        sent_score=sent_score_raw,  sent_max=sent_max_raw,
        time_horizon=time_horizon,
    )

    tech_score_adj  = th["technical"]["score"]
    tech_max_adj    = th["technical"]["max"]
    fund_score_adj  = th["fundamental"]["score"]
    fund_max_adj    = th["fundamental"]["max"]
    sent_score_adj  = th["sentiment"]["score"]
    sent_max_adj    = th["sentiment"]["max"]

    # Total = weighted component scores + risk penalty (risk is not time-horizon-weighted)
    total_score      = round(tech_score_adj + fund_score_adj + sent_score_adj + risk["penalty"])
    max_possible     = round(tech_max_adj + fund_max_adj + sent_max_adj)

    # 5d — Normalized score (0–100 scale)
    normalized_score = compute_normalized_score(total_score, max_possible)

    # 5e — Conflict detection
    conflict_detected = detect_conflict(
        tech_score=tech_score_adj, tech_max=tech_max_adj,
        fund_score=fund_score_adj, fund_max=fund_max_adj,
        sent_score=sent_score_adj, sent_max=sent_max_adj,
        fundamental_available=fundamental_available,
    )

    # 5f — Confidence
    tech_missing_count = len(tech_result.get("missing_components", []))
    fund_missing_count = len(fundamentals.get("missing_fields", []))

    confidence_result = compute_confidence(
        fundamental_available=fundamental_available,
        fundamental_missing_count=fund_missing_count,
        technical_missing_count=tech_missing_count,
        technical_score=tech_score_adj,
        technical_max=tech_max_adj,
        fundamental_score=fund_score_adj,
        fundamental_max=fund_max_adj,
        sentiment_score=sent_score_adj,
        news_sentiment=news_sentiment,
        volatility=indicators.get("volatility_30d"),
    )
    confidence = confidence_result["confidence"]

    logger.info(
        "scores_computed", ticker=ticker,
        total=total_score, max_possible=max_possible,
        normalized=normalized_score,
        technical=tech_score_raw, fundamental=fund_score_raw,
        sentiment=sent_score_raw, risk_penalty=risk["penalty"],
        conflict=conflict_detected, confidence=confidence,
        time_horizon=time_horizon,
    )

    # ── Step 6: Deterministic decision (normalized score + conflict check) ────
    logger.info("step_6_decision", ticker=ticker)
    decision_str = make_deterministic_decision(
        normalized_score=normalized_score,
        confidence=confidence,
        conflict_detected=conflict_detected,
    )

    # ── Step 7: LLM generates explanation (cannot override decision) ─────────
    logger.info("step_7_explanation", ticker=ticker)
    explanation_data = generate_explanation(
        ticker=ticker,
        decision=decision_str,
        total_score=total_score,
        confidence=confidence,
        technical=tech_result,
        fundamental=fund_result,
        sentiment=sent_result,
        risk=risk,
        fundamentals_raw=fundamentals,
    )

    # ── Collect missing components across all domains ─────────────────────────
    all_missing_components = list(tech_result.get("missing_components", []))
    all_missing_components += list(fund_result.get("missing_components", []))

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
        "BUY":              Recommendation.BUY,
        "SELL":             Recommendation.SELL,
        "HOLD":             Recommendation.HOLD,
        "INSUFFICIENT_DATA": Recommendation.INSUFFICIENT_DATA,
    }
    recommendation = recommendation_map.get(decision_str, Recommendation.INSUFFICIENT_DATA)

    trend_map = {
        "Bullish":  TrendDirection.BULLISH,
        "Bearish":  TrendDirection.BEARISH,
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
        max_score=max_possible,
        normalized_score=normalized_score,
        technical_score=round(tech_score_raw),
        fundamental_score=round(fund_score_raw),
        sentiment_score=sent_score_raw,
        risk_penalty=risk["penalty"],
        score_breakdown={
            "technical":   {**tech_result, "weight": th["technical"]["weight"]},
            "fundamental": {**fund_result, "weight": th["fundamental"]["weight"]},
            "sentiment":   {
                "score": sent_score_raw, "max": sent_max_raw,
                "reason": sent_result["reason"],
                "weight": th["sentiment"]["weight"],
            },
            "risk": risk,
            "time_horizon": th,
        },
        confidence_breakdown=confidence_result["breakdown"],
        key_factors=explanation_data.get("key_factors", []),
        data_gaps=fundamentals.get("missing_fields", []),
        missing_components=all_missing_components,
        fundamental_data={
            "pe_ratio":       fundamentals.get("pe_ratio"),
            "eps":            fundamentals.get("eps"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "profit_margin":  fundamentals.get("profit_margin"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "free_cash_flow": fundamentals.get("free_cash_flow"),
            "market_cap":     fundamentals.get("market_cap"),
        },
        conflict_detected=conflict_detected,
        time_horizon_used=time_horizon,
    )

    response = apply_guardrails(response, session_id)
    logger.info("orchestrator_completed", ticker=ticker,
                decision=decision_str, normalized=normalized_score,
                conflict=conflict_detected, confidence=confidence)
    return response
