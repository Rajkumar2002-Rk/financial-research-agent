import asyncio
from langgraph.graph import StateGraph, END

from app.models.agent_state import AgentState, create_initial_state
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
    AnalysisResponse, TechnicalIndicators, TrendDirection, Recommendation,
)
from app.guardrails.financial_guardrails import apply_guardrails
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EMPTY_FUNDAMENTALS: dict = {
    "pe_ratio": None, "eps": None, "revenue_growth": None,
    "profit_margin": None, "debt_to_equity": None, "free_cash_flow": None,
    "market_cap": None, "data_available": False, "missing_fields": [],
}


# ── Node 0: Dispatcher — logs start, fans out to the three fetch nodes ─────────

def _dispatch(state: AgentState) -> dict:
    logger.info("pipeline_started", ticker=state["ticker"],
                session_id=state["session_id"],
                time_horizon=state.get("time_horizon", "default"))
    return {"current_step": "dispatching"}


# ── Node 1: Fetch OHLCV price data (Alpha Vantage TIME_SERIES_DAILY) ──────────

def _fetch_market_data(state: AgentState) -> dict:
    ticker, session_id = state["ticker"], state["session_id"]
    logger.info("node_fetch_market_data", ticker=ticker)
    try:
        raw = fetch_stock_data(ticker)
        validated = validate_market_data(raw, session_id)
        return {
            "raw_market_data": raw,
            "validated_market_data": validated,
            "current_step": "market_data_fetched",
            "tool_calls_log": [{"node": "fetch_market_data", "ticker": ticker,
                                 "records": len(raw.get("price_history", [])), "status": "ok"}],
        }
    except Exception as e:
        logger.error("node_fetch_market_data_failed", ticker=ticker, error=str(e))
        return {
            "errors": [f"fetch_market_data: {e}"],
            "current_step": "market_data_failed",
            "tool_calls_log": [{"node": "fetch_market_data", "ticker": ticker,
                                 "status": "error", "error": str(e)}],
        }


# ── Node 2: Fetch fundamental data (Alpha Vantage OVERVIEW + BALANCE_SHEET + CASH_FLOW) ──

def _fetch_fundamental_data(state: AgentState) -> dict:
    ticker = state["ticker"]
    logger.info("node_fetch_fundamental_data", ticker=ticker)
    try:
        fundamentals = fetch_fundamental_data(ticker)
        return {
            "fundamental_data": fundamentals,
            "current_step": "fundamental_data_fetched",
            "tool_calls_log": [{"node": "fetch_fundamental_data", "ticker": ticker,
                                 "available": fundamentals.get("data_available"), "status": "ok"}],
        }
    except Exception as e:
        logger.error("node_fetch_fundamental_data_failed", ticker=ticker, error=str(e))
        return {
            "fundamental_data": {**_EMPTY_FUNDAMENTALS},
            "errors": [f"fetch_fundamental_data: {e}"],
            "tool_calls_log": [{"node": "fetch_fundamental_data", "ticker": ticker, "status": "error"}],
        }


# ── Node 3: Fetch and validate news articles (Tavily) ─────────────────────────

def _fetch_news(state: AgentState) -> dict:
    ticker, session_id = state["ticker"], state["session_id"]
    include_news = state.get("include_news", True)
    logger.info("node_fetch_news", ticker=ticker, include_news=include_news)

    if not include_news:
        return {
            "news_articles": [],
            "validated_news_data": [],
            "current_step": "news_skipped",
            "tool_calls_log": [{"node": "fetch_news", "ticker": ticker, "status": "skipped"}],
        }

    try:
        raw = fetch_company_news(ticker, ticker)
        validated = validate_news_data(raw, session_id)
        return {
            "raw_news_data": raw,
            "news_articles": validated,
            "validated_news_data": validated,
            "current_step": "news_fetched",
            "tool_calls_log": [{"node": "fetch_news", "ticker": ticker,
                                 "count": len(validated), "status": "ok"}],
        }
    except Exception as e:
        logger.error("node_fetch_news_failed", ticker=ticker, error=str(e))
        return {
            "news_articles": [],
            "errors": [f"fetch_news: {e}"],
            "tool_calls_log": [{"node": "fetch_news", "ticker": ticker, "status": "error"}],
        }


# ── Node 4: Compute technical indicators (fan-in: waits for nodes 1, 2, 3) ────

def _compute_indicators(state: AgentState) -> dict:
    ticker, session_id = state["ticker"], state["session_id"]
    validated_market = state.get("validated_market_data")

    if not validated_market:
        return {
            "errors": ["compute_indicators: market data unavailable"],
            "current_step": "indicators_failed",
        }

    logger.info("node_compute_indicators", ticker=ticker)
    result = calculate_indicators(validated_market, session_id)
    return {
        "technical_indicators": result.get("indicators", {}),
        "trend_direction": result.get("trend", "Neutral"),
        "current_step": "indicators_computed",
        "tool_calls_log": [{"node": "compute_indicators", "ticker": ticker,
                             "trend": result.get("trend"), "status": "ok"}],
    }


def _indicators_route(state: AgentState) -> str:
    """Abort to END if market data is missing; otherwise continue scoring."""
    if not state.get("validated_market_data"):
        return "abort"
    return "continue"


# ── Node 5: Score all components + LLM news sentiment classification ──────────

def _compute_scores(state: AgentState) -> dict:
    ticker = state["ticker"]
    indicators    = state.get("technical_indicators") or {}
    fundamentals  = state.get("fundamental_data") or {**_EMPTY_FUNDAMENTALS}
    news_articles = state.get("news_articles") or []
    time_horizon  = state.get("time_horizon", "default")
    logger.info("node_compute_scores", ticker=ticker, time_horizon=time_horizon)

    # LLM call 1 — sentiment classification only, no investment decision
    news_analysis  = classify_news_sentiment(news_articles, ticker)
    news_sentiment = news_analysis.get("sentiment", "neutral")

    # Deterministic component scoring
    tech_result = compute_technical_score(indicators)
    fund_result = compute_fundamental_score(fundamentals)
    sent_result = compute_sentiment_score(news_sentiment)
    risk        = compute_risk_penalty(indicators)

    # Apply time-horizon multipliers to each component
    th = apply_time_horizon_weights(
        tech_score=tech_result["score"], tech_max=tech_result["max"],
        fund_score=fund_result["score"], fund_max=fund_result["max"],
        sent_score=sent_result["score"], sent_max=sent_result["max"],
        time_horizon=time_horizon,
    )

    tech_adj = th["technical"]
    fund_adj = th["fundamental"]
    sent_adj = th["sentiment"]

    total_score  = round(tech_adj["score"] + fund_adj["score"] + sent_adj["score"] + risk["penalty"])
    max_possible = round(tech_adj["max"] + fund_adj["max"] + sent_adj["max"])
    normalized   = compute_normalized_score(total_score, max_possible)

    fund_available = fundamentals.get("data_available", False)
    conflict = detect_conflict(
        tech_score=tech_adj["score"], tech_max=tech_adj["max"],
        fund_score=fund_adj["score"], fund_max=fund_adj["max"],
        sent_score=sent_adj["score"], sent_max=sent_adj["max"],
        fundamental_available=fund_available,
    )

    confidence_result = compute_confidence(
        fundamental_available=fund_available,
        fundamental_missing_count=len(fundamentals.get("missing_fields", [])),
        technical_missing_count=len(tech_result.get("missing_components", [])),
        technical_score=tech_adj["score"],
        technical_max=tech_adj["max"],
        fundamental_score=fund_adj["score"],
        fundamental_max=fund_adj["max"],
        sentiment_score=sent_adj["score"],
        news_sentiment=news_sentiment,
        volatility=indicators.get("volatility_30d"),
    )

    logger.info("scores_computed", ticker=ticker,
                total=total_score, max_possible=max_possible, normalized=normalized,
                conflict=conflict, confidence=confidence_result["confidence"])

    return {
        "news_analysis":        news_analysis,
        "news_summary":         news_analysis.get("summary", ""),
        "tech_result":          tech_result,
        "fund_result":          fund_result,
        "sent_result":          sent_result,
        "risk_result":          risk,
        "time_horizon_weights": th,
        "total_score":          total_score,
        "max_score":            max_possible,
        "normalized_score":     normalized,
        "conflict_detected":    conflict,
        "confidence_result":    confidence_result,
        "current_step":         "scores_computed",
        "tool_calls_log": [{"node": "compute_scores", "ticker": ticker,
                             "normalized": normalized, "status": "ok"}],
    }


# ── Node 6: Deterministic decision (no LLM involvement) ──────────────────────

def _make_decision(state: AgentState) -> dict:
    ticker     = state["ticker"]
    confidence = (state.get("confidence_result") or {}).get("confidence", 0)
    logger.info("node_make_decision", ticker=ticker)

    decision = make_deterministic_decision(
        normalized_score=state.get("normalized_score", 0.0),
        confidence=confidence,
        conflict_detected=state.get("conflict_detected", False),
    )
    return {
        "recommendation":   decision,
        "confidence_score": round(confidence / 100, 2),
        "current_step":     "decision_made",
        "tool_calls_log":   [{"node": "make_decision", "ticker": ticker,
                               "decision": decision, "status": "ok"}],
    }


# ── Node 7: LLM translates locked decision into natural language ───────────────

def _generate_explanation(state: AgentState) -> dict:
    ticker = state["ticker"]
    logger.info("node_generate_explanation", ticker=ticker)

    explanation = generate_explanation(
        ticker=ticker,
        decision=state.get("recommendation", "HOLD"),
        total_score=state.get("total_score", 0),
        confidence=int((state.get("confidence_score") or 0) * 100),
        technical=state.get("tech_result") or {},
        fundamental=state.get("fund_result") or {},
        sentiment=state.get("sent_result") or {},
        risk=state.get("risk_result") or {},
        fundamentals_raw=state.get("fundamental_data") or {},
    )
    return {
        "explanation_data": explanation,
        "reasoning":        explanation.get("reasoning", ""),
        "risk_assessment":  explanation.get("risk_assessment", ""),
        "current_step":     "explanation_generated",
        "tool_calls_log":   [{"node": "generate_explanation", "ticker": ticker, "status": "ok"}],
    }


# ── Node 8: Build AnalysisResponse and apply guardrails ───────────────────────

def _apply_guardrails(state: AgentState) -> dict:
    ticker, session_id = state["ticker"], state["session_id"]
    logger.info("node_apply_guardrails", ticker=ticker)

    ind  = state.get("technical_indicators") or {}
    vm   = state.get("validated_market_data") or {}
    fund = state.get("fundamental_data") or {}
    tech = state.get("tech_result") or {}
    fnd  = state.get("fund_result") or {}
    sent = state.get("sent_result") or {}
    risk = state.get("risk_result") or {}
    th   = state.get("time_horizon_weights") or {}
    na   = state.get("news_analysis") or {}
    cr   = state.get("confidence_result") or {}

    recommendation_map = {
        "BUY":               Recommendation.BUY,
        "SELL":              Recommendation.SELL,
        "HOLD":              Recommendation.HOLD,
        "INSUFFICIENT_DATA": Recommendation.INSUFFICIENT_DATA,
    }
    trend_map = {
        "Bullish": TrendDirection.BULLISH,
        "Bearish": TrendDirection.BEARISH,
        "Volatile": TrendDirection.VOLATILE,
    }

    all_missing = list(tech.get("missing_components", [])) + list(fnd.get("missing_components", []))

    response = AnalysisResponse(
        ticker=ticker,
        company_name=vm.get("company_name", ticker),
        current_price=vm.get("current_price"),
        currency=vm.get("currency", "USD"),
        price_history=vm.get("price_history", []),
        trend_analysis=trend_map.get(state.get("trend_direction", ""), TrendDirection.NEUTRAL),
        technical_indicators=TechnicalIndicators(
            ma_50=ind.get("ma_50"),
            ma_200=ind.get("ma_200"),
            rsi=ind.get("rsi"),
            volatility_30d=ind.get("volatility_30d"),
            price_change_pct=ind.get("price_change_pct"),
            volume_avg_30d=ind.get("volume_avg_30d"),
            golden_cross=ind.get("golden_cross"),
            death_cross=ind.get("death_cross"),
        ),
        news_summary=na.get("summary", ""),
        risk_assessment=state.get("risk_assessment", ""),
        recommendation=recommendation_map.get(
            state.get("recommendation", "INSUFFICIENT_DATA"), Recommendation.INSUFFICIENT_DATA
        ),
        confidence_score=state.get("confidence_score", 0.0),
        reasoning=state.get("reasoning", ""),
        session_id=session_id,
        cached=False,
        total_score=state.get("total_score"),
        max_score=state.get("max_score"),
        normalized_score=state.get("normalized_score"),
        technical_score=round(tech.get("score", 0)),
        fundamental_score=round(fnd.get("score", 0)),
        sentiment_score=sent.get("score"),
        risk_penalty=risk.get("penalty"),
        score_breakdown={
            "technical":   {**tech, "weight": th.get("technical", {}).get("weight", 1.0)},
            "fundamental": {**fnd,  "weight": th.get("fundamental", {}).get("weight", 1.0)},
            "sentiment":   {
                "score":  sent.get("score", 0),
                "max":    sent.get("max", 15),
                "reason": sent.get("reason", ""),
                "weight": th.get("sentiment", {}).get("weight", 1.0),
            },
            "risk": risk,
            "time_horizon": th,
        },
        confidence_breakdown=cr.get("breakdown"),
        key_factors=(state.get("explanation_data") or {}).get("key_factors", []),
        data_gaps=fund.get("missing_fields", []),
        missing_components=all_missing,
        fundamental_data={
            "pe_ratio":       fund.get("pe_ratio"),
            "eps":            fund.get("eps"),
            "revenue_growth": fund.get("revenue_growth"),
            "profit_margin":  fund.get("profit_margin"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "free_cash_flow": fund.get("free_cash_flow"),
            "market_cap":     fund.get("market_cap"),
        },
        conflict_detected=state.get("conflict_detected", False),
        time_horizon_used=state.get("time_horizon", "default"),
    )

    response = apply_guardrails(response, session_id)

    return {
        "final_response": response.model_dump(mode="json"),
        "current_step":   "guardrails_applied",
        "tool_calls_log": [{"node": "apply_guardrails", "ticker": ticker,
                             "recommendation": response.recommendation.value, "status": "ok"}],
    }


# ── Build and compile the LangGraph StateGraph ────────────────────────────────

def _build_pipeline():
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("dispatch",               _dispatch)
    graph.add_node("fetch_market_data",      _fetch_market_data)
    graph.add_node("fetch_fundamental_data", _fetch_fundamental_data)
    graph.add_node("fetch_news",             _fetch_news)
    graph.add_node("compute_indicators",     _compute_indicators)
    graph.add_node("compute_scores",         _compute_scores)
    graph.add_node("make_decision",          _make_decision)
    graph.add_node("generate_explanation",   _generate_explanation)
    graph.add_node("apply_guardrails",       _apply_guardrails)

    # Entry point
    graph.set_entry_point("dispatch")

    # Step 1 (sequential): fetch market data first — AV burst limit is 1 req/sec
    graph.add_edge("dispatch", "fetch_market_data")

    # Step 2 (parallel): after price data returns, fan out to fundamental + news
    # fetch_fundamental_data hits AV again; fetch_news hits Tavily — no conflict
    graph.add_edge("fetch_market_data",      "fetch_fundamental_data")
    graph.add_edge("fetch_market_data",      "fetch_news")

    # Fan-in: compute_indicators waits for both branches to complete
    graph.add_edge("fetch_fundamental_data", "compute_indicators")
    graph.add_edge("fetch_news",             "compute_indicators")

    # Conditional edge: abort to END if market data fetch failed
    graph.add_conditional_edges(
        "compute_indicators",
        _indicators_route,
        {"continue": "compute_scores", "abort": END},
    )

    # Sequential scoring → decision → explanation → guardrails
    graph.add_edge("compute_scores",       "make_decision")
    graph.add_edge("make_decision",        "generate_explanation")
    graph.add_edge("generate_explanation", "apply_guardrails")
    graph.add_edge("apply_guardrails",     END)

    return graph.compile()


_pipeline = _build_pipeline()


# ── Public entry point (called by API routes and portfolio engine) ─────────────

async def run_analysis(
    ticker: str,
    session_id: str,
    include_news: bool = True,
    time_horizon: str = "default",
    settings=None,
) -> AnalysisResponse:
    initial_state = create_initial_state(
        ticker=ticker,
        session_id=session_id,
        include_news=include_news,
        time_horizon=time_horizon,
    )

    # Run the sync graph in a thread so we don't block the async event loop
    final_state = await asyncio.to_thread(_pipeline.invoke, initial_state)

    if not final_state.get("final_response"):
        errors = final_state.get("errors", [])
        raise ValueError(f"Analysis pipeline failed for '{ticker}': {'; '.join(errors)}")

    result = AnalysisResponse(**final_state["final_response"])
    logger.info("orchestrator_completed", ticker=ticker,
                decision=result.recommendation.value,
                normalized=result.normalized_score,
                confidence=result.confidence_score,
                steps=len(final_state.get("tool_calls_log", [])))
    return result
