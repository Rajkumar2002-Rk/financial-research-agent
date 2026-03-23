from typing import Dict, Any, Optional


# ─── Technical Score (max 25) ────────────────────────────────────────────────

def compute_technical_score(indicators: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    breakdown = {}

    ma_50 = indicators.get("ma_50")
    ma_200 = indicators.get("ma_200")
    rsi = indicators.get("rsi")
    volatility = indicators.get("volatility_30d")

    # Trend: MA50 vs MA200 → +10 or 0
    if ma_50 is not None and ma_200 is not None:
        if ma_50 > ma_200:
            score += 10
            breakdown["trend"] = {
                "score": 10, "max": 10,
                "reason": f"MA50 (${ma_50}) > MA200 (${ma_200}) — bullish trend confirmed",
            }
        else:
            breakdown["trend"] = {
                "score": 0, "max": 10,
                "reason": f"MA50 (${ma_50}) < MA200 (${ma_200}) — bearish trend",
            }
    else:
        breakdown["trend"] = {"score": 0, "max": 10, "reason": "MA data unavailable"}

    # Momentum: RSI → +10, 0, or -5
    if rsi is not None:
        if 50 <= rsi <= 70:
            score += 10
            breakdown["momentum"] = {
                "score": 10, "max": 10,
                "reason": f"RSI {rsi} — healthy momentum (50–70 zone)",
            }
        elif rsi > 80:
            score -= 5
            breakdown["momentum"] = {
                "score": -5, "max": 10,
                "reason": f"RSI {rsi} — overbought (>80), pullback risk",
            }
        elif rsi < 30:
            score -= 5
            breakdown["momentum"] = {
                "score": -5, "max": 10,
                "reason": f"RSI {rsi} — oversold (<30), possible rebound but weak trend",
            }
        else:
            breakdown["momentum"] = {
                "score": 0, "max": 10,
                "reason": f"RSI {rsi} — neutral zone (30–50 or 70–80)",
            }
    else:
        breakdown["momentum"] = {"score": 0, "max": 10, "reason": "RSI unavailable"}

    # Volatility → +5, +2, or 0
    if volatility is not None:
        vol_pct = round(volatility * 100, 1)
        if volatility < 0.25:
            score += 5
            breakdown["volatility"] = {
                "score": 5, "max": 5,
                "reason": f"Low volatility ({vol_pct}%) — stable price action",
            }
        elif volatility < 0.40:
            score += 2
            breakdown["volatility"] = {
                "score": 2, "max": 5,
                "reason": f"Moderate volatility ({vol_pct}%)",
            }
        else:
            breakdown["volatility"] = {
                "score": 0, "max": 5,
                "reason": f"High volatility ({vol_pct}%) — unstable",
            }
    else:
        breakdown["volatility"] = {"score": 0, "max": 5, "reason": "Volatility unavailable"}

    return {"score": max(-5, score), "max": 25, "breakdown": breakdown}


# ─── Fundamental Score (max 40) ──────────────────────────────────────────────

def compute_fundamental_score(fundamentals: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    breakdown = {}

    if not fundamentals.get("data_available"):
        return {
            "score": 0, "max": 40,
            "breakdown": {
                "status": {
                    "score": 0, "max": 40,
                    "reason": "Fundamental data unavailable from source — scored 0/40",
                }
            },
            "missing_fields": fundamentals.get("missing_fields", []),
        }

    # Revenue Growth → 0–10
    rev = fundamentals.get("revenue_growth")
    if rev is not None:
        if rev >= 15:
            score += 10
            breakdown["revenue_growth"] = {"score": 10, "max": 10, "reason": f"Revenue growth {rev}% ≥ 15% — strong"}
        elif rev >= 5:
            score += 6
            breakdown["revenue_growth"] = {"score": 6, "max": 10, "reason": f"Revenue growth {rev}% — moderate"}
        elif rev >= 0:
            score += 2
            breakdown["revenue_growth"] = {"score": 2, "max": 10, "reason": f"Revenue growth {rev}% — weak positive"}
        else:
            breakdown["revenue_growth"] = {"score": 0, "max": 10, "reason": f"Revenue declining ({rev}%)"}
    else:
        breakdown["revenue_growth"] = {"score": 0, "max": 10, "reason": "Revenue growth data missing"}

    # Profit Margin → 0–10
    margin = fundamentals.get("profit_margin")
    if margin is not None:
        if margin >= 20:
            score += 10
            breakdown["profit_margin"] = {"score": 10, "max": 10, "reason": f"Profit margin {margin}% — excellent"}
        elif margin >= 10:
            score += 7
            breakdown["profit_margin"] = {"score": 7, "max": 10, "reason": f"Profit margin {margin}% — healthy"}
        elif margin >= 5:
            score += 4
            breakdown["profit_margin"] = {"score": 4, "max": 10, "reason": f"Profit margin {margin}% — thin"}
        elif margin >= 0:
            score += 1
            breakdown["profit_margin"] = {"score": 1, "max": 10, "reason": f"Profit margin {margin}% — very thin"}
        else:
            breakdown["profit_margin"] = {"score": 0, "max": 10, "reason": f"Negative profit margin ({margin}%)"}
    else:
        breakdown["profit_margin"] = {"score": 0, "max": 10, "reason": "Profit margin data missing"}

    # P/E Ratio → 0–10
    pe = fundamentals.get("pe_ratio")
    if pe is not None:
        if 10 <= pe <= 25:
            score += 10
            breakdown["pe_ratio"] = {"score": 10, "max": 10, "reason": f"P/E {pe} — reasonable valuation"}
        elif 25 < pe <= 40:
            score += 5
            breakdown["pe_ratio"] = {"score": 5, "max": 10, "reason": f"P/E {pe} — elevated but acceptable"}
        elif pe > 40:
            score += 2
            breakdown["pe_ratio"] = {"score": 2, "max": 10, "reason": f"P/E {pe} — expensive valuation"}
        elif 0 < pe < 10:
            score += 7
            breakdown["pe_ratio"] = {"score": 7, "max": 10, "reason": f"P/E {pe} — potentially undervalued"}
        else:
            breakdown["pe_ratio"] = {"score": 0, "max": 10, "reason": f"Negative P/E — not currently profitable"}
    else:
        breakdown["pe_ratio"] = {"score": 0, "max": 10, "reason": "P/E ratio data missing"}

    # Debt/Equity → 0–10
    de = fundamentals.get("debt_to_equity")
    if de is not None:
        if de < 50:
            score += 10
            breakdown["debt_equity"] = {"score": 10, "max": 10, "reason": f"D/E {de}% — low leverage"}
        elif de < 100:
            score += 6
            breakdown["debt_equity"] = {"score": 6, "max": 10, "reason": f"D/E {de}% — manageable debt"}
        elif de < 200:
            score += 3
            breakdown["debt_equity"] = {"score": 3, "max": 10, "reason": f"D/E {de}% — elevated leverage"}
        else:
            breakdown["debt_equity"] = {"score": 0, "max": 10, "reason": f"D/E {de}% — high leverage risk"}
    else:
        breakdown["debt_equity"] = {"score": 0, "max": 10, "reason": "Debt/Equity data missing"}

    return {
        "score": score, "max": 40,
        "breakdown": breakdown,
        "missing_fields": fundamentals.get("missing_fields", []),
    }


# ─── Sentiment Score (max 15) ────────────────────────────────────────────────

def compute_sentiment_score(news_sentiment: str) -> Dict[str, Any]:
    mapping = {
        "positive": {"score": 10, "reason": "Positive recent news — market tailwinds"},
        "neutral":  {"score": 5,  "reason": "Mixed/neutral news sentiment"},
        "negative": {"score": 0,  "reason": "Negative recent news — headwinds present"},
    }
    result = mapping.get(news_sentiment.lower(), {"score": 5, "reason": "Sentiment undetermined — defaulting to neutral"})
    return {"score": result["score"], "max": 15, "reason": result["reason"]}


# ─── Risk Penalty (max -20) ──────────────────────────────────────────────────

def compute_risk_penalty(indicators: Dict[str, Any], news_sentiment: str) -> Dict[str, Any]:
    penalty = 0
    reasons = []

    volatility = indicators.get("volatility_30d")
    if volatility is not None and volatility > 0.40:
        penalty -= 10
        reasons.append(f"High volatility ({round(volatility * 100, 1)}%) → -10")

    if news_sentiment.lower() == "negative":
        penalty -= 10
        reasons.append("Negative news sentiment → -10")

    if not reasons:
        reasons.append("No risk penalties applied")

    return {"penalty": penalty, "min": -20, "reasons": reasons}


# ─── Confidence Score (0–100) ────────────────────────────────────────────────

def compute_confidence(
    fundamental_available: bool,
    fundamental_missing_count: int,
    technical_score: int,
    fundamental_score: int,
    sentiment_score: int,
    news_sentiment: str,
    volatility: Optional[float],
) -> Dict[str, Any]:
    breakdown = {}
    confidence = 0

    # Data Completeness (0–40)
    if fundamental_available:
        completeness = max(0, 40 - (fundamental_missing_count * 7))
    else:
        completeness = 12  # price + technical data only
    confidence += completeness
    breakdown["data_completeness"] = {
        "score": completeness, "max": 40,
        "reason": f"{'Fundamental data available' if fundamental_available else 'No fundamental data'} — {6 - fundamental_missing_count}/6 fields present",
    }

    # Signal Agreement (0–30)
    tech_norm = (technical_score + 5) / 30   # normalise to 0–1 (min possible is -5)
    fund_norm = fundamental_score / 40
    sent_norm = sentiment_score / 15

    normals = [tech_norm, fund_norm, sent_norm]
    avg = sum(normals) / len(normals)
    variance = sum((s - avg) ** 2 for s in normals) / len(normals)
    agreement = max(0, min(30, int(30 - variance * 120)))
    confidence += agreement
    breakdown["signal_agreement"] = {
        "score": agreement, "max": 30,
        "reason": f"Technical, fundamental, sentiment variance = {round(variance, 3)} — {'low' if variance < 0.05 else 'moderate' if variance < 0.15 else 'high'} disagreement",
    }

    # Volatility Penalty (0 to -20)
    vol_penalty = 0
    if volatility is not None:
        if volatility > 0.50:
            vol_penalty = -20
        elif volatility > 0.40:
            vol_penalty = -15
        elif volatility > 0.30:
            vol_penalty = -8
    confidence += vol_penalty
    breakdown["volatility_penalty"] = {
        "score": vol_penalty,
        "reason": f"Annualised volatility {round((volatility or 0) * 100, 1)}%",
    }

    # News Uncertainty Penalty (0 to -10)
    news_penalty = -10 if news_sentiment == "negative" else 0
    confidence += news_penalty
    breakdown["news_uncertainty"] = {
        "score": news_penalty,
        "reason": f"News sentiment: {news_sentiment}",
    }

    final = max(0, min(100, confidence))
    return {"confidence": final, "breakdown": breakdown}


# ─── Final Decision ───────────────────────────────────────────────────────────

def make_deterministic_decision(total_score: int, confidence: int) -> str:
    if confidence < 40:
        return "INSUFFICIENT_DATA"
    if total_score >= 60:
        return "BUY"
    elif total_score >= 40:
        return "HOLD"
    else:
        return "SELL"
