"""
Qualification pipeline — fetch all signal sources, score, return leads.

Industry-agnostic sources (always on):
  - SEC EDGAR 10-K AI/risk disclosures
  - Google News RSS (exec interviews, AI/compliance mentions)
  - BusinessWire + PRNewswire RSS (funding rounds, AI initiatives)

Industry-specific packs (opt-in via env):
  - ENABLE_FDA_SIGNALS=true → openFDA (enforcement + 510k) — biotech/pharma/medtech
  # Future packs: ENABLE_FTC_SIGNALS, ENABLE_FINRA_SIGNALS, etc.

Flow: sources → deduplicate → score → tier filter
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from src.qualify.scorer import Lead, Tier, qualify_leads
from src.signals.base import Signal
from src.signals.news import fetch_exec_interviews
from src.signals.press import fetch_press_releases
from src.signals.sec import fetch_10k_ai_risk

logger = logging.getLogger(__name__)


async def run_pipeline(
    days: int = 180,
    min_tier: Tier = Tier.NURTURE,
) -> dict:
    """
    Run the full signal ingestion + qualification pipeline.

    Returns:
      leads         — list[Lead] at or above min_tier, score desc
      signal_counts — dict of source → count
      contact_count — leads ready for immediate outreach
      nurture_count — leads to monitor
      run_at        — ISO timestamp
      errors        — non-fatal source errors
    """
    run_at = datetime.now(timezone.utc).isoformat()
    logger.info("qualification pipeline starting (days=%d)", days)

    # Build task list — always-on sources
    tasks: list[tuple[str, object]] = [
        ("SEC_EDGAR",  fetch_10k_ai_risk(days)),
        ("News_RSS",   fetch_exec_interviews(days)),
        ("Press_RSS",  fetch_press_releases(min(days, 30))),
    ]

    # Industry-specific packs
    if os.environ.get("ENABLE_FDA_SIGNALS", "").lower() in ("1", "true", "yes"):
        from src.signals.openfda import fetch_all as fetch_fda
        tasks.append(("openFDA", fetch_fda(days)))

    source_names = [name for name, _ in tasks]
    coroutines   = [coro for _, coro in tasks]

    results = await asyncio.gather(*coroutines, return_exceptions=True)

    all_signals: list[Signal] = []
    signal_counts: dict[str, int] = {}
    errors: list[str] = []

    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            logger.error("Source %s failed: %s", name, result)
            errors.append(f"{name}: {result}")
            signal_counts[name] = 0
        else:
            signal_counts[name] = len(result)
            all_signals.extend(result)

    logger.info("signals fetched: %s → total %d", signal_counts, len(all_signals))

    leads = qualify_leads(all_signals)

    tier_order = [Tier.CONTACT, Tier.NURTURE, Tier.ARCHIVE]
    min_idx    = tier_order.index(min_tier)
    filtered   = [l for l in leads if tier_order.index(l.tier) <= min_idx]

    logger.info(
        "qualification complete: %d total leads, %d at/above %s",
        len(leads), len(filtered), min_tier.value,
    )

    return {
        "leads":         filtered,
        "signal_counts": signal_counts,
        "total_leads":   len(leads),
        "contact_count": sum(1 for l in leads if l.tier == Tier.CONTACT),
        "nurture_count": sum(1 for l in leads if l.tier == Tier.NURTURE),
        "run_at":        run_at,
        "errors":        errors,
    }
