"""
Lead qualification scoring — deterministic, 0–100. Industry-agnostic.

Tiers:
  CONTACT  ≥ 60  → ready for outreach (email + voice)
  NURTURE  40-59 → monitor, re-score next cycle
  ARCHIVE  < 40  → skip

Scoring factors:
  1. Signal base score × freshness decay (per signal, from base.py)
  2. Multi-signal bonus  (+8 per additional signal, same company)
  3. High-urgency bonus  (+10 if any signal is REGULATORY or FUNDING)
  4. Cluster bonus       (+5 if 2+ signals within 30 days — buying window)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.signals.base import HIGH_URGENCY, SIGNAL_BASE_SCORE, Signal, SignalType


class Tier(str, Enum):
    CONTACT = "CONTACT"
    NURTURE = "NURTURE"
    ARCHIVE = "ARCHIVE"


@dataclass
class Lead:
    company_name:    str
    signals:         list[Signal]
    score:           int           = 0
    tier:            Tier          = Tier.ARCHIVE
    score_breakdown: dict          = field(default_factory=dict)
    best_signal:     Signal | None = None
    created_at:      datetime      = field(default_factory=lambda: datetime.now(timezone.utc))

    def primary_signal_type(self) -> str:
        return self.best_signal.signal_type.value if self.best_signal else ""

    def primary_summary(self) -> str:
        return self.best_signal.summary if self.best_signal else ""

    def to_dict(self) -> dict:
        return {
            "company_name":    self.company_name,
            "score":           self.score,
            "tier":            self.tier.value,
            "signal_count":    len(self.signals),
            "signal_types":    [s.signal_type.value for s in self.signals],
            "primary_signal":  self.primary_signal_type(),
            "summary":         self.primary_summary(),
            "source_url":      self.best_signal.source_url if self.best_signal else "",
            "score_breakdown": self.score_breakdown,
            "created_at":      self.created_at.isoformat(),
        }


def score_company(company_name: str, signals: list[Signal]) -> Lead:
    if not signals:
        return Lead(company_name=company_name, signals=[], score=0, tier=Tier.ARCHIVE)

    breakdown: dict[str, float] = {}
    raw_score = 0.0

    # 1. Signal base scores × freshness
    for sig in signals:
        base    = SIGNAL_BASE_SCORE.get(sig.signal_type, 5)
        decayed = base * sig.freshness_factor()
        key     = f"{sig.signal_type.value}_decayed"
        breakdown[key] = breakdown.get(key, 0) + round(decayed, 1)
        raw_score += decayed

    # 2. Multi-signal bonus
    if len(signals) > 1:
        bonus = (len(signals) - 1) * 8
        breakdown["multi_signal_bonus"] = bonus
        raw_score += bonus

    # 3. High-urgency bonus
    if any(s.signal_type in HIGH_URGENCY for s in signals):
        breakdown["urgency_bonus"] = 10
        raw_score += 10

    # 4. Signal cluster bonus
    recent = [s for s in signals if s.age_days() <= 30]
    if len(recent) >= 2:
        breakdown["cluster_bonus"] = 5
        raw_score += 5

    score = min(100, int(raw_score))
    tier  = Tier.CONTACT if score >= 60 else (Tier.NURTURE if score >= 40 else Tier.ARCHIVE)

    # best signal: prefer high-urgency types, then most recent
    def _rank(s: Signal) -> tuple:
        return (1 if s.signal_type in HIGH_URGENCY else 0, -s.age_days())

    best = max(signals, key=_rank)

    return Lead(
        company_name=company_name,
        signals=signals,
        score=score,
        tier=tier,
        score_breakdown=breakdown,
        best_signal=best,
    )


def qualify_leads(signals: list[Signal]) -> list[Lead]:
    """Group by NORMALIZED company name, drop junk, score, sort by score desc.

    Normalized grouping lets the same company from different sources merge
    ("AMERICAN EXPRESS CO" + "American Express") → multi-signal → higher tier.
    """
    from src.signals.normalize import normalize_company, is_valid_company, pick_display_name

    grouped: dict[str, list[Signal]] = {}
    for sig in signals:
        if not is_valid_company(sig.company_name):
            continue
        key = normalize_company(sig.company_name)
        if not key:
            continue
        grouped.setdefault(key, []).append(sig)

    leads = [
        score_company(pick_display_name([s.company_name for s in sigs]), sigs)
        for sigs in grouped.values()
    ]
    leads.sort(key=lambda l: l.score, reverse=True)
    return leads
