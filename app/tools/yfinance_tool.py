import pandas_datareader as pdr
from datetime import datetime, timedelta
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_stock_data(ticker: str, period: str = "1y") -> Dict[str, Any]:
    try:
        end = datetime.now()
        start = end - timedelta(days=365)

        df = pdr.data.DataReader(ticker, "stooq", start, end)

        if df.empty:
            raise ValueError(f"No price data found for ticker '{ticker}'")

        df = df.sort_index()
        df = df.dropna()

        current_price = round(float(df["Close"].iloc[-1]), 2)
        week_52_high = round(float(df["High"].max()), 2)
        week_52_low = round(float(df["Low"].min()), 2)

        history_records = []
        for date, row in df.iterrows():
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
            "52_week_high": week_52_high,
            "52_week_low": week_52_low,
            "price_history": history_records,
        }

    except Exception as e:
        logger.error("stock_fetch_failed", ticker=ticker, error=str(e))
        raise
