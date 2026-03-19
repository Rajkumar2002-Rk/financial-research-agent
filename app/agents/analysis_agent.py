import pandas as pd
import numpy as np
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_indicators(validated_market_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    try:
        history = validated_market_data.get("price_history", [])

        if len(history) < 10:
            logger.warning("insufficient_history", session_id=session_id, rows=len(history))
            return {}

        df = pd.DataFrame(history)
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])

        ma_50 = round(float(df["close"].tail(50).mean()), 2) if len(df) >= 50 else None
        ma_200 = round(float(df["close"].tail(200).mean()), 2) if len(df) >= 200 else None

        current_price = float(df["close"].iloc[-1])
        start_price = float(df["close"].iloc[0])
        price_change_pct = round(((current_price - start_price) / start_price) * 100, 2)

        daily_returns = df["close"].pct_change().dropna()
        volatility_30d = round(float(daily_returns.tail(30).std() * np.sqrt(252)), 4) if len(daily_returns) >= 30 else None

        rsi = calculate_rsi(df["close"])

        volume_avg_30d = round(float(df["volume"].tail(30).mean()), 0) if len(df) >= 30 else None

        golden_cross = None
        death_cross = None
        if ma_50 and ma_200:
            golden_cross = ma_50 > ma_200
            death_cross = ma_50 < ma_200

        trend = determine_trend(current_price, ma_50, ma_200, price_change_pct, rsi)

        indicators = {
            "ma_50": ma_50,
            "ma_200": ma_200,
            "rsi": rsi,
            "volatility_30d": volatility_30d,
            "price_change_pct": price_change_pct,
            "volume_avg_30d": volume_avg_30d,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
        }

        logger.info("indicators_calculated", session_id=session_id, trend=trend)
        return {"indicators": indicators, "trend": trend}

    except Exception as e:
        logger.error("indicator_calculation_failed", session_id=session_id, error=str(e))
        return {}


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def determine_trend(price, ma_50, ma_200, price_change_pct, rsi) -> str:
    bullish_signals = 0
    bearish_signals = 0

    if ma_50 and ma_200:
        if ma_50 > ma_200:
            bullish_signals += 1
        else:
            bearish_signals += 1

    if price_change_pct > 5:
        bullish_signals += 1
    elif price_change_pct < -5:
        bearish_signals += 1

    if rsi and rsi < 30:
        bullish_signals += 1
    elif rsi and rsi > 70:
        bearish_signals += 1

    if bullish_signals > bearish_signals:
        return "Bullish"
    elif bearish_signals > bullish_signals:
        return "Bearish"
    else:
        return "Neutral"