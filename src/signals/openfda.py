"""
openFDA signal ingestion — free, no API key required.

Pulls:
  S3  510(k) device clearances (recent)
  S1  Drug/device enforcement actions (warning letter proxy)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from src.signals.base import Signal, SignalType

logger = logging.getLogger(__name__)

_BASE = "https://api.fda.gov"
_HEADERS = {"User-Agent": "SDR-Voice-Agent/0.1 (open source hackathon project)"}


def _since(days: int = 180) -> str:
    d = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return d


async def fetch_510k(days: int = 180, limit: int = 50) -> list[Signal]:
    """Recent 510(k) clearances — companies that just got a device cleared."""
    since = _since(days)
    url = (
        f"{_BASE}/device/510k.json"
        f"?search=decision_date:[{since}+TO+2099-01-01]"
        f"&limit={limit}&sort=decision_date:desc"
    )
    signals: list[Signal] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        for r in results:
            company = r.get("applicant", "").strip()
            if not company:
                continue
            date_str = r.get("decision_date", "")
            try:
                date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            except Exception:
                date = datetime.now(timezone.utc)
            signals.append(Signal(
                signal_type=SignalType.CLEARANCE_510K,
                company_name=company,
                date=date,
                summary=(
                    f"510(k) clearance for '{r.get('device_name', 'unknown device')}' "
                    f"({r.get('advisory_committee_description', '')}). "
                    f"Decision: {r.get('decision_description', '')}."
                ),
                source_url=f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={r.get('k_number','')}",
                raw=r,
            ))
    except Exception as exc:
        logger.warning("openFDA 510k fetch failed: %s", exc)
    logger.info("openFDA 510k: fetched %d signals", len(signals))
    return signals


async def fetch_enforcement(days: int = 180, limit: int = 50) -> list[Signal]:
    """
    FDA enforcement actions (recalls, market withdrawals) as a warning-signal proxy.
    True warning letters don't have a clean openFDA API; enforcement is the best free proxy.
    """
    since = _since(days)
    url = (
        f"{_BASE}/drug/enforcement.json"
        f"?search=report_date:[{since}+TO+2099-01-01]"
        f"&limit={limit}&sort=report_date:desc"
    )
    signals: list[Signal] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        for r in results:
            company = r.get("recalling_firm", "").strip()
            if not company:
                continue
            date_str = r.get("report_date", "")
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                date = datetime.now(timezone.utc)
            signals.append(Signal(
                signal_type=SignalType.FDA_WARNING_LETTER,
                company_name=company,
                date=date,
                summary=(
                    f"FDA enforcement action: {r.get('reason_for_recall', '')[:200]}. "
                    f"Class {r.get('classification', '')} — {r.get('status', '')}."
                ),
                source_url="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
                raw=r,
            ))
    except Exception as exc:
        logger.warning("openFDA enforcement fetch failed: %s", exc)
    logger.info("openFDA enforcement: fetched %d signals", len(signals))
    return signals


async def fetch_all(days: int = 180) -> list[Signal]:
    import asyncio
    results = await asyncio.gather(
        fetch_510k(days),
        fetch_enforcement(days),
        return_exceptions=True,
    )
    signals = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)
    return signals
