from typing import Dict, Any, List
from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_market_data(raw_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    warnings = []
    cleaned = raw_data.copy()

    if not cleaned.get("current_price") or cleaned["current_price"] <= 0:
        warnings.append("current_price missing or invalid")
        cleaned["current_price"] = None

    if not cleaned.get("price_history"):
        warnings.append("price_history is empty")
    elif len(cleaned["price_history"]) < 10:
        warnings.append(f"price_history only has {len(cleaned['price_history'])} rows, expected at least 10")

    if cleaned.get("52_week_high") and cleaned.get("52_week_low"):
        if cleaned["52_week_low"] > cleaned["52_week_high"]:
            warnings.append("52_week_low is greater than 52_week_high, swapping values")
            cleaned["52_week_high"], cleaned["52_week_low"] = cleaned["52_week_low"], cleaned["52_week_high"]

    for warning in warnings:
        logger.warning("market_data_validation", session_id=session_id, issue=warning)

    cleaned["data_warnings"] = warnings
    return cleaned


def validate_news_data(raw_news: List[Dict[str, Any]], session_id: str) -> List[Dict[str, Any]]:
    if not raw_news:
        logger.warning("news_data_empty", session_id=session_id)
        return []

    cleaned = []
    for article in raw_news:
        if not article.get("title") or not article.get("content"):
            continue
        if len(article.get("content", "")) < 50:
            continue
        cleaned.append(article)

    logger.info("news_validation_complete", session_id=session_id, original=len(raw_news), kept=len(cleaned))
    return cleaned