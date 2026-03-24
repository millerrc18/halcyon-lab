"""LLM-enhanced trade packet writer with template fallback."""

import logging

from src.llm.client import is_llm_available, generate
from src.llm.prompts import PACKET_SYSTEM_PROMPT
from src.models import TradePacket
from src.universe.company_names import get_company_name

logger = logging.getLogger(__name__)


def _build_feature_prompt(packet: TradePacket, features: dict) -> str:
    """Build a multi-source prompt from all available data."""
    ticker = packet.ticker
    company_name = packet.company_name

    # SECTION 1: Technical Data (existing)
    prompt = f"""=== TECHNICAL DATA ===
Ticker: {ticker} ({company_name})
Current Price: ${features.get('current_price', 0):.2f}
Trend State: {features.get('trend_state', 'n/a')} | SMA50 slope: {features.get('sma50_slope', 'n/a')} | SMA200 slope: {features.get('sma200_slope', 'n/a')}
Price vs SMA50: {features.get('price_vs_sma50_pct', 0):.1f}% | Price vs SMA200: {features.get('price_vs_sma200_pct', 0):.1f}%
Relative Strength: {features.get('relative_strength_state', 'n/a')}
RS vs SPY — 1m: {features.get('rs_vs_spy_1m', 0):.1f}% | 3m: {features.get('rs_vs_spy_3m', 0):.1f}% | 6m: {features.get('rs_vs_spy_6m', 0):.1f}%
Pullback Depth: {features.get('pullback_depth_pct', 0):.1f}% from 50-day high
ATR(14): ${features.get('atr_14', 0):.2f} ({features.get('atr_pct', 0):.1f}% of price)
Volume Ratio: {features.get('volume_ratio_20d', 0):.2f}x 20-day average
Distance to SMA20: {features.get('dist_to_sma20_pct', 0):.1f}%"""

    # SECTION 2: Market Regime (new)
    prompt += f"""

=== MARKET REGIME ===
Market Trend: {features.get('market_trend', 'n/a')} | SPY RSI(14): {features.get('spy_rsi_14', 'n/a')}
Volatility: {features.get('volatility_regime', 'n/a')} ({features.get('vix_proxy', 0):.1f}% realized vol)
SPY: {features.get('spy_20d_return', 0):+.1f}% (20d) | {features.get('spy_drawdown_from_high', 0):.1f}% from 52-week high
Breadth: {features.get('market_breadth_label', 'n/a')} ({features.get('market_breadth_pct', 0):.0f}% above 50d MA)
Regime: {features.get('regime_label', 'n/a')}"""

    # SECTION 3: Sector Context (new)
    prompt += f"""

=== SECTOR CONTEXT ===
Sector: {features.get('sector', 'n/a')} | Rank: {features.get('sector_rs_rank', 'n/a')} | Sector Avg Score: {features.get('sector_avg_score', 0):.0f}"""

    # SECTION 4: Fundamental Snapshot (new)
    fundamental_text = features.get('fundamental_summary', 'No fundamental data available')
    prompt += f"""

=== FUNDAMENTAL SNAPSHOT ===
{fundamental_text}"""

    # SECTION 5: Insider Activity (new)
    insider_text = features.get('insider_summary', 'No insider data available')
    prompt += f"""

=== INSIDER ACTIVITY ===
{insider_text}"""

    # SECTION 6: Macro Context (new)
    macro_text = features.get('macro_summary', 'No macro data available')
    prompt += f"""

=== MACRO CONTEXT ===
{macro_text}"""

    # SECTION 7: Entry/Stop/Targets (existing)
    prompt += f"""

=== TRADE PARAMETERS ===
Score: {features.get('_score', 0):.0f}/100 | Confidence: {packet.confidence}/10
Entry Zone: {packet.entry_zone} | Stop: {packet.stop_invalidation} | Targets: {packet.targets}
Position Size: ${packet.position_sizing.allocation_dollars:.0f} ({packet.position_sizing.allocation_pct:.1f}% of capital) | Risk: ${packet.position_sizing.estimated_risk_dollars:.2f}
Event Risk: {packet.event_risk}"""

    return prompt


def _parse_llm_response(response: str) -> tuple[str | None, str | None]:
    """Parse WHY NOW and DEEPER ANALYSIS sections from LLM response.

    Returns (why_now, deeper_analysis) or (None, None) on parse failure.
    """
    why_now = None
    deeper_analysis = None

    # Find WHY NOW section
    why_now_marker = "WHY NOW:"
    deeper_marker = "DEEPER ANALYSIS:"

    upper = response.upper()
    why_idx = upper.find(why_now_marker.upper())
    deeper_idx = upper.find(deeper_marker.upper())

    if why_idx == -1 or deeper_idx == -1:
        return None, None

    # Extract WHY NOW (between marker and DEEPER ANALYSIS)
    why_start = why_idx + len(why_now_marker)
    why_now = response[why_start:deeper_idx].strip()

    # Extract DEEPER ANALYSIS (after marker to end)
    deeper_start = deeper_idx + len(deeper_marker)
    deeper_analysis = response[deeper_start:].strip()

    if not why_now or not deeper_analysis:
        return None, None

    return why_now, deeper_analysis


def enhance_packet_with_llm(packet: TradePacket, features: dict,
                            config: dict) -> TradePacket:
    """Enhance a trade packet with LLM-written prose.

    If LLM is disabled or unavailable, returns the packet unchanged.
    Never modifies deterministic fields (entry, stop, targets, sizing, confidence, event_risk).

    Args:
        packet: The trade packet built from features.
        features: The raw feature dict for this ticker.
        config: Application config dict.

    Returns:
        The packet, potentially with enhanced why_now and deeper_analysis.
    """
    llm_cfg = config.get("llm", {})
    if not llm_cfg.get("enabled", False):
        logger.info("[LLM] Disabled in config — fallback to template for %s", packet.ticker)
        return packet

    if not is_llm_available():
        logger.warning("[LLM] Ollama not reachable — fallback to template for %s", packet.ticker)
        print(f"  [LLM] Fallback to template for {packet.ticker}")
        return packet

    prompt = _build_feature_prompt(packet, features)
    response = generate(prompt, PACKET_SYSTEM_PROMPT)

    if response is None:
        logger.warning("[LLM] Generation failed — fallback to template for %s", packet.ticker)
        print(f"  [LLM] Fallback to template for {packet.ticker}")
        return packet

    why_now, deeper_analysis = _parse_llm_response(response)

    if why_now is None or deeper_analysis is None:
        logger.warning("[LLM] Failed to parse response — fallback to template for %s", packet.ticker)
        print(f"  [LLM] Fallback to template for {packet.ticker}")
        return packet

    # Only update prose fields — never touch deterministic fields
    packet.why_now = why_now
    packet.deeper_analysis = deeper_analysis
    logger.info("[LLM] Enhanced packet for %s", packet.ticker)
    print(f"  [LLM] Enhanced packet for {packet.ticker}")
    return packet
