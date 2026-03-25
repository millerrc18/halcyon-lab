"""CTO performance report generator.

Produces a comprehensive structured report for CTO analysis,
designed to be consumed by Claude for strategic recommendations.
"""

import json
import logging
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def generate_cto_report(days: int = 7, db_path: str = "ai_research_desk.sqlite3") -> dict:
    """Generate a comprehensive structured performance report for CTO analysis.

    Returns a dict (JSON-serializable) with all performance data.
    """
    now = datetime.now(ET)
    start_date = now - timedelta(days=days)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d")

    from src.journal.store import (
        get_closed_shadow_trades,
        get_open_shadow_trades,
        get_all_shadow_trades,
        get_recommendations_in_period,
    )
    from src.training.versioning import get_active_model_name, get_training_example_counts

    closed = get_closed_shadow_trades(days=days, db_path=db_path)
    open_trades = get_open_shadow_trades(db_path=db_path)
    all_trades = get_all_shadow_trades(days=days, db_path=db_path)
    recommendations = get_recommendations_in_period(days=days, db_path=db_path)

    # Count trading days (weekdays in period)
    trading_days = sum(
        1 for d in range(days)
        if (start_date + timedelta(days=d)).weekday() < 5
    )

    # System status
    model_name = get_active_model_name()
    try:
        t_counts = get_training_example_counts()
        dataset_size = t_counts.get("total", 0)
    except Exception:
        dataset_size = 0

    from src.config import load_config
    config = load_config()
    bootcamp_cfg = config.get("bootcamp", {})

    # Trade summary
    trade_summary = _compute_trade_summary(closed, open_trades, all_trades)

    # By exit reason
    by_exit_reason = _compute_by_exit_reason(closed)

    # By score band
    by_score_band = _compute_by_score_band(closed, recommendations)

    # By sector
    by_sector = _compute_by_sector(closed, recommendations)

    # By regime
    by_regime = _compute_by_regime(closed, recommendations)

    # By model version
    by_model = _compute_by_model_version(closed, recommendations)

    # Execution analysis
    execution = _compute_execution_analysis(closed)

    # Signal quality
    signal_quality = _compute_signal_quality(closed, recommendations)

    # Feature correlations
    feature_correlations = _compute_feature_correlations(closed, recommendations)

    # Training status
    training_status = _compute_training_status(days, db_path)

    # Confidence calibration
    confidence_calibration = _compute_confidence_calibration(closed, recommendations)

    return {
        "report_period": {
            "start": start_str,
            "end": end_str,
            "trading_days": trading_days,
        },
        "system_status": {
            "model_version": model_name,
            "dataset_size": dataset_size,
            "bootcamp_phase": bootcamp_cfg.get("phase", 0) if bootcamp_cfg.get("enabled") else None,
            "bootcamp_day": None,
        },
        "trade_summary": trade_summary,
        "by_exit_reason": by_exit_reason,
        "by_score_band": by_score_band,
        "by_sector": by_sector,
        "by_regime": by_regime,
        "by_model_version": by_model,
        "execution_analysis": execution,
        "signal_quality": signal_quality,
        "feature_correlations": feature_correlations,
        "training_status": training_status,
        "confidence_calibration": confidence_calibration,
    }


def _compute_trade_summary(closed: list, open_trades: list, all_trades: list) -> dict:
    """Compute overall trade performance summary."""
    winners = [t for t in closed if (t.get("pnl_dollars") or 0) > 0]
    losers = [t for t in closed if (t.get("pnl_dollars") or 0) <= 0]

    win_rate = len(winners) / len(closed) if closed else 0
    avg_winner = sum(t.get("pnl_pct", 0) or 0 for t in winners) / len(winners) if winners else 0
    avg_loser = sum(t.get("pnl_pct", 0) or 0 for t in losers) / len(losers) if losers else 0

    total_pnl = sum(t.get("pnl_dollars", 0) or 0 for t in closed)
    expectancy = total_pnl / len(closed) if closed else 0

    max_win = max(closed, key=lambda t: t.get("pnl_pct", 0) or 0) if closed else None
    max_loss = min(closed, key=lambda t: t.get("pnl_pct", 0) or 0) if closed else None

    # Sharpe ratio (annualized from per-trade returns)
    import math
    pnl_pcts = [t.get("pnl_pct", 0) or 0 for t in closed]
    if len(pnl_pcts) >= 2:
        mean_r = sum(pnl_pcts) / len(pnl_pcts)
        std_r = (sum((r - mean_r) ** 2 for r in pnl_pcts) / (len(pnl_pcts) - 1)) ** 0.5
        # Annualize assuming ~150 trades/year (roughly 3/week)
        sharpe = (mean_r / std_r) * math.sqrt(150) if std_r > 0 else 0
    else:
        sharpe = 0

    return {
        "trades_opened": len(all_trades),
        "trades_closed": len(closed),
        "trades_open": len(open_trades),
        "win_rate": round(win_rate, 3),
        "sharpe_ratio": round(sharpe, 2),
        "avg_winner_pct": round(avg_winner, 1),
        "avg_loser_pct": round(avg_loser, 1),
        "expectancy_dollars": round(expectancy, 2),
        "total_pnl": round(total_pnl, 2),
        "max_single_win": {
            "ticker": max_win.get("ticker", ""),
            "pnl_pct": round(max_win.get("pnl_pct", 0) or 0, 1),
            "duration": max_win.get("duration_days", 0) or 0,
        } if max_win else None,
        "max_single_loss": {
            "ticker": max_loss.get("ticker", ""),
            "pnl_pct": round(max_loss.get("pnl_pct", 0) or 0, 1),
            "duration": max_loss.get("duration_days", 0) or 0,
        } if max_loss else None,
    }


def _compute_by_exit_reason(closed: list) -> dict:
    by_reason = defaultdict(lambda: {"count": 0, "pnls": []})
    for t in closed:
        reason = t.get("exit_reason", "unknown")
        by_reason[reason]["count"] += 1
        by_reason[reason]["pnls"].append(t.get("pnl_pct", 0) or 0)

    result = {}
    for reason, data in by_reason.items():
        avg = sum(data["pnls"]) / len(data["pnls"]) if data["pnls"] else 0
        result[reason] = {"count": data["count"], "avg_pnl": round(avg, 1)}
    return result


def _compute_by_score_band(closed: list, recommendations: list) -> dict:
    # Map recommendation_id -> priority_score
    score_map = {r.get("recommendation_id"): r.get("priority_score", 0) or 0 for r in recommendations}

    bands = {"90-100": [], "80-89": [], "70-79": [], "below_70": []}
    for t in closed:
        rec_id = t.get("recommendation_id")
        score = score_map.get(rec_id, 0)
        pnl = t.get("pnl_pct", 0) or 0
        won = 1 if (t.get("pnl_dollars") or 0) > 0 else 0

        if score >= 90:
            bands["90-100"].append((pnl, won))
        elif score >= 80:
            bands["80-89"].append((pnl, won))
        elif score >= 70:
            bands["70-79"].append((pnl, won))
        else:
            bands["below_70"].append((pnl, won))

    result = {}
    for band, data in bands.items():
        if data:
            wr = sum(w for _, w in data) / len(data)
            avg = sum(p for p, _ in data) / len(data)
            result[band] = {"trades": len(data), "win_rate": round(wr, 2), "avg_pnl": round(avg, 1)}
        else:
            result[band] = {"trades": 0, "win_rate": 0, "avg_pnl": 0}
    return result


def _compute_by_sector(closed: list, recommendations: list) -> dict:
    from src.universe.sectors import SECTOR_MAP

    by_sector = defaultdict(lambda: {"trades": 0, "wins": 0})
    for t in closed:
        ticker = t.get("ticker", "")
        sector = SECTOR_MAP.get(ticker, "Unknown")
        by_sector[sector]["trades"] += 1
        if (t.get("pnl_dollars") or 0) > 0:
            by_sector[sector]["wins"] += 1

    result = {}
    for sector, data in by_sector.items():
        wr = data["wins"] / data["trades"] if data["trades"] > 0 else 0
        result[sector] = {"trades": data["trades"], "win_rate": round(wr, 2)}
    return result


def _compute_by_regime(closed: list, recommendations: list) -> dict:
    # Try to get regime from recommendation's market_regime column
    regime_map = {r.get("recommendation_id"): r.get("market_regime", "unknown") for r in recommendations}

    by_regime = defaultdict(lambda: {"trades": 0, "wins": 0})
    for t in closed:
        rec_id = t.get("recommendation_id")
        regime = regime_map.get(rec_id, "unknown") or "unknown"
        by_regime[regime]["trades"] += 1
        if (t.get("pnl_dollars") or 0) > 0:
            by_regime[regime]["wins"] += 1

    result = {}
    for regime, data in by_regime.items():
        wr = data["wins"] / data["trades"] if data["trades"] > 0 else 0
        result[regime] = {"trades": data["trades"], "win_rate": round(wr, 2)}
    return result


def _compute_by_model_version(closed: list, recommendations: list) -> dict:
    version_map = {r.get("recommendation_id"): r.get("model_version", "base") for r in recommendations}

    by_model = defaultdict(lambda: {"trades": 0, "wins": 0, "pnls": []})
    for t in closed:
        rec_id = t.get("recommendation_id")
        version = version_map.get(rec_id, "base") or "base"
        by_model[version]["trades"] += 1
        pnl = t.get("pnl_dollars", 0) or 0
        by_model[version]["pnls"].append(pnl)
        if pnl > 0:
            by_model[version]["wins"] += 1

    result = {}
    for ver, data in by_model.items():
        wr = data["wins"] / data["trades"] if data["trades"] > 0 else 0
        exp = sum(data["pnls"]) / len(data["pnls"]) if data["pnls"] else 0
        result[ver] = {
            "trades": data["trades"],
            "win_rate": round(wr, 2),
            "expectancy": round(exp, 2),
        }
    return result


def _compute_execution_analysis(closed: list) -> dict:
    if not closed:
        return {
            "avg_stop_distance_atr": 0,
            "stops_that_then_reversed": 0,
            "targets_hit_pct": 0,
            "timeout_pct": 0,
            "avg_mfe_winners": 0,
            "avg_mae_losers": 0,
            "avg_hold_period_days": 0,
        }

    winners = [t for t in closed if (t.get("pnl_dollars") or 0) > 0]
    losers = [t for t in closed if (t.get("pnl_dollars") or 0) <= 0]
    targets = [t for t in closed if t.get("exit_reason", "").startswith("target")]
    timeouts = [t for t in closed if t.get("exit_reason") == "timeout"]

    avg_mfe_w = sum(t.get("max_favorable_excursion", 0) or 0 for t in winners) / len(winners) if winners else 0
    avg_mae_l = sum(t.get("max_adverse_excursion", 0) or 0 for t in losers) / len(losers) if losers else 0
    avg_hold = sum(t.get("duration_days", 0) or 0 for t in closed) / len(closed)

    return {
        "avg_stop_distance_atr": 2.0,  # Default per our setup
        "stops_that_then_reversed": 0,  # Would need post-exit data
        "targets_hit_pct": round(len(targets) / len(closed), 3) if closed else 0,
        "timeout_pct": round(len(timeouts) / len(closed), 3) if closed else 0,
        "avg_mfe_winners": round(avg_mfe_w, 2),
        "avg_mae_losers": round(avg_mae_l, 2),
        "avg_hold_period_days": round(avg_hold, 1),
    }


def _compute_signal_quality(closed: list, recommendations: list) -> dict:
    score_map = {r.get("recommendation_id"): r.get("priority_score", 0) or 0 for r in recommendations}

    high_score_losers = []
    for t in closed:
        rec_id = t.get("recommendation_id")
        score = score_map.get(rec_id, 0)
        pnl = t.get("pnl_pct", 0) or 0
        if score >= 80 and pnl < 0:
            high_score_losers.append({
                "ticker": t.get("ticker"),
                "score": score,
                "pnl_pct": round(pnl, 1),
                "exit_reason": t.get("exit_reason"),
            })

    return {
        "high_score_losers": high_score_losers[:10],
        "low_score_winners": [],  # Would require backfill data
    }


def _compute_feature_correlations(closed: list, recommendations: list) -> dict:
    """Compute win rate by feature state for key features."""
    feat_map = {}
    for r in recommendations:
        rec_id = r.get("recommendation_id")
        feat_map[rec_id] = {
            "trend_state": r.get("trend_state"),
            "relative_strength_state": r.get("relative_strength_state"),
            "pullback_depth_pct": r.get("pullback_depth_pct"),
            "volume_state": r.get("volume_state"),
        }

    # Trend state correlation
    trend_groups = defaultdict(lambda: {"total": 0, "wins": 0})
    rs_groups = defaultdict(lambda: {"total": 0, "wins": 0})
    pullback_groups = defaultdict(lambda: {"total": 0, "wins": 0})
    vol_groups = defaultdict(lambda: {"total": 0, "wins": 0})

    for t in closed:
        rec_id = t.get("recommendation_id")
        feats = feat_map.get(rec_id, {})
        won = 1 if (t.get("pnl_dollars") or 0) > 0 else 0

        trend = feats.get("trend_state", "unknown")
        trend_groups[trend]["total"] += 1
        trend_groups[trend]["wins"] += won

        rs = feats.get("relative_strength_state", "unknown")
        rs_groups[rs]["total"] += 1
        rs_groups[rs]["wins"] += won

        pb = feats.get("pullback_depth_pct")
        if pb is not None:
            if -7 <= pb <= -3:
                pb_label = "3_to_7_pct"
            elif -12 <= pb < -7:
                pb_label = "7_to_12_pct"
            else:
                pb_label = "other"
            pullback_groups[pb_label]["total"] += 1
            pullback_groups[pb_label]["wins"] += won

        vol = feats.get("volume_state")
        if vol:
            vol_groups[vol]["total"] += 1
            vol_groups[vol]["wins"] += won

    def _wr(group):
        result = {}
        for k, v in group.items():
            wr = v["wins"] / v["total"] if v["total"] > 0 else 0
            result[f"{k}_win_rate"] = round(wr, 2)
        return result

    return {
        "trend_state": _wr(trend_groups),
        "relative_strength": _wr(rs_groups),
        "pullback_depth": _wr(pullback_groups),
        "volume_contraction": _wr(vol_groups),
    }


def _compute_training_status(days: int, db_path: str) -> dict:
    try:
        from src.training.versioning import get_training_example_counts
        counts = get_training_example_counts(db_path)
    except Exception:
        counts = {"total": 0, "live": 0, "backfill": 0}

    # Training data quality metrics
    training_data_quality = {}
    try:
        from src.training.validation import validate_training_dataset
        validation = validate_training_dataset(db_path)
        training_data_quality["format_compliance"] = validation.get("format_breakdown", {})
        training_data_quality["average_process_score"] = validation.get("avg_quality_score")
    except Exception:
        pass

    try:
        from src.training.leakage_detector import check_outcome_leakage
        leakage = check_outcome_leakage(db_path)
        training_data_quality["leakage_test_accuracy"] = leakage.get("test_accuracy")
    except Exception:
        pass

    # Annie Duke quadrant distribution from source tags
    try:
        import sqlite3 as _sqlite3
        with _sqlite3.connect(db_path) as conn:
            conn.row_factory = _sqlite3.Row
            rows = conn.execute(
                "SELECT source, quality_score_auto FROM training_examples "
                "WHERE source IS NOT NULL"
            ).fetchall()
        quadrants = {
            "good_process_good_outcome": 0,
            "good_process_bad_outcome": 0,
            "bad_process_good_outcome": 0,
            "bad_process_bad_outcome": 0,
        }
        for row in rows:
            source = row["source"] or ""
            score = row["quality_score_auto"]
            is_win = "win" in source
            is_good_process = score is not None and score >= 3.0
            if is_good_process and is_win:
                quadrants["good_process_good_outcome"] += 1
            elif is_good_process and not is_win:
                quadrants["good_process_bad_outcome"] += 1
            elif not is_good_process and is_win:
                quadrants["bad_process_good_outcome"] += 1
            elif not is_good_process and not is_win:
                quadrants["bad_process_bad_outcome"] += 1
        training_data_quality["quadrant_distribution"] = quadrants
    except Exception:
        pass

    return {
        "total_examples": counts.get("total", 0),
        "backfill_examples": counts.get("backfill", 0),
        "live_examples": counts.get("live", 0),
        "examples_this_period": 0,  # Would need date filtering
        "model_version_trend": "stable",
        "training_data_quality": training_data_quality,
    }


def _compute_confidence_calibration(closed: list, recommendations: list) -> dict:
    """Compute confidence calibration from LLM conviction scores."""
    conv_map = {r.get("recommendation_id"): r.get("llm_conviction") for r in recommendations}

    bands = {"8-10": [], "5-7": [], "1-4": []}
    convictions = []
    pnls = []

    for t in closed:
        rec_id = t.get("recommendation_id")
        conv = conv_map.get(rec_id)
        if conv is None:
            continue

        pnl = t.get("pnl_pct", 0) or 0
        won = 1 if (t.get("pnl_dollars") or 0) > 0 else 0
        convictions.append(conv)
        pnls.append(pnl)

        if conv >= 8:
            bands["8-10"].append((pnl, won))
        elif conv >= 5:
            bands["5-7"].append((pnl, won))
        else:
            bands["1-4"].append((pnl, won))

    by_band = {}
    for band, data in bands.items():
        if data:
            wr = sum(w for _, w in data) / len(data)
            avg_pnl = sum(p for p, _ in data) / len(data)
            by_band[band] = {"trades": len(data), "win_rate": round(wr, 2), "avg_pnl": round(avg_pnl, 1)}
        else:
            by_band[band] = {"trades": 0, "win_rate": 0, "avg_pnl": 0}

    # Correlation
    correlation = 0.0
    if len(convictions) >= 5:
        from src.evaluation.feature_importance import _pearson_correlation
        correlation = _pearson_correlation([float(c) for c in convictions], pnls)

    # Calibration check: higher conviction should = higher win rate
    is_calibrated = True
    if by_band["8-10"]["trades"] >= 3 and by_band["1-4"]["trades"] >= 3:
        is_calibrated = by_band["8-10"]["win_rate"] > by_band["1-4"]["win_rate"]

    # Overconfidence rate
    high_conv_losers = sum(1 for p, w in bands["8-10"] if w == 0)
    overconfidence = high_conv_losers / len(bands["8-10"]) if bands["8-10"] else 0

    return {
        "by_conviction_band": by_band,
        "correlation_with_outcomes": round(correlation, 3),
        "is_calibrated": is_calibrated,
        "overconfidence_rate": round(overconfidence, 2),
        "total_with_conviction": len(convictions),
    }


def format_cto_report(report: dict) -> str:
    """Format the CTO report as a readable text summary."""
    lines = []
    lines.append("=" * 60)
    lines.append(f" CTO PERFORMANCE REPORT")
    lines.append(f" Period: {report['report_period']['start']} to {report['report_period']['end']}")
    lines.append(f" Trading Days: {report['report_period']['trading_days']}")
    lines.append("=" * 60)
    lines.append("")

    status = report["system_status"]
    lines.append(f"MODEL: {status['model_version']} | Dataset: {status['dataset_size']} examples")
    lines.append("")

    ts = report["trade_summary"]
    lines.append("TRADE SUMMARY:")
    lines.append(f"  Opened: {ts['trades_opened']} | Closed: {ts['trades_closed']} | Open: {ts['trades_open']}")
    lines.append(f"  Win Rate: {ts['win_rate']:.1%} | Avg Winner: {ts['avg_winner_pct']:+.1f}% | Avg Loser: {ts['avg_loser_pct']:+.1f}%")
    lines.append(f"  Expectancy: ${ts['expectancy_dollars']:+.2f} | Total P&L: ${ts['total_pnl']:+.2f}")
    if ts.get("max_single_win"):
        lines.append(f"  Best: {ts['max_single_win']['ticker']} ({ts['max_single_win']['pnl_pct']:+.1f}%)")
    if ts.get("max_single_loss"):
        lines.append(f"  Worst: {ts['max_single_loss']['ticker']} ({ts['max_single_loss']['pnl_pct']:+.1f}%)")
    lines.append("")

    lines.append("BY EXIT REASON:")
    for reason, data in report["by_exit_reason"].items():
        lines.append(f"  {reason}: {data['count']} trades, avg {data['avg_pnl']:+.1f}%")
    lines.append("")

    lines.append("BY SCORE BAND:")
    for band, data in report["by_score_band"].items():
        lines.append(f"  {band}: {data['trades']} trades, WR {data['win_rate']:.0%}, avg {data['avg_pnl']:+.1f}%")
    lines.append("")

    lines.append("BY SECTOR:")
    for sector, data in sorted(report["by_sector"].items(), key=lambda x: -x[1]["trades"]):
        lines.append(f"  {sector}: {data['trades']} trades, WR {data['win_rate']:.0%}")
    lines.append("")

    exec_data = report["execution_analysis"]
    lines.append("EXECUTION:")
    lines.append(f"  Targets hit: {exec_data['targets_hit_pct']:.0%} | Timeout: {exec_data['timeout_pct']:.0%}")
    lines.append(f"  Avg MFE (winners): ${exec_data['avg_mfe_winners']:.2f} | Avg MAE (losers): ${exec_data['avg_mae_losers']:.2f}")
    lines.append(f"  Avg hold: {exec_data['avg_hold_period_days']:.1f} days")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
