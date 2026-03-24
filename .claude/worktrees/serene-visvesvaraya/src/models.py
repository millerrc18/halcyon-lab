from dataclasses import dataclass
from typing import Optional


@dataclass
class PositionSizing:
    allocation_dollars: float
    allocation_pct: float
    estimated_risk_dollars: float


@dataclass
class TradePacket:
    ticker: str
    company_name: str
    recommendation: str
    setup_type: str
    why_now: str
    entry_zone: str
    stop_invalidation: str
    targets: str
    expected_hold_period: str
    confidence: int
    event_risk: str
    position_sizing: PositionSizing
    deeper_analysis: str
