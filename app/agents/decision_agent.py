from openai import OpenAI
from typing import Dict, Any, List
from app.utils.config import get_settings
from app.utils.logger import get_logger
import json

logger = get_logger(__name__)
settings = get_settings()


def make_decision(
    ticker: str,
    market_data: Dict[str, Any],
    indicators: Dict[str, Any],
    news_articles: List[Dict[str, Any]],
    session_id: str,
) -> Dict[str, Any]:
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        news_text = ""
        if news_articles:
            for i, article in enumerate(news_articles[:3], 1):
                news_text += f"{i}. {article['title']}\n{article['content'][:200]}\n\n"
        else:
            news_text = "No recent news available."

        prompt = f"""You are a financial analyst. Analyze the following data for {ticker} and provide an investment recommendation.

PRICE DATA:
- Current Price: ${market_data.get('current_price')}
- 52-Week High: ${market_data.get('52_week_high')}
- 52-Week Low: ${market_data.get('52_week_low')}

TECHNICAL INDICATORS:
- 50-Day Moving Average: {indicators.get('ma_50')}
- 200-Day Moving Average: {indicators.get('ma_200')}
- RSI: {indicators.get('rsi')}
- 30-Day Volatility: {indicators.get('volatility_30d')}
- Price Change (1 year): {indicators.get('price_change_pct')}%
- Golden Cross: {indicators.get('golden_cross')}

RECENT NEWS:
{news_text}

Respond in this exact JSON format only:
{{
    "recommendation": "BUY or SELL or HOLD",
    "confidence_score": 0.0 to 1.0,
    "reasoning": "2-3 sentences explaining your recommendation",
    "risk_assessment": "1-2 sentences on key risks",
    "news_summary": "1-2 sentences summarizing the news sentiment"
}}"""

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.OPENAI_TEMPERATURE,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
          content = content.split("```")[1]
        if content.startswith("json"):
          content = content[4:]
        content = content.strip()

        result = json.loads(content)

        logger.info(
            "decision_made",
            session_id=session_id,
            ticker=ticker,
            recommendation=result.get("recommendation"),
            confidence=result.get("confidence_score"),
        )

        return result

    except json.JSONDecodeError as e:
        logger.error("decision_json_parse_failed", session_id=session_id, error=str(e))
        return {
            "recommendation": "INSUFFICIENT_DATA",
            "confidence_score": 0.0,
            "reasoning": "Failed to parse model response.",
            "risk_assessment": "Unable to assess risk.",
            "news_summary": "Unable to summarize news.",
        }

    except Exception as e:
        logger.error("decision_failed", session_id=session_id, error=str(e))
        raise