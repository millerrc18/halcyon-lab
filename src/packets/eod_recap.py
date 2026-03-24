"""End-of-day recap email formatter."""

from src.universe.company_names import get_company_name


def build_eod_recap(packet_worthy: list[dict], watchlist: list[dict],
                    journal_entries: list[dict], date_str: str) -> str:
    """Build a formatted plain-text EOD recap email body.

    Args:
        packet_worthy: List of packet-worthy candidate dicts from get_top_candidates.
        watchlist: List of watchlist candidate dicts from get_top_candidates.
        journal_entries: List of recommendation dicts from get_todays_recommendations.
        date_str: Date string for the header (YYYY-MM-DD).

    Returns:
        Formatted plain-text email body.
    """
    lines = []

    # Header
    lines.append(f"[TRADE DESK] EOD Recap - {date_str}")
    lines.append("")

    # Activity summary
    lines.append("ACTIVITY SUMMARY:")
    lines.append(f"  - Packets sent today: {len(journal_entries)}")
    lines.append(f"  - Watchlist names: {len(watchlist)}")
    lines.append(f"  - Total recommendations logged: {len(journal_entries)}")
    lines.append("")

    # Packets sent today
    lines.append("PACKETS SENT:")
    if journal_entries:
        for entry in journal_entries:
            ticker = entry.get("ticker", "???")
            name = entry.get("company_name") or get_company_name(ticker)
            entry_zone = entry.get("entry_zone", "n/a")
            stop = entry.get("stop_level", "n/a")
            t1 = entry.get("target_1", "")
            t2 = entry.get("target_2", "")
            targets = f"{t1} / {t2}".strip(" /") if t1 or t2 else "n/a"
            confidence = entry.get("confidence_score", "n/a")
            conf_str = f"{confidence:.0f}" if isinstance(confidence, (int, float)) else str(confidence)
            lines.append(
                f"  {ticker:6s}  {name:20s}  entry={entry_zone}  stop={stop}  "
                f"targets={targets}  confidence={conf_str}/10"
            )
    else:
        lines.append("  No packet-worthy setups today.")
    lines.append("")

    # Watchlist status
    lines.append("WATCHLIST STATUS:")
    if watchlist:
        for c in watchlist:
            feat = c["features"]
            name = get_company_name(c["ticker"])
            lines.append(
                f"  {c['ticker']:6s}  {name:20s}  score={c['score']:.0f}  "
                f"trend={feat.get('trend_state', 'n/a')}  "
                f"RS={feat.get('relative_strength_state', 'n/a')}  "
                f"pullback={feat.get('pullback_depth_pct', 0):.1f}%"
            )
    else:
        lines.append("  No watchlist names today.")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("Halcyon Lab AI Research Desk")
    lines.append(f"EOD recap for {date_str}. Full post-trade review is only required for trades you actually execute.")

    return "\n".join(lines)
