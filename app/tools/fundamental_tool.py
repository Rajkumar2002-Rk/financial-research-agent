import requests
from typing import Dict, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
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


def _safe_float(val) -> float | None:
    """Parse a value to float, return None if empty / non-numeric."""
    try:
        f = float(val)
        return f if f == f else None   # NaN check
    except (TypeError, ValueError):
        return None


def fetch_fundamental_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch fundamental data from Alpha Vantage OVERVIEW endpoint.
    Works on EC2 — Alpha Vantage does not block cloud IPs.
    Free tier: 25 requests / day  |  5 requests / minute.

    Returns P/E, EPS, revenue growth, profit margin from OVERVIEW.
    D/E and FCF require separate BALANCE_SHEET / CASH_FLOW calls
    which would consume 2 extra daily quota slots; they are fetched
    only when the key is present and degrade gracefully if rate-limited.
    """
    settings = get_settings()

    if not settings.ALPHA_VANTAGE_API_KEY:
        logger.warning("alpha_vantage_key_missing", ticker=ticker)
        return {**EMPTY_RESULT}

    result: Dict[str, Any] = {k: None for k in FIELD_KEYS}
    result["market_cap"] = None
    result["data_available"] = False
    result["missing_fields"] = []

    # ── OVERVIEW call ─────────────────────────────────────────────────────────
    try:
        resp = requests.get(
            ALPHA_VANTAGE_BASE,
            params={
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_API_KEY,
            },
            timeout=12,
        )

        if resp.status_code != 200:
            logger.warning("av_overview_http_error", ticker=ticker, status=resp.status_code)
            return {**EMPTY_RESULT}

        data = resp.json()

        # Rate-limit or wrong key returns {"Information": "..."}
        if "Information" in data or "Note" in data:
            logger.warning("av_rate_limited", ticker=ticker, msg=data.get("Information") or data.get("Note"))
            return {**EMPTY_RESULT}

        if not data.get("Symbol"):
            logger.warning("av_unknown_ticker", ticker=ticker)
            return {**EMPTY_RESULT}

        # P/E — prefer trailing, fall back to forward
        pe_raw = _safe_float(data.get("TrailingPE")) or _safe_float(data.get("ForwardPE"))
        result["pe_ratio"] = round(pe_raw, 2) if pe_raw else None

        result["eps"] = _safe_float(data.get("EPS"))
        if result["eps"] is not None:
            result["eps"] = round(result["eps"], 2)

        # Revenue growth is a decimal in AV (0.12 = 12%) — convert to %
        rev_raw = _safe_float(data.get("QuarterlyRevenueGrowthYOY"))
        result["revenue_growth"] = round(rev_raw * 100, 2) if rev_raw is not None else None

        # Profit margin is also a decimal
        margin_raw = _safe_float(data.get("ProfitMargin"))
        result["profit_margin"] = round(margin_raw * 100, 2) if margin_raw is not None else None

        # Market cap (not in scoring but useful for display)
        mc_raw = _safe_float(data.get("MarketCapitalization"))
        result["market_cap"] = int(mc_raw) if mc_raw else None

        logger.info("av_overview_fetched", ticker=ticker,
                    pe=result["pe_ratio"], eps=result["eps"])

    except Exception as e:
        logger.error("av_overview_failed", ticker=ticker, error=str(e))
        return {**EMPTY_RESULT}

    # ── INCOME_STATEMENT for additional revenue metrics (optional) ────────────
    # ── BALANCE_SHEET for D/E ────────────────────────────────────────────────
    try:
        bs_resp = requests.get(
            ALPHA_VANTAGE_BASE,
            params={
                "function": "BALANCE_SHEET",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_API_KEY,
            },
            timeout=12,
        )
        if bs_resp.status_code == 200:
            bs_data = bs_resp.json()
            if "Information" not in bs_data and "Note" not in bs_data:
                reports = bs_data.get("annualReports") or bs_data.get("quarterlyReports") or []
                if reports:
                    latest = reports[0]
                    total_liabilities = _safe_float(latest.get("totalLiabilities"))
                    shareholder_equity = _safe_float(latest.get("totalShareholderEquity"))
                    if total_liabilities and shareholder_equity and shareholder_equity != 0:
                        de = (total_liabilities / shareholder_equity) * 100
                        result["debt_to_equity"] = round(de, 2)
    except Exception as e:
        logger.warning("av_balance_sheet_failed", ticker=ticker, error=str(e))

    # ── CASH_FLOW for FCF ────────────────────────────────────────────────────
    try:
        cf_resp = requests.get(
            ALPHA_VANTAGE_BASE,
            params={
                "function": "CASH_FLOW",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_API_KEY,
            },
            timeout=12,
        )
        if cf_resp.status_code == 200:
            cf_data = cf_resp.json()
            if "Information" not in cf_data and "Note" not in cf_data:
                reports = cf_data.get("annualReports") or cf_data.get("quarterlyReports") or []
                if reports:
                    latest = reports[0]
                    op_cf = _safe_float(latest.get("operatingCashflow"))
                    capex = _safe_float(latest.get("capitalExpenditures"))
                    if op_cf is not None and capex is not None:
                        result["free_cash_flow"] = int(op_cf - abs(capex))
    except Exception as e:
        logger.warning("av_cash_flow_failed", ticker=ticker, error=str(e))

    # ── Finalise ──────────────────────────────────────────────────────────────
    missing = [k for k in FIELD_KEYS if result.get(k) is None]
    result["missing_fields"] = missing
    result["data_available"] = len(missing) < 6   # at least 1 field present

    logger.info("fundamental_data_complete", ticker=ticker,
                available=result["data_available"], missing_count=len(missing))
    return result
