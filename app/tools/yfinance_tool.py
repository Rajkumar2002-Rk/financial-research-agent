import yfinance as yf
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_stock_data(ticker: str, period: str = "1y") -> Dict[str, Any]:
    try:
        history = yf.download(
            ticker,
            period=period,
            auto_adjust=True,
            progress=False,
        )

        if history.empty:
            raise ValueError(f"No price data found for ticker '{ticker}'")

        history.columns = [col[0] if isinstance(col, tuple) else col for col in history.columns]
        current_price = round(float(history["Close"].iloc[-1]), 2)

        history_records = []
        for date, row in history.iterrows():
            history_records.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return {
            "ticker": ticker,
            "company_name": ticker,
            "current_price": current_price,
            "currency": "USD",
            "sector": "N/A",
            "market_cap": None,
            "52_week_high": round(float(history["High"].max()), 2),
            "52_week_low": round(float(history["Low"].min()), 2),
            "price_history": history_records,
        }

    except Exception as e:
        logger.error("yfinance_fetch_failed", ticker=ticker, error=str(e))
        raise