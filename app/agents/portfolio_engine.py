"""
Portfolio Engine — Multi-stock ranking and allocation.

Given N tickers, runs a full analysis on each, then:
  1. Ranks stocks by normalized_score (highest first)
  2. Assigns BUY / HOLD stocks a proportional allocation % (sums to 100%)
  3. Assigns SELL / INSUFFICIENT_DATA stocks 0% allocation
"""
import uuid
from typing import List, Dict, Any

from app.agents.orchestrator import run_analysis
from app.models.responses import AnalysisResponse, Recommendation
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _new_session_id() -> str:
    return f"portfolio-{uuid.uuid4().hex[:10]}"


async def rank_portfolio(
    tickers: List[str],
    time_horizon: str = "default",
    session_id: str = None,
) -> Dict[str, Any]:
    """
    Run analysis on each ticker, rank by normalized_score, compute allocations.

    Returns:
        {
            "session_id": str,
            "time_horizon": str,
            "tickers_analyzed": int,
            "rankings": [
                {
                    "rank": 1,
                    "ticker": "AAPL",
                    "recommendation": "BUY",
                    "normalized_score": 74.3,
                    "confidence_score": 0.72,
                    "allocation_pct": 45.2,
                    "conflict_detected": False,
                    "reasoning_summary": "...",
                },
                ...
            ],
            "analyses": [AnalysisResponse, ...],  # full results per ticker
            "allocation_note": "Allocation split only among BUY/HOLD stocks",
        }
    """
    sid = session_id or _new_session_id()
    logger.info("portfolio_rank_started", tickers=tickers, time_horizon=time_horizon)

    analyses: List[AnalysisResponse] = []
    errors: List[Dict[str, str]] = []

    for ticker in tickers:
        try:
            result = await run_analysis(
                ticker=ticker,
                session_id=sid,
                include_news=True,
                time_horizon=time_horizon,
            )
            analyses.append(result)
            logger.info("portfolio_ticker_done", ticker=ticker,
                        normalized=result.normalized_score,
                        decision=result.recommendation.value)
        except Exception as e:
            logger.error("portfolio_ticker_failed", ticker=ticker, error=str(e))
            errors.append({"ticker": ticker, "error": str(e)})

    # ── Rank by normalized_score (descending) ────────────────────────────────
    ranked = sorted(
        analyses,
        key=lambda a: a.normalized_score if a.normalized_score is not None else -999,
        reverse=True,
    )

    # ── Allocation: only to BUY and HOLD stocks ───────────────────────────────
    investable = [
        a for a in ranked
        if a.recommendation in (Recommendation.BUY, Recommendation.HOLD)
        and a.normalized_score is not None
    ]
    total_score = sum(a.normalized_score for a in investable)

    allocations: Dict[str, float] = {}
    for a in analyses:
        if a in investable and total_score > 0:
            allocations[a.ticker] = round((a.normalized_score / total_score) * 100, 1)
        else:
            allocations[a.ticker] = 0.0

    # ── Build ranking rows ────────────────────────────────────────────────────
    rankings = []
    for rank_idx, analysis in enumerate(ranked, start=1):
        # Extract a short reasoning summary (first sentence of reasoning)
        reasoning_full = analysis.reasoning or ""
        summary = reasoning_full.split(".")[0].strip() if reasoning_full else "No summary available"
        if len(summary) > 120:
            summary = summary[:117] + "..."

        rankings.append({
            "rank":              rank_idx,
            "ticker":            analysis.ticker,
            "company_name":      analysis.company_name,
            "recommendation":    analysis.recommendation.value,
            "normalized_score":  analysis.normalized_score,
            "total_score":       analysis.total_score,
            "max_score":         analysis.max_score,
            "confidence_score":  analysis.confidence_score,
            "allocation_pct":    allocations.get(analysis.ticker, 0.0),
            "conflict_detected": analysis.conflict_detected,
            "current_price":     analysis.current_price,
            "currency":          analysis.currency,
            "reasoning_summary": summary,
            "time_horizon_used": analysis.time_horizon_used,
        })

    logger.info(
        "portfolio_rank_complete",
        total=len(analyses), investable=len(investable),
        errors=len(errors),
    )

    return {
        "session_id": sid,
        "time_horizon": time_horizon,
        "tickers_analyzed": len(analyses),
        "tickers_failed": errors,
        "rankings": rankings,
        "analyses": analyses,
        "allocation_note": (
            "Allocation % is proportional to normalized_score among BUY/HOLD stocks only. "
            "SELL and INSUFFICIENT_DATA stocks receive 0% allocation."
        ) if investable else
        "All stocks rated SELL or INSUFFICIENT_DATA — no allocation recommended.",
    }
