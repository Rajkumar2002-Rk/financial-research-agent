import yfinance as yf
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

FIELD_KEYS = ["pe_ratio", "eps", "revenue_growth", "profit_margin", "debt_to_equity", "free_cash_flow"]

EMPTY_RESULT = {
    "pe_ratio": None,
    "eps": None,
    "revenue_growth": None,
    "profit_margin": None,
    "debt_to_equity": None,
    "free_cash_flow": None,
    "market_cap": None,
    "data_available": False,
    "missing_fields": FIELD_KEYS[:],
}


def fetch_fundamental_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch fundamental data using yfinance Ticker.info.
    yfinance handles Yahoo Finance crumb/cookie auth automatically,
    which plain requests.get() cannot do on cloud IPs.
    """
    result = {
        "pe_ratio": None,
        "eps": None,
        "revenue_growth": None,
        "profit_margin": None,
        "debt_to_equity": None,
        "free_cash_flow": None,
        "market_cap": None,
        "data_available": False,
        "missing_fields": [],
    }

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # If yfinance returns an empty or minimal dict it means the request failed
        if not info or len(info) < 5:
            logger.warning("fundamental_data_empty", ticker=ticker, keys=len(info) if info else 0)
            return {**EMPTY_RESULT}

        # P/E — prefer trailing, fall back to forward
        pe = info.get("trailingPE") or info.get("forwardPE")
        eps = info.get("trailingEps")

        # Revenue growth comes as a decimal (0.12 = 12%) — convert to %
        rev_raw = info.get("revenueGrowth")
        rev_growth = round(float(rev_raw) * 100, 2) if rev_raw is not None else None

        # Profit margin comes as a decimal — convert to %
        margin_raw = info.get("profitMargins")
        profit_margin = round(float(margin_raw) * 100, 2) if margin_raw is not None else None

        # D/E is already a percentage in yfinance info
        de = info.get("debtToEquity")

        fcf = info.get("freeCashflow")
        market_cap = info.get("marketCap")

        result["pe_ratio"]       = round(float(pe), 2)    if pe           is not None else None
        result["eps"]            = round(float(eps), 2)   if eps          is not None else None
        result["revenue_growth"] = rev_growth
        result["profit_margin"]  = profit_margin
        result["debt_to_equity"] = round(float(de), 2)    if de           is not None else None
        result["free_cash_flow"] = int(fcf)               if fcf          is not None else None
        result["market_cap"]     = int(market_cap)        if market_cap   is not None else None

        missing = [k for k in FIELD_KEYS if result.get(k) is None]
        result["missing_fields"] = missing
        result["data_available"] = len(missing) < 6

        logger.info("fundamental_data_fetched", ticker=ticker,
                    available=result["data_available"], missing_count=len(missing))
        return result

    except Exception as e:
        logger.error("fundamental_fetch_failed", ticker=ticker, error=str(e))
        return {**EMPTY_RESULT}
