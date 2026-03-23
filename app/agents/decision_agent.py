from openai import OpenAI
from typing import Dict, Any, List
from app.utils.config import get_settings
from app.utils.logger import get_logger
import json

logger = get_logger(__name__)
settings = get_settings()


def classify_news_sentiment(news_articles: List[Dict[str, Any]], ticker: str) -> Dict[str, Any]:
    """
    LLM role: classify news sentiment only — positive / neutral / negative.
    LLM does NOT make investment decisions here.
    """
    if not news_articles:
        return {
            "sentiment": "neutral",
            "summary": "No recent news available.",
            "key_events": [],
        }

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    news_text = ""
    for i, article in enumerate(news_articles[:3], 1):
        news_text += f"{i}. {article['title']}\n{article['content'][:300]}\n\n"

    prompt = f"""You are classifying news sentiment for a financial analysis system.
Analyze these news articles about {ticker} and return ONLY valid JSON with these exact keys:
- "sentiment": exactly one of "positive", "neutral", or "negative"
- "summary": 1-2 sentence factual summary
- "key_events": list of up to 3 specific events mentioned

News articles:
{news_text}

Return only valid JSON. No markdown, no explanation."""

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rstrip("`").strip()
        result = json.loads(content.strip())
        # Guard: GPT sometimes wraps response in an array
        if isinstance(result, list):
            result = result[0] if result else {}
        return result
    except Exception as e:
        logger.error("sentiment_classification_failed", ticker=ticker, error=str(e))
        return {"sentiment": "neutral", "summary": "News analysis unavailable.", "key_events": []}


def generate_explanation(
    ticker: str,
    decision: str,
    total_score: int,
    confidence: int,
    technical: Dict[str, Any],
    fundamental: Dict[str, Any],
    sentiment: Dict[str, Any],
    risk: Dict[str, Any],
    fundamentals_raw: Dict[str, Any],
) -> Dict[str, Any]:
    """
    LLM role: translate deterministic scores into natural language.
    LLM cannot override or change the decision.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    fund_lines = []
    if fundamentals_raw.get("pe_ratio"):
        fund_lines.append(f"P/E: {fundamentals_raw['pe_ratio']}")
    if fundamentals_raw.get("eps"):
        fund_lines.append(f"EPS: ${fundamentals_raw['eps']}")
    if fundamentals_raw.get("revenue_growth") is not None:
        fund_lines.append(f"Revenue Growth: {fundamentals_raw['revenue_growth']}%")
    if fundamentals_raw.get("profit_margin") is not None:
        fund_lines.append(f"Profit Margin: {fundamentals_raw['profit_margin']}%")
    if fundamentals_raw.get("debt_to_equity") is not None:
        fund_lines.append(f"Debt/Equity: {fundamentals_raw['debt_to_equity']}%")

    missing = fundamentals_raw.get("missing_fields", [])

    tech_max  = technical.get('max', 25)
    fund_max  = fundamental.get('max', 40)
    tech_missing  = technical.get('missing_components', [])
    fund_missing  = fundamental.get('missing_components', [])

    prompt = f"""You are writing a brief explanation for a deterministic financial analysis result.
The decision was computed by a rule-based scoring engine — you are NOT changing it.

TICKER: {ticker}
DECISION: {decision} (LOCKED — do not suggest a different decision)
TOTAL SCORE: {total_score} (max achievable with available data: {tech_max + fund_max + 15})
CONFIDENCE: {confidence}%
MISSING COMPONENTS: {tech_missing + fund_missing if (tech_missing or fund_missing) else 'None — full data available'}

SCORE BREAKDOWN:
- Technical: {technical.get('score', 0)}/{tech_max} (missing: {tech_missing if tech_missing else 'none'})
  {json.dumps(technical.get('breakdown', {}), indent=2)}
- Fundamental: {fundamental.get('score', 0)}/{fund_max} (missing: {fund_missing if fund_missing else 'none'})
  {json.dumps(fundamental.get('breakdown', {}), indent=2)}
- Sentiment: {sentiment.get('score', 0)}/15 ({sentiment.get('reason', '')})
- Risk Penalty: {risk.get('penalty', 0)}/−10 (volatility-only)
  Reasons: {risk.get('reasons', [])}

FUNDAMENTAL DATA: {', '.join(fund_lines) if fund_lines else 'Not available'}
MISSING DATA: {missing if missing else 'None'}
NEWS SENTIMENT: {sentiment.get('sentiment', 'neutral')}
NEWS SUMMARY: {sentiment.get('summary', '')}

Write exactly 3 fields in JSON:
- "reasoning": 3-4 sentences explaining the specific scores and why they led to this decision
- "risk_assessment": 2 sentences on the main risks given the data above
- "key_factors": list of exactly 3 specific factors that drove the decision (be precise, use numbers)

Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rstrip("`").strip()
        result = json.loads(content.strip())
        # Guard: GPT sometimes wraps response in an array
        if isinstance(result, list):
            result = result[0] if result else {}
        return result
    except Exception as e:
        logger.error("explanation_generation_failed", ticker=ticker, error=str(e))
        return {
            "reasoning": f"Score-based decision: {decision} with total score {total_score}/80.",
            "risk_assessment": "Unable to generate detailed risk assessment.",
            "key_factors": [f"Total score: {total_score}/80", f"Confidence: {confidence}%", f"Decision: {decision}"],
        }
