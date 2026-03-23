from typing import Dict, Any, Optional, List


# ─── Time Horizon Weight Profiles ────────────────────────────────────────────

TIME_HORIZON_WEIGHTS: Dict[str, Dict[str, Any]] = {
    "short_term": {
        "technical":   1.5,   # Momentum & MAs matter most for near-term moves
        "fundamental": 0.5,   # Fundamentals are slow-moving — less relevant
        "sentiment":   1.2,   # News has immediate price impact
        "label": "Short-Term (1–4 weeks)",
    },
    "long_term": {
        "technical":   0.7,   # Technicals are noise over multi-year horizons
        "fundamental": 1.5,   # Earnings, margins, debt matter most long-term
        "sentiment":   0.8,   # News fades; fundamentals persist
        "label": "Long-Term (1–5 years)",
    },
    "default": {
        "technical":   1.0,
        "fundamental": 1.0,
        "sentiment":   1.0,
        "label": "Balanced (default)",
    },
}


# ─── Technical Score (dynamic max — excludes missing components) ──────────────

def compute_technical_score(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score = sum of available component scores.
    max   = sum of component maxes ONLY for components with data.
    Missing components are excluded from both score and max — they do NOT
    reduce the normalized score.
    """
    score = 0
    available_max = 0
    breakdown = {}
    missing_components: List[str] = []

    ma_50 = indicators.get("ma_50")
    ma_200 = indicators.get("ma_200")
    rsi = indicators.get("rsi")
    volatility = indicators.get("volatility_30d")

    # ── Trend: MA50 vs MA200 → 0 or +10 (component max 10) ──────────────────
    if ma_50 is not None and ma_200 is not None:
        available_max += 10
        if ma_50 > ma_200:
            score += 10
            breakdown["trend"] = {
                "score": 10, "max": 10,
                "reason": f"MA50 (${ma_50:.2f}) > MA200 (${ma_200:.2f}) — bullish trend confirmed",
            }
        else:
            breakdown["trend"] = {
                "score": 0, "max": 10,
                "reason": f"MA50 (${ma_50:.2f}) < MA200 (${ma_200:.2f}) — bearish trend",
            }
    else:
        missing_components.append("trend")
        breakdown["trend"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "MA data unavailable — component excluded from scoring",
        }

    # ── Momentum: RSI → −5, 0, or +10 (component max 10) ───────────────────
    if rsi is not None:
        available_max += 10
        rsi_r = round(rsi, 1)
        if 50 <= rsi <= 70:
            score += 10
            breakdown["momentum"] = {
                "score": 10, "max": 10,
                "reason": f"RSI {rsi_r} — healthy momentum (50–70 zone)",
            }
        elif rsi > 80:
            score -= 5
            breakdown["momentum"] = {
                "score": -5, "max": 10,
                "reason": f"RSI {rsi_r} — overbought (>80), pullback risk",
            }
        elif rsi < 30:
            score -= 5
            breakdown["momentum"] = {
                "score": -5, "max": 10,
                "reason": f"RSI {rsi_r} — oversold (<30), possible rebound but weak trend",
            }
        else:
            breakdown["momentum"] = {
                "score": 0, "max": 10,
                "reason": f"RSI {rsi_r} — neutral zone (30–50 or 70–80)",
            }
    else:
        missing_components.append("momentum")
        breakdown["momentum"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "RSI unavailable — component excluded from scoring",
        }

    # ── Volatility → 0, +2, or +5 (component max 5) ─────────────────────────
    if volatility is not None:
        available_max += 5
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
                "reason": f"High volatility ({vol_pct}%) — unstable price action",
            }
    else:
        missing_components.append("volatility")
        breakdown["volatility"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "Volatility data unavailable — component excluded from scoring",
        }

    return {
        "score": score,
        "max": available_max,
        "breakdown": breakdown,
        "missing_components": missing_components,
    }


# ─── Fundamental Score (dynamic max — excludes missing fields) ────────────────

def compute_fundamental_score(fundamentals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Each fundamental field is worth 10 points.
    max = 10 × number_of_available_fields.
    Missing fields are excluded from both score and max.
    If fundamental data is completely unavailable, max = 0 (excluded entirely).
    """
    score = 0
    available_max = 0
    breakdown = {}
    missing_components: List[str] = []

    if not fundamentals.get("data_available"):
        return {
            "score": 0, "max": 0,
            "breakdown": {
                "status": {
                    "score": 0, "max": 0, "excluded": True,
                    "reason": "Fundamental data unavailable — entire component excluded from scoring",
                }
            },
            "missing_fields": fundamentals.get("missing_fields", []),
            "missing_components": ["revenue_growth", "profit_margin", "pe_ratio", "debt_equity"],
        }

    # ── Revenue Growth → 0–10 ─────────────────────────────────────────────────
    rev = fundamentals.get("revenue_growth")
    if rev is not None:
        available_max += 10
        if rev >= 15:
            score += 10
            breakdown["revenue_growth"] = {
                "score": 10, "max": 10,
                "reason": f"Revenue growth {rev}% ≥ 15% — strong",
            }
        elif rev >= 5:
            score += 6
            breakdown["revenue_growth"] = {
                "score": 6, "max": 10,
                "reason": f"Revenue growth {rev}% — moderate",
            }
        elif rev >= 0:
            score += 2
            breakdown["revenue_growth"] = {
                "score": 2, "max": 10,
                "reason": f"Revenue growth {rev}% — weak positive",
            }
        else:
            breakdown["revenue_growth"] = {
                "score": 0, "max": 10,
                "reason": f"Revenue declining ({rev}%)",
            }
    else:
        missing_components.append("revenue_growth")
        breakdown["revenue_growth"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "Revenue growth data missing — excluded from scoring",
        }

    # ── Profit Margin → 0–10 ──────────────────────────────────────────────────
    margin = fundamentals.get("profit_margin")
    if margin is not None:
        available_max += 10
        if margin >= 20:
            score += 10
            breakdown["profit_margin"] = {
                "score": 10, "max": 10,
                "reason": f"Profit margin {margin}% — excellent",
            }
        elif margin >= 10:
            score += 7
            breakdown["profit_margin"] = {
                "score": 7, "max": 10,
                "reason": f"Profit margin {margin}% — healthy",
            }
        elif margin >= 5:
            score += 4
            breakdown["profit_margin"] = {
                "score": 4, "max": 10,
                "reason": f"Profit margin {margin}% — thin",
            }
        elif margin >= 0:
            score += 1
            breakdown["profit_margin"] = {
                "score": 1, "max": 10,
                "reason": f"Profit margin {margin}% — very thin",
            }
        else:
            breakdown["profit_margin"] = {
                "score": 0, "max": 10,
                "reason": f"Negative profit margin ({margin}%)",
            }
    else:
        missing_components.append("profit_margin")
        breakdown["profit_margin"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "Profit margin data missing — excluded from scoring",
        }

    # ── P/E Ratio → 0–10 ──────────────────────────────────────────────────────
    pe = fundamentals.get("pe_ratio")
    if pe is not None:
        available_max += 10
        if 10 <= pe <= 25:
            score += 10
            breakdown["pe_ratio"] = {
                "score": 10, "max": 10,
                "reason": f"P/E {pe} — reasonable valuation",
            }
        elif 25 < pe <= 40:
            score += 5
            breakdown["pe_ratio"] = {
                "score": 5, "max": 10,
                "reason": f"P/E {pe} — elevated but acceptable",
            }
        elif pe > 40:
            score += 2
            breakdown["pe_ratio"] = {
                "score": 2, "max": 10,
                "reason": f"P/E {pe} — expensive valuation",
            }
        elif 0 < pe < 10:
            score += 7
            breakdown["pe_ratio"] = {
                "score": 7, "max": 10,
                "reason": f"P/E {pe} — potentially undervalued",
            }
        else:
            breakdown["pe_ratio"] = {
                "score": 0, "max": 10,
                "reason": f"Negative P/E — not currently profitable",
            }
    else:
        missing_components.append("pe_ratio")
        breakdown["pe_ratio"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "P/E ratio data missing — excluded from scoring",
        }

    # ── Debt/Equity → 0–10 ────────────────────────────────────────────────────
    de = fundamentals.get("debt_to_equity")
    if de is not None:
        available_max += 10
        if de < 50:
            score += 10
            breakdown["debt_equity"] = {
                "score": 10, "max": 10,
                "reason": f"D/E {de}% — low leverage",
            }
        elif de < 100:
            score += 6
            breakdown["debt_equity"] = {
                "score": 6, "max": 10,
                "reason": f"D/E {de}% — manageable debt",
            }
        elif de < 200:
            score += 3
            breakdown["debt_equity"] = {
                "score": 3, "max": 10,
                "reason": f"D/E {de}% — elevated leverage",
            }
        else:
            breakdown["debt_equity"] = {
                "score": 0, "max": 10,
                "reason": f"D/E {de}% — high leverage risk",
            }
    else:
        missing_components.append("debt_equity")
        breakdown["debt_equity"] = {
            "score": 0, "max": 0, "excluded": True,
            "reason": "Debt/Equity data missing — excluded from scoring",
        }

    return {
        "score": score,
        "max": available_max,
        "breakdown": breakdown,
        "missing_fields": fundamentals.get("missing_fields", []),
        "missing_components": missing_components,
    }


# ─── Sentiment Score (max 15 — always scoreable) ─────────────────────────────

def compute_sentiment_score(news_sentiment: str) -> Dict[str, Any]:
    """Sentiment affects ONLY this score component — not the risk penalty."""
    mapping = {
        "positive": {"score": 10, "reason": "Positive recent news — market tailwinds"},
        "neutral":  {"score": 5,  "reason": "Mixed/neutral news sentiment"},
        "negative": {"score": 0,  "reason": "Negative recent news — headwinds present"},
    }
    result = mapping.get(
        news_sentiment.lower(),
        {"score": 5, "reason": "Sentiment undetermined — defaulting to neutral"},
    )
    return {"score": result["score"], "max": 15, "reason": result["reason"]}


# ─── Risk Penalty (volatility only — sentiment removed to prevent double-count) ─

def compute_risk_penalty(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """
    Risk penalty is VOLATILITY ONLY.
    Sentiment was removed: it already affects the 0–15 sentiment score.
    Double-penalising the same signal biased every negative-news stock toward SELL.
    """
    penalty = 0
    reasons = []

    volatility = indicators.get("volatility_30d")
    if volatility is not None and volatility > 0.40:
        penalty -= 10
        reasons.append(f"High volatility ({round(volatility * 100, 1)}%) → -10")

    if not reasons:
        reasons.append("No risk penalties applied")

    return {"penalty": penalty, "min": -10, "reasons": reasons}


# ─── Time Horizon Weight Application ─────────────────────────────────────────

def apply_time_horizon_weights(
    tech_score: int, tech_max: int,
    fund_score: int, fund_max: int,
    sent_score: int, sent_max: int,
    time_horizon: str = "default",
) -> Dict[str, Any]:
    """
    Rescales component scores and maxes by time-horizon weights.
    Returns adjusted values used for total_score and max_possible_score.
    """
    weights = TIME_HORIZON_WEIGHTS.get(time_horizon, TIME_HORIZON_WEIGHTS["default"])
    w_tech = weights["technical"]
    w_fund = weights["fundamental"]
    w_sent = weights["sentiment"]

    return {
        "technical": {
            "score": round(tech_score * w_tech, 2),
            "max":   round(tech_max   * w_tech, 2),
            "weight": w_tech,
        },
        "fundamental": {
            "score": round(fund_score * w_fund, 2),
            "max":   round(fund_max   * w_fund, 2),
            "weight": w_fund,
        },
        "sentiment": {
            "score": round(sent_score * w_sent, 2),
            "max":   round(sent_max   * w_sent, 2),
            "weight": w_sent,
        },
        "weights_used": {k: v for k, v in weights.items() if k != "label"},
        "label": weights["label"],
        "time_horizon": time_horizon,
    }


# ─── Normalized Score ─────────────────────────────────────────────────────────

def compute_normalized_score(total_score: float, max_possible_score: float) -> float:
    """Returns score on a 0–100 scale. Clipped to [-20, 100] for display."""
    if max_possible_score <= 0:
        return 0.0
    raw = (total_score / max_possible_score) * 100
    return round(max(-20.0, min(100.0, raw)), 1)


# ─── Conflict Detection ───────────────────────────────────────────────────────

def detect_conflict(
    tech_score: float, tech_max: float,
    fund_score: float, fund_max: float,
    sent_score: float, sent_max: float,
    fundamental_available: bool,
) -> bool:
    """
    Returns True when component signals disagree significantly (variance > 0.15).
    Only includes signals that have data — avoids false conflicts from missing data.
    """
    normals: List[float] = []

    if tech_max > 0:
        normals.append(tech_score / tech_max)
    if fund_max > 0 and fundamental_available:
        normals.append(fund_score / fund_max)
    if sent_max > 0:
        normals.append(sent_score / sent_max)

    if len(normals) < 2:
        return False

    avg = sum(normals) / len(normals)
    variance = sum((s - avg) ** 2 for s in normals) / len(normals)
    return variance > 0.15


# ─── Confidence Score (0–100) ─────────────────────────────────────────────────

def compute_confidence(
    fundamental_available: bool,
    fundamental_missing_count: int,
    technical_missing_count: int,
    technical_score: float,
    technical_max: float,
    fundamental_score: float,
    fundamental_max: float,
    sentiment_score: float,
    news_sentiment: str,
    volatility: Optional[float],
) -> Dict[str, Any]:
    """
    Enhanced confidence scoring:
    - Data Completeness (0–40): based on available data sources
    - Signal Agreement (0–30): variance-based, excluding missing signals
    - Missing Data Penalty (0 to −15): additional penalty for sparse data
    - Signal Consistency Bonus (+5): if all signals agree strongly
    - Volatility Penalty (0 to −20): high vol reduces predictability
    - News Uncertainty Penalty (0 to −10): negative news = less certainty
    """
    breakdown = {}
    confidence = 0

    # ── Data Completeness (0–40) ──────────────────────────────────────────────
    if fundamental_available:
        completeness = max(0, 40 - (fundamental_missing_count * 6))
    else:
        # We have OHLCV + technical indicators — meaningful but incomplete
        completeness = 28
    confidence += completeness
    breakdown["data_completeness"] = {
        "score": completeness, "max": 40,
        "reason": (
            f"{'Fundamental data available' if fundamental_available else 'Technical-only analysis'} — "
            f"{6 - fundamental_missing_count if fundamental_available else 0}/6 fundamental fields, "
            f"{3 - technical_missing_count}/3 technical indicators present"
        ),
    }

    # ── Missing Data Penalty (0 to −15) ──────────────────────────────────────
    # Extra penalty when significant portions of the model are missing
    missing_penalty = 0
    total_missing = fundamental_missing_count + technical_missing_count
    if not fundamental_available:
        total_missing += 4  # all fundamental fields missing
    if total_missing >= 6:
        missing_penalty = -15
    elif total_missing >= 4:
        missing_penalty = -8
    elif total_missing >= 2:
        missing_penalty = -3
    confidence += missing_penalty
    breakdown["missing_data_penalty"] = {
        "score": missing_penalty,
        "reason": f"{total_missing} total components missing across technical + fundamental",
    }

    # ── Signal Agreement (0–30) ───────────────────────────────────────────────
    normals: List[float] = []
    if technical_max > 0:
        normals.append(technical_score / technical_max)
    if fundamental_available and fundamental_max > 0:
        normals.append(fundamental_score / fundamental_max)
    sent_max = 15.0
    normals.append(sentiment_score / sent_max)

    if len(normals) >= 2:
        avg = sum(normals) / len(normals)
        variance = sum((s - avg) ** 2 for s in normals) / len(normals)
        agreement = max(0, min(30, int(30 - variance * 120)))
        variance_label = "low" if variance < 0.05 else "moderate" if variance < 0.15 else "high"
    else:
        variance = 0.0
        agreement = 15  # neutral when only one signal
        variance_label = "unknown"

    confidence += agreement
    breakdown["signal_agreement"] = {
        "score": agreement, "max": 30,
        "reason": f"Signal variance = {round(variance, 3)} — {variance_label} disagreement across {len(normals)} signals",
    }

    # ── Signal Consistency Bonus (+5) ─────────────────────────────────────────
    consistency_bonus = 0
    if len(normals) >= 2 and variance < 0.05:
        consistency_bonus = 5
    confidence += consistency_bonus
    breakdown["consistency_bonus"] = {
        "score": consistency_bonus,
        "reason": "All signals strongly aligned" if consistency_bonus > 0 else "No consistency bonus (signals diverge)",
    }

    # ── Volatility Penalty (0 to −20) ─────────────────────────────────────────
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

    # ── News Uncertainty Penalty (0 to −10) ───────────────────────────────────
    # This affects CONFIDENCE (our certainty about the analysis), not the score itself
    news_penalty = -10 if news_sentiment.lower() == "negative" else 0
    confidence += news_penalty
    breakdown["news_uncertainty"] = {
        "score": news_penalty,
        "reason": f"News sentiment: {news_sentiment}",
    }

    final = max(0, min(100, confidence))
    return {"confidence": final, "breakdown": breakdown}


# ─── Final Decision (uses normalized_score 0–100) ────────────────────────────

def make_deterministic_decision(
    normalized_score: float,
    confidence: int,
    conflict_detected: bool = False,
) -> str:
    """
    Thresholds operate on normalized_score (0–100):
      BUY   ≥ 70
      HOLD  40–69  (includes ±5 buffer zones: 65–69 below BUY, 40–44 above SELL)
      SELL  < 40

    The ±5 buffer (compared to legacy 45 SELL threshold) means borderline
    signals default to HOLD — the conservative, non-actionable option.

    Conflict override: if signals strongly disagree AND score is in the
    35–55 uncertainty band, override to HOLD regardless of raw score.
    """
    if confidence < 20:
        return "INSUFFICIENT_DATA"

    # Conflict-aware stability override
    if conflict_detected and 35.0 <= normalized_score <= 55.0:
        return "HOLD"

    # Main decision ladder
    if normalized_score >= 70.0:
        return "BUY"
    elif normalized_score >= 40.0:
        return "HOLD"
    else:
        return "SELL"
