"""Deterministic ranking and qualification for trade candidates."""

from src.config import load_config


def _load_thresholds() -> dict:
    """Load scoring thresholds from config, with defaults."""
    config = load_config()
    ranking_cfg = config.get("ranking", {})
    return {
        "packet_worthy": ranking_cfg.get("packet_worthy_threshold", 70),
        "watchlist": ranking_cfg.get("watchlist_threshold", 45),
    }


def _score_ticker(features: dict) -> float:
    """Score a single ticker on a 0-100 scale. Deterministic, no randomness."""
    score = 0.0

    # Trend state: strong_uptrend=+30, uptrend=+20, neutral=+5
    trend = features.get("trend_state", "")
    if trend == "strong_uptrend":
        score += 30
    elif trend == "uptrend":
        score += 20
    elif trend == "neutral":
        score += 5

    # Relative strength
    rs = features.get("relative_strength_state", "")
    if rs == "strong_outperformer":
        score += 25
    elif rs == "outperformer":
        score += 15

    # Pullback depth (sweet spot: -3% to -10%)
    pullback = features.get("pullback_depth_pct", 0.0)
    if -10 <= pullback <= -3:
        score += 25
    elif -15 <= pullback < -10:
        score += 10

    # Distance to SMA20 (pulling back toward support: -1% to -5%)
    dist_sma20 = features.get("dist_to_sma20_pct", 0.0)
    if -5 <= dist_sma20 <= -1:
        score += 10

    # Volume contraction on pullback
    vol_ratio = features.get("volume_ratio_20d", 1.0)
    if vol_ratio < 0.8:
        score += 10

    return score


def rank_universe(features: dict[str, dict]) -> list[dict]:
    """Rank all tickers and classify each as packet_worthy, watchlist, or not_interesting.

    Args:
        features: Output of compute_all_features — dict mapping ticker -> feature dict.

    Returns:
        List of dicts with keys: ticker, score, qualification, features.
        Sorted by score descending.
    """
    thresholds = _load_thresholds()
    packet_threshold = thresholds["packet_worthy"]
    watchlist_threshold = thresholds["watchlist"]

    ranked = []
    for ticker, feat in features.items():
        score = _score_ticker(feat)

        if score >= packet_threshold:
            event_risk_level = feat.get("event_risk_level", "none")
            if event_risk_level in ("elevated", "imminent"):
                qualification = "earnings_risk_packet"
            else:
                qualification = "packet_worthy"
        elif score >= watchlist_threshold:
            qualification = "watchlist"
        else:
            qualification = "not_interesting"

        ranked.append({
            "ticker": ticker,
            "score": score,
            "qualification": qualification,
            "features": feat,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def get_top_candidates(ranked: list[dict], max_packets: int = 5,
                        max_watchlist: int = 7) -> dict:
    """Extract top packet-worthy and watchlist candidates.

    Returns:
        {"packet_worthy": [...], "watchlist": [...]} sorted by score descending.
    """
    # Include earnings_risk_packet in packet_worthy list with a flag
    packet_worthy = []
    for r in ranked:
        if r["qualification"] in ("packet_worthy", "earnings_risk_packet"):
            entry = dict(r)
            entry["earnings_risk"] = r["qualification"] == "earnings_risk_packet"
            packet_worthy.append(entry)
            if len(packet_worthy) >= max_packets:
                break
    watchlist = [r for r in ranked if r["qualification"] == "watchlist"][:max_watchlist]
    return {
        "packet_worthy": packet_worthy,
        "watchlist": watchlist,
    }
