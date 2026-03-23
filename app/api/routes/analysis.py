from fastapi import APIRouter, HTTPException
import uuid
import re
from typing import List, Optional

from app.models.requests import AnalysisRequest
from app.models.responses import AnalysisResponse
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["Analysis"])

COMPANY_TO_TICKER = {
    "apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL", "amazon": "AMZN",
    "meta": "META", "facebook": "META", "nvidia": "NVDA",
    "netflix": "NFLX", "spotify": "SPOT", "uber": "UBER",
    "airbnb": "ABNB", "shopify": "SHOP", "palantir": "PLTR",
    "amd": "AMD", "intel": "INTC", "qualcomm": "QCOM",
    "disney": "DIS", "coca cola": "KO", "pepsi": "PEP",
    "nike": "NKE", "walmart": "WMT", "jpmorgan": "JPM",
    "goldman": "GS", "berkshire": "BRK-B", "salesforce": "CRM",
    "oracle": "ORCL", "adobe": "ADBE", "paypal": "PYPL",
    "snap": "SNAP", "twitter": "X", "lyft": "LYFT",
}

SKIP_WORDS = {
    "I", "A", "AN", "THE", "IN", "AT", "IS", "IT", "OR", "AND",
    "TO", "OF", "ON", "BY", "AS", "FOR", "NOT", "BUT", "RSI",
    "MA", "BUY", "SELL", "HOLD", "USD", "ETF", "AI", "IF",
    "MY", "ME", "DO", "SO", "US", "BE", "NO", "UP", "GO",
}


def new_session_id():
    return f"session-{uuid.uuid4().hex[:12]}"


def extract_tickers(message: str) -> list:
    msg_lower = message.lower()
    tickers = set()

    for name, ticker in COMPANY_TO_TICKER.items():
        if name in msg_lower:
            tickers.add(ticker)

    found = re.findall(r'\b[A-Z]{2,5}\b', message)
    for t in found:
        if t not in SKIP_WORDS:
            tickers.add(t)

    return list(tickers)[:3]


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_company(request: AnalysisRequest):
    session_id = request.session_id or new_session_id()
    logger.info("analyze_request", ticker=request.ticker, session_id=session_id)

    try:
        from app.services.cache_service import CacheService
        from app.agents.orchestrator import run_analysis

        cache = CacheService(settings)
        cache_key = f"analysis:{request.ticker}:v1"

        cached = await cache.get(cache_key)
        if cached:
            cached["cached"] = True
            cached["session_id"] = session_id
            return AnalysisResponse(**cached)

        result = await run_analysis(
            ticker=request.ticker,
            session_id=session_id,
            include_news=request.include_news,
            time_horizon=getattr(request, "time_horizon", "default"),
            settings=settings,
        )

        await cache.set(cache_key, result.model_dump(mode="json"), settings.REDIS_CACHE_TTL)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("analyze_failed", ticker=request.ticker, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(request: dict):
    from openai import OpenAI
    from app.services.session_service import SessionService
    from app.tools.yfinance_tool import fetch_stock_data

    message = request.get("message", "")
    session_id = request.get("session_id") or new_session_id()
    context_ticker = request.get("ticker", "")

    tickers_to_fetch = extract_tickers(message)

    live_data_lines = []
    for ticker in tickers_to_fetch:
        try:
            data = fetch_stock_data(ticker)
            live_data_lines.append(
                f"  {ticker}: Price=${data['current_price']}, "
                f"52W High=${data['52_week_high']}, 52W Low=${data['52_week_low']}"
            )
        except Exception:
            pass

    session = SessionService(settings)
    history = await session.get_history(session_id)
    await session.add_to_history(session_id, "user", message)

    system_parts = [
        "You are a professional financial analyst AI. You provide expert, concise investment insights.",
        "Always back your answers with data. For buy/sell/hold questions, give a clear recommendation with reasoning.",
    ]

    if context_ticker:
        ind = {}
        system_parts.append(f"\nCURRENT SESSION — {context_ticker}:")
        system_parts.append(f"  Price: ${request.get('current_price', 'N/A')}")
        system_parts.append(f"  Recommendation: {request.get('recommendation', 'N/A')}")
        system_parts.append(f"  Confidence: {request.get('confidence_score', 'N/A')}")
        system_parts.append(f"  RSI: {request.get('rsi', 'N/A')}")
        system_parts.append(f"  MA50: {request.get('ma_50', 'N/A')}")
        system_parts.append(f"  MA200: {request.get('ma_200', 'N/A')}")
        system_parts.append(f"  1Y Change: {request.get('price_change_pct', 'N/A')}%")

    if live_data_lines:
        system_parts.append("\nLIVE MARKET DATA (fetched now):")
        system_parts.extend(live_data_lines)

    messages = [{"role": "system", "content": "\n".join(system_parts)}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.3,
    )

    reply = response.choices[0].message.content.strip()
    await session.add_to_history(session_id, "assistant", reply)
    return {"reply": reply, "session_id": session_id}


# ── Portfolio Ranking ─────────────────────────────────────────────────────────

from pydantic import BaseModel, Field as PydanticField


class PortfolioRankRequest(BaseModel):
    tickers: List[str] = PydanticField(..., min_length=2, max_length=8)
    time_horizon: str = PydanticField(
        default="default",
        description="'short_term', 'long_term', or 'default'",
    )
    session_id: Optional[str] = None


@router.post("/portfolio/rank")
async def portfolio_rank(request: PortfolioRankRequest):
    """
    Analyze multiple tickers, rank by normalized_score, and return
    proportional allocation percentages for BUY/HOLD stocks.
    """
    from app.agents.portfolio_engine import rank_portfolio

    # Deduplicate and uppercase
    seen: set = set()
    clean_tickers: List[str] = []
    for t in request.tickers:
        u = t.strip().upper()
        if u not in seen:
            seen.add(u)
            clean_tickers.append(u)

    if len(clean_tickers) < 2:
        raise HTTPException(status_code=400, detail="At least 2 unique tickers required.")

    valid_horizons = {"short_term", "long_term", "default"}
    time_horizon = request.time_horizon if request.time_horizon in valid_horizons else "default"

    try:
        result = await rank_portfolio(
            tickers=clean_tickers,
            time_horizon=time_horizon,
            session_id=request.session_id,
        )
        # Serialise AnalysisResponse objects
        result["analyses"] = [a.model_dump(mode="json") for a in result["analyses"]]
        return result
    except Exception as e:
        logger.error("portfolio_rank_failed", tickers=clean_tickers, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
