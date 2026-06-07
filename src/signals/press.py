"""
Press release signal ingestion — BusinessWire + PRNewswire RSS. Free, no key.

Catches:
  - Funding rounds (S4)
  - Product/partnership announcements (S7)
  - AI/data initiative announcements (S7)

Industry-agnostic: any company issuing a press release about
AI, data, compliance, digital transformation, or a major funding event.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from src.signals.base import Signal, SignalType

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SDR-Voice-Agent/0.1)"}

# BusinessWire category feeds (free RSS, no auth)
_BW_FEEDS = [
    ("https://www.businesswire.com/rss/home/?rss=G7",    "technology"),
    ("https://www.businesswire.com/rss/home/?rss=G6",    "healthcare"),
    ("https://www.businesswire.com/rss/home/?rss=G18",   "financial-services"),
    ("https://www.businesswire.com/rss/home/?rss=G14",   "energy-environment"),
]

# PRNewswire topic feeds (free RSS)
_PRN_FEEDS = [
    ("https://www.prnewswire.com/rss/news-releases-list.rss", "all"),
]

# Keywords that indicate a buying signal in a press release headline
_FUNDING_KEYWORDS = re.compile(
    r"\b(raises|secures|closes|announces|completes)\b.{0,60}\b"
    r"(\$[\d,.]+\s*[MB]illion|\bSeries\s+[A-E]\b|IPO|SPAC)\b",
    re.IGNORECASE,
)
_AI_KEYWORDS = re.compile(
    r"\b(AI|artificial intelligence|machine learning|data governance|"
    r"compliance platform|digital transformation|data integrity)\b",
    re.IGNORECASE,
)


def _parse_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _extract_company_from_pr(title: str) -> str:
    """Press release titles usually start with the company name before a comma or dash."""
    m = re.match(r"^([^,–—|]+?)(?:\s*[,–—|]|\s+Announces|\s+Raises|\s+Closes)", title)
    if m:
        name = m.group(1).strip()
        if 3 < len(name) < 60:
            return name
    return ""


def _classify_signal(title: str, description: str) -> SignalType | None:
    text = f"{title} {description}"
    if _FUNDING_KEYWORDS.search(title):
        return SignalType.FUNDING_ROUND
    if _AI_KEYWORDS.search(text):
        return SignalType.PRESS_RELEASE
    return None   # not relevant


async def _fetch_rss(url: str, days: int) -> list[Signal]:
    signals: list[Signal] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        for item in root.findall(".//item"):
            title       = (item.findtext("title") or "").strip()
            link        = (item.findtext("link") or "").strip()
            pub_date    = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()

            date = _parse_date(pub_date)
            if (datetime.now(timezone.utc) - date).days > days:
                continue

            signal_type = _classify_signal(title, description)
            if signal_type is None:
                continue

            company = _extract_company_from_pr(title)
            if not company:
                continue

            signals.append(Signal(
                signal_type=signal_type,
                company_name=company,
                date=date,
                summary=title[:300],
                source_url=link,
                raw={"title": title, "description": description[:400]},
            ))
    except Exception as exc:
        logger.warning("Press RSS fetch failed %s: %s", url, exc)
    return signals


async def fetch_press_releases(days: int = 30) -> list[Signal]:
    """
    Fetch recent press releases from BusinessWire and PRNewswire.
    Shorter default window (30 days) since press releases go stale quickly.
    """
    import asyncio

    tasks = [_fetch_rss(url, days) for url, _ in (_BW_FEEDS + _PRN_FEEDS)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals: list[Signal] = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)

    logger.info("Press releases: fetched %d signals", len(signals))
    return signals
