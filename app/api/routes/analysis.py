from fastapi import APIRouter, HTTPException
import uuid

from app.models.requests import AnalysisRequest, ComparisonRequest, PortfolioRequest
from app.models.responses import AnalysisResponse
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["Analysis"])


def new_session_id():
    return f"session-{uuid.uuid4().hex[:12]}"


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

    ticker = request.get("ticker", "")
    message = request.get("message", "")
    session_id = request.get("session_id") or new_session_id()

    session = SessionService(settings)
    history = await session.get_history(session_id)

    await session.add_to_history(session_id, "user", message)

    messages = [
        {
            "role": "system",
            "content": f"You are a financial analyst assistant. The user just analyzed {ticker}. You already have this data: current price=${request.get('current_price', 'unknown')}, recommendation={request.get('recommendation', 'unknown')}, confidence={request.get('confidence_score', 'unknown')}, RSI={request.get('rsi', 'unknown')}, MA50={request.get('ma_50', 'unknown')}, MA200={request.get('ma_200', 'unknown')}, 1Y change={request.get('price_change_pct', 'unknown')}%. Answer questions using this data. Be concise."
        }
    ]

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