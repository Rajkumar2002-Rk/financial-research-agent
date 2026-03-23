import requests
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

EMPTY_RESULT = {
    "pe_ratio": None,
    "eps": None,
    "revenue_growth": None,
    "profit_margin": None,
    "debt_to_equity": None,
    "free_cash_flow": None,
    "market_cap": None,
    "data_available": False,
    "missing_fields": ["pe_ratio", "eps", "revenue_growth", "profit_margin", "debt_to_equity", "free_cash_flow"],
}


def fetch_fundamental_data(ticker: str) -> Dict[str, Any]:
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
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {
            "modules": "defaultKeyStatistics,financialData,summaryDetail"
        }
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)

        if resp.status_code != 200:
            logger.warning("fundamental_fetch_http_error", ticker=ticker, status=resp.status_code)
            return {**EMPTY_RESULT}

        data = resp.json()
        result_data = data.get("quoteSummary", {}).get("result", [])
        if not result_data:
            return {**EMPTY_RESULT}

        summary = result_data[0]
        key_stats = summary.get("defaultKeyStatistics", {})
        fin_data = summary.get("financialData", {})
        summary_detail = summary.get("summaryDetail", {})

        def safe(obj, key):
            val = obj.get(key, {})
            if isinstance(val, dict):
                return val.get("raw")
            return val

        pe = safe(summary_detail, "trailingPE") or safe(key_stats, "forwardPE")
        eps = safe(key_stats, "trailingEps")
        rev_growth = safe(fin_data, "revenueGrowth")
        profit_margin = safe(fin_data, "profitMargins")
        de_ratio = safe(fin_data, "debtToEquity")
        fcf = safe(fin_data, "freeCashflow")
        market_cap = safe(summary_detail, "marketCap")

        result["pe_ratio"] = round(float(pe), 2) if pe is not None else None
        result["eps"] = round(float(eps), 2) if eps is not None else None
        result["revenue_growth"] = round(float(rev_growth) * 100, 2) if rev_growth is not None else None
        result["profit_margin"] = round(float(profit_margin) * 100, 2) if profit_margin is not None else None
        result["debt_to_equity"] = round(float(de_ratio), 2) if de_ratio is not None else None
        result["free_cash_flow"] = int(fcf) if fcf is not None else None
        result["market_cap"] = int(market_cap) if market_cap is not None else None

        missing = [k for k in ["pe_ratio", "eps", "revenue_growth", "profit_margin", "debt_to_equity", "free_cash_flow"]
                   if result.get(k) is None]
        result["missing_fields"] = missing
        result["data_available"] = len(missing) < 6

        logger.info("fundamental_data_fetched", ticker=ticker, missing_count=len(missing))
        return result

    except Exception as e:
        logger.error("fundamental_fetch_failed", ticker=ticker, error=str(e))
        return {**EMPTY_RESULT}
