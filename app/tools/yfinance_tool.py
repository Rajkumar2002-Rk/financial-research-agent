import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"


def fetch_stock_data(ticker: str, period: str = "1y") -> Dict[str, Any]:
    """
    Fetch daily OHLCV price data from Alpha Vantage TIME_SERIES_DAILY.
    Works reliably from EC2 — Alpha Vantage does not block cloud IPs.
    """
    settings = get_settings()

    try:
        resp = requests.get(
            ALPHA_VANTAGE_BASE,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",      # up to 20 years; we slice to 1y below
                "apikey": settings.ALPHA_VANTAGE_API_KEY,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        # Rate-limit or invalid key
        if "Information" in data or "Note" in data:
            msg = data.get("Information") or data.get("Note")
            logger.warning("av_price_rate_limited", ticker=ticker, msg=msg)
            raise ValueError(f"Alpha Vantage rate limit or invalid key: {msg}")

        time_series = data.get("Time Series (Daily)")
        if not time_series:
            raise ValueError(f"No price data found for ticker '{ticker}'")

        # Filter to last 365 days
        cutoff = datetime.now() - timedelta(days=365)
        history_records = []
        for date_str, values in sorted(time_series.items()):
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date < cutoff:
                continue
            history_records.append({
                "date": date_str,
                "open":   round(float(values["1. open"]),  2),
                "high":   round(float(values["2. high"]),  2),
                "low":    round(float(values["3. low"]),   2),
                "close":  round(float(values["4. close"]), 2),
                "volume": int(float(values["5. volume"])),
            })

        if not history_records:
            raise ValueError(f"No price data found for ticker '{ticker}'")

        closes = [r["close"] for r in history_records]
        highs  = [r["high"]  for r in history_records]
        lows   = [r["low"]   for r in history_records]

        current_price  = closes[-1]
        week_52_high   = round(max(highs),  2)
        week_52_low    = round(min(lows),   2)

        logger.info("price_data_fetched", ticker=ticker, records=len(history_records))

        return {
            "ticker":        ticker,
            "company_name":  ticker,
            "current_price": current_price,
            "currency":      "USD",
            "sector":        "N/A",
            "market_cap":    None,
            "52_week_high":  week_52_high,
            "52_week_low":   week_52_low,
            "price_history": history_records,
        }

    except Exception as e:
        logger.error("stock_fetch_failed", ticker=ticker, error=str(e))
        raise
