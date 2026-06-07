from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class SignalType(str, Enum):
    # Regulatory (pluggable per-industry packs)
    REGULATORY_ACTION  = "S1"   # FDA enforcement, FTC action, SEC enforcement, etc.
    REGULATORY_FILING  = "S2"   # 10-K AI/risk disclosure, material weakness, etc.
    PRODUCT_CLEARANCE  = "S3"   # FDA 510k, patent grant, product launch, CE mark, etc.

    # Growth / hiring
    FUNDING_ROUND      = "S4"   # Series A-D, IPO, SPAC — expansion = need for services
    HIRING_SIGNAL      = "S5"   # Job postings for AI/data/compliance/quality roles

    # Executive signals
    EXEC_INTERVIEW     = "S6"   # Public interview, podcast, press quote about AI/data/risk
    PRESS_RELEASE      = "S7"   # Company-issued announcement: new initiative, partnership

    # Catch-all
    OTHER              = "S9"


# Base points before freshness decay — tune per use case
SIGNAL_BASE_SCORE: dict[SignalType, int] = {
    SignalType.REGULATORY_ACTION: 35,   # highest urgency — pain is real and immediate
    SignalType.REGULATORY_FILING: 25,   # disclosed risk → board-level conversation
    SignalType.PRODUCT_CLEARANCE: 20,   # growth moment → capacity pressure
    SignalType.FUNDING_ROUND:     25,   # budget just appeared
    SignalType.HIRING_SIGNAL:     15,   # scaling pain
    SignalType.EXEC_INTERVIEW:    15,   # awareness + openness
    SignalType.PRESS_RELEASE:     10,   # weakest — informational
    SignalType.OTHER:             5,
}

HIGH_URGENCY = {SignalType.REGULATORY_ACTION, SignalType.FUNDING_ROUND, SignalType.REGULATORY_FILING}


@dataclass
class Signal:
    signal_type:    SignalType
    company_name:   str
    date:           datetime
    summary:        str        = ""
    source_url:     str        = ""
    company_domain: str        = ""
    industry:       str        = ""   # optional — set by industry-specific packs
    raw:            dict       = field(default_factory=dict)

    def age_days(self) -> int:
        now = datetime.now(timezone.utc)
        d = self.date if self.date.tzinfo else self.date.replace(tzinfo=timezone.utc)
        return max(0, (now - d).days)

    def freshness_factor(self) -> float:
        age = self.age_days()
        if age <= 30:  return 1.0
        if age <= 60:  return 0.75
        if age <= 90:  return 0.50
        return 0.25
