"""Morning watchlist email formatter."""

from src.universe.company_names import get_company_name


def build_morning_watchlist(watchlist: list[dict], packet_worthy: list[dict],
                            date_str: str) -> str:
    """Build a formatted plain-text morning watchlist email body.

    Args:
        watchlist: List of watchlist candidate dicts from get_top_candidates.
        packet_worthy: List of packet-worthy candidate dicts from get_top_candidates.
        date_str: Date string for the header (YYYY-MM-DD).

    Returns:
        Formatted plain-text email body.
    """
    lines = []

    # Header
    lines.append(f"[TRADE DESK] Morning Watchlist - {date_str}")
    lines.append("")
    lines.append("Quick Summary:")
    lines.append(f"  - {len(watchlist)} names on watchlist")
    lines.append(f"  - {len(packet_worthy)} names packet-worthy (action packets to follow)")
    lines.append("")

    # Packet-worthy section
    lines.append(f"PACKET-WORTHY ({len(packet_worthy)}):")
    if packet_worthy:
        for c in packet_worthy:
            feat = c["features"]
            name = get_company_name(c["ticker"])
            flag = ""
            if c.get("earnings_risk"):
                flag = "  [EARNINGS RISK]"
            lines.append(
                f"  {c['ticker']:6s}  {name:20s}  score={c['score']:.0f}  "
                f"trend={feat.get('trend_state', 'n/a')}  "
                f"RS={feat.get('relative_strength_state', 'n/a')}  "
                f"pullback={feat.get('pullback_depth_pct', 0):.1f}%{flag}"
            )
    else:
        lines.append("  No packet-worthy setups today.")
    lines.append("")

    # Watchlist section
    lines.append(f"WATCHLIST ({len(watchlist)}):")
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
    lines.append("Quality over quantity. No packets is a valid answer.")

    return "\n".join(lines)
