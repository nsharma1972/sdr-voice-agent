"""
Qualification pipeline — fetch all signal sources, score, return leads.

Industry-agnostic sources (always on):
  - SEC EDGAR 10-K AI/risk disclosures
  - Google News RSS (exec interviews, AI/compliance mentions)
  - BusinessWire + PRNewswire RSS (funding rounds, AI initiatives)
  - LinkedIn / job-posting hiring signals (S5)            [Issue #7]

Industry packs (opt-in):
  - INDUSTRY_PACK=fintech|healthtech|saas  → vertical news + hiring queries  [Issue #6]
  - ENABLE_FDA_SIGNALS=true → openFDA (enforcement + 510k) — biotech/pharma/medtech

Flow: sources → deduplicate → score → tier filter
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from src.db import enqueue_call
from src.qualify.scorer import Lead, Tier, qualify_leads
from src.signals.base import HIGH_URGENCY, Signal, SignalType
from src.signals.news import fetch_exec_interviews
from src.signals.press import fetch_press_releases
from src.signals.sec import fetch_10k_ai_risk
from src.signals.linkedin import fetch_hiring_signals          # Issue #7
from src.signals.queries import get_active_pack, pack_news_queries, pack_hiring_queries  # Issue #6

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
      industry_pack — active vertical pack ("generic" if none)
      contact_count — leads ready for immediate outreach
      nurture_count — leads to monitor
      run_at        — ISO timestamp
      errors        — non-fatal source errors
    """
    run_at = datetime.now(timezone.utc).isoformat()

    # Industry pack selection (Issue #6) — None => generic, industry-agnostic
    pack_name, _ = get_active_pack()
    news_pack   = pack_news_queries()    # extra vertical news queries (or [])
    hiring_pack = pack_hiring_queries()  # vertical buyer roles (or [] => generic roles)
    logger.info("qualification pipeline starting (days=%d, pack=%s)", days, pack_name or "generic")

    # Build task list — always-on sources
    tasks: list[tuple[str, object]] = [
        ("SEC_EDGAR",     fetch_10k_ai_risk(days)),
        ("News_RSS",      fetch_exec_interviews(days, custom_queries=news_pack or None)),
        ("Press_RSS",     fetch_press_releases(min(days, 30))),
        ("LinkedIn_Jobs", fetch_hiring_signals(days, custom_queries=hiring_pack or None)),
    ]

    # Industry-specific regulatory pack
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

    # Enrichment (Issue: lift single-signal companies → CONTACT).
    # Anchor on real company names we already have (SEC names are cleanest) and
    # search news/hiring for each, so the same company gains a 2nd/3rd signal.
    if os.environ.get("DISABLE_ENRICHMENT", "").lower() not in ("1", "true", "yes"):
        from src.signals.enrich import enrich_companies
        from src.signals.normalize import is_valid_company
        anchor_names: list[str] = []
        seen_anchor: set[str] = set()
        for s in all_signals:
            if not is_valid_company(s.company_name):
                continue
            k = s.company_name.lower().strip()
            if k not in seen_anchor:
                seen_anchor.add(k)
                anchor_names.append(s.company_name)
        try:
            extra = await enrich_companies(anchor_names, days=days)
            signal_counts["Enrichment"] = len(extra)
            all_signals.extend(extra)
        except Exception as exc:
            logger.error("Enrichment failed: %s", exc)
            errors.append(f"Enrichment: {exc}")
            signal_counts["Enrichment"] = 0
        logger.info("after enrichment: total %d signals", len(all_signals))

    leads = qualify_leads(all_signals)

    tier_order = [Tier.CONTACT, Tier.NURTURE, Tier.ARCHIVE]
    min_idx    = tier_order.index(min_tier)
    filtered   = [l for l in leads if tier_order.index(l.tier) <= min_idx]

    logger.info(
        "qualification complete: %d total leads, %d at/above %s",
        len(leads), len(filtered), min_tier.value,
    )

    # Auto-enqueue CONTACT-tier leads into the call queue
    enqueued = await _enqueue_contacts(leads)
    logger.info("auto-enqueued %d CONTACT leads", enqueued)

    return {
        "leads":         filtered,
        "signal_counts": signal_counts,
        "industry_pack": pack_name or "generic",
        "total_leads":   len(leads),
        "contact_count": sum(1 for l in leads if l.tier == Tier.CONTACT),
        "nurture_count": sum(1 for l in leads if l.tier == Tier.NURTURE),
        "enqueued":      enqueued,
        "run_at":        run_at,
        "errors":        errors,
    }


async def _enqueue_contacts(leads: list[Lead]) -> int:
    """Insert CONTACT-tier leads into call_queue. Idempotent — skips if already queued."""
    from datetime import datetime, timedelta, timezone
    import zoneinfo

    enqueued = 0
    tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(tz)

    # Find next slot within call window (8am–9pm Eastern)
    if 8 <= now.hour < 21:
        scheduled = now + timedelta(minutes=2)   # dispatch soon with small jitter
    else:
        # Schedule for 8am next weekday
        next_day = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour >= 21:
            next_day += timedelta(days=1)
        scheduled = next_day

    scheduled_iso = scheduled.astimezone(timezone.utc).isoformat()

    for lead in leads:
        if lead.tier != Tier.CONTACT:
            continue
        priority = 80 if (lead.best_signal and lead.best_signal.signal_type in HIGH_URGENCY) else 50
        qid = await enqueue_call(
            company_name=lead.company_name,
            signal_type=lead.best_signal.signal_type.value if lead.best_signal else "S9",
            signal_summary=lead.primary_summary()[:300],
            source_url=lead.best_signal.source_url if lead.best_signal else "",
            scheduled_for=scheduled_iso,
            priority=priority,
        )
        if qid:
            enqueued += 1

    return enqueued
