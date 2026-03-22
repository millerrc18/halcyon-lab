from src.models import PositionSizing, TradePacket


def build_demo_packet() -> str:
    packet = TradePacket(
        ticker="AAPL",
        company_name="Apple Inc.",
        recommendation="Watch",
        setup_type="Pullback in strong trend / relative strength continuation",
        why_now="Constructive pullback into support while relative strength remains intact.",
        entry_zone="$212 - $215",
        stop_invalidation="$207 close basis",
        targets="$220 / $225",
        expected_hold_period="2 to 10 trading days",
        confidence=7,
        event_risk="Normal",
        position_sizing=PositionSizing(
            allocation_dollars=250.0,
            allocation_pct=25.0,
            estimated_risk_dollars=7.5,
        ),
        deeper_analysis=(
            "Trend remains constructive, pullback is orderly, and broader market context is neutral-to-supportive. "
            "Packet is a demo only and should not be treated as a real recommendation."
        ),
    )
    return render_packet(packet)



def render_packet(packet: TradePacket) -> str:
    return f"""[TRADE DESK] Action Packet - {packet.ticker}

Quick Bullet Brief
- Ticker / Company: {packet.ticker} / {packet.company_name}
- Recommendation: {packet.recommendation}
- Setup Type: {packet.setup_type}
- Why now: {packet.why_now}
- Entry Zone: {packet.entry_zone}
- Stop / Invalidation: {packet.stop_invalidation}
- Targets: {packet.targets}
- Expected Hold Period: {packet.expected_hold_period}
- Suggested Position Size: ${packet.position_sizing.allocation_dollars:.0f} ({packet.position_sizing.allocation_pct:.1f}% of capital), est. risk ${packet.position_sizing.estimated_risk_dollars:.2f}
- Event Risk: {packet.event_risk}
- Confidence: {packet.confidence}/10

Deeper Analysis
{packet.deeper_analysis}
"""
