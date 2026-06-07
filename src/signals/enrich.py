"""
Targeted enrichment — turn single-signal companies into multi-signal leads.

Generic news/jobs searches rarely name the same company that SEC surfaces, so
cross-source overlap (the thing that lifts a lead to CONTACT) almost never happens
organically. Enrichment fixes that: it takes companies we already KNOW are real
(clean SEC names) and searches news for each one specifically — funding, hiring,
regulatory, exec moves. The stored company_name is set EXACTLY to the anchor name,
so the new signals merge with the original under the same lead.

Result: a company with an SEC 10-K risk filing (S2) that also recently raised /
is hiring / had an exec quote now carries 2–3 signals → multi-signal + urgency
bonuses → CONTACT tier.
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from src.signals.base import Signal, SignalType
from src.signals.news import _parse_rss_date
from src.signals.normalize import is_valid_company

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SDR-Voice-Agent/0.1)"}

# one combined query per company catches the high-value triggers
_ENRICH_TERMS = (
    '(raises OR funding OR "Series" OR acquires OR IPO OR '
    'hiring OR "is hiring" OR appoints OR names OR '
    'fined OR penalty OR enforcement OR lawsuit OR launches OR partnership)'
)


def _classify(title: str, summary: str) -> SignalType:
    t = f"{title} {summary}".lower()
    if any(k in t for k in ("fined", "penalty", "enforcement", "lawsuit", "sanction", "violation")):
        return SignalType.REGULATORY_ACTION          # S1
    if any(k in t for k in ("raises", "raised", "funding", "series ", "ipo", "acquires", "acquisition", "spac")):
        return SignalType.FUNDING_ROUND              # S4
    if any(k in t for k in ("hiring", "is hiring", "job opening", "careers", "open role")):
        return SignalType.HIRING_SIGNAL              # S5
    if any(k in t for k in ("appoints", "names", "new ceo", "new cto", "hires", "interview")):
        return SignalType.EXEC_INTERVIEW             # S6
    if any(k in t for k in ("launch", "launches", "unveils", "clearance", "approved")):
        return SignalType.PRODUCT_CLEARANCE          # S3
    return SignalType.PRESS_RELEASE                  # S7


async def _enrich_one(client: httpx.AsyncClient, company: str, days: int, per_company: int) -> list[Signal]:
    query = f'"{company}" {_ENRICH_TERMS}'
    url = (f"https://news.google.com/rss/search?q={quote_plus(query)}"
           f"&hl=en-US&gl=US&ceid=US:en")
    out: list[Signal] = []
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as exc:
        logger.debug("enrich failed for %s: %s", company, exc)
        return out

    cl = company.lower().split()[0]  # first token must appear → avoid false matches
    for item in root.findall(".//item")[: per_company * 3]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()
        if not title or cl not in title.lower():
            continue
        date = _parse_rss_date(pub) if pub else datetime.now(timezone.utc)
        if (datetime.now(timezone.utc) - date).days > days:
            continue
        out.append(Signal(
            signal_type=_classify(title, desc),
            company_name=company,                  # anchor → guarantees the merge
            date=date,
            summary=title[:250],
            source_url=link,
            raw={"title": title, "enriched": True},
        ))
        if len(out) >= per_company:
            break
    return out


async def enrich_companies(
    companies: list[str],
    days: int = 120,
    max_companies: int = 25,
    per_company: int = 3,
) -> list[Signal]:
    """Find extra signals for known-real companies. Returns merged Signal list."""
    # dedupe, keep valid, cap for latency
    seen: set[str] = set()
    targets: list[str] = []
    for c in companies:
        key = c.lower().strip()
        if key in seen or not is_valid_company(c):
            continue
        seen.add(key)
        targets.append(c)
        if len(targets) >= max_companies:
            break

    if not targets:
        return []

    async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[_enrich_one(client, c, days, per_company) for c in targets],
            return_exceptions=True,
        )

    signals: list[Signal] = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)
    logger.info("Enrichment: %d extra signals across %d companies", len(signals), len(targets))
    return signals
