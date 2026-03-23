from app.models.responses import AnalysisResponse, Recommendation
from app.utils.logger import get_logger

logger = get_logger(__name__)


def apply_guardrails(response: AnalysisResponse, session_id: str) -> AnalysisResponse:

    response = check_confidence_threshold(response, session_id)
    response = check_recommendation_consistency(response, session_id)
    response = check_required_fields(response, session_id)

    return response


def check_confidence_threshold(response: AnalysisResponse, session_id: str) -> AnalysisResponse:
    if response.confidence_score < 0.2:
        logger.warning(
            "guardrail_low_confidence",
            session_id=session_id,
            confidence=response.confidence_score,
            original_recommendation=response.recommendation,
        )
        response.recommendation = Recommendation.INSUFFICIENT_DATA
        response.reasoning = f"Confidence too low ({response.confidence_score:.2f}) to make a reliable recommendation. " + response.reasoning

    return response


def check_recommendation_consistency(response: AnalysisResponse, session_id: str) -> AnalysisResponse:
    indicators = response.technical_indicators
    recommendation = response.recommendation

    if recommendation == Recommendation.BUY:
        if indicators.rsi and indicators.rsi > 80:
            logger.warning(
                "guardrail_inconsistent_recommendation",
                session_id=session_id,
                rule="BUY with RSI above 80",
                rsi=indicators.rsi,
            )
            response.recommendation = Recommendation.HOLD
            response.reasoning = "Recommendation adjusted from BUY to HOLD: RSI above 80 indicates overbought conditions. " + response.reasoning

    if recommendation == Recommendation.SELL:
        if indicators.rsi and indicators.rsi < 20:
            logger.warning(
                "guardrail_inconsistent_recommendation",
                session_id=session_id,
                rule="SELL with RSI below 20",
                rsi=indicators.rsi,
            )
            response.recommendation = Recommendation.HOLD
            response.reasoning = "Recommendation adjusted from SELL to HOLD: RSI below 20 indicates oversold conditions. " + response.reasoning

    return response


def check_required_fields(response: AnalysisResponse, session_id: str) -> AnalysisResponse:
    if not response.reasoning:
        logger.warning("guardrail_missing_reasoning", session_id=session_id)
        response.reasoning = "No reasoning provided."

    if not response.risk_assessment:
        logger.warning("guardrail_missing_risk", session_id=session_id)
        response.risk_assessment = "No risk assessment provided."

    if response.confidence_score < 0.0:
        response.confidence_score = 0.0
    if response.confidence_score > 1.0:
        response.confidence_score = 1.0

    return response