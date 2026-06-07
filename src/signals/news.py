"""
News signal ingestion — Google News RSS. Free, no API key.

Industry-agnostic: searches for exec interviews/quotes about
AI adoption, data governance, digital transformation, compliance —
buying-intent signals that span any vertical.

Add industry-specific queries via EXTRA_QUERIES env var or the
`custom_queries` parameter.
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx

from src.signals.base import Signal, SignalType

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SDR-Voice-Agent/0.1)"}

# Generic buying-intent queries — work across industries
_DEFAULT_QUERIES = [
    # AI / data governance pressure
    '"AI governance" "executive" interview',
    '"data compliance" "digital transformation" CEO OR VP OR CTO',
    '"AI risk" "board" "enterprise" 2025 OR 2026',
    # Regulatory pressure (cross-industry)
    '"regulatory compliance" challenge "AI" company',
    # Operational / scaling pain
    '"data integrity" "enterprise" problem OR challenge OR investment',
    '"quality management" AI initiative announcement',
]


def _parse_rss_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _extract_company(title: str, description: str) -> str:
    text = f"{title} {description}"
    # Match capitalized multi-word sequences likely to be company names
    candidates = re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}(?:\s+(?:Inc|Corp|Ltd|LLC|AG|SE|GmbH|Co))?)\b", text)
    skip = {"The", "This", "For", "With", "CEO", "CTO", "VP", "AI", "From", "When",
            "How", "Why", "What", "New", "Top", "Best", "First", "On", "In", "At"}
    for c in candidates:
        if c not in skip and len(c) > 5:
            return c
    return ""


async def fetch_exec_interviews(
    days: int = 90,
    limit: int = 15,
    custom_queries: list[str] | None = None,
) -> list[Signal]:
    """Executive public interviews / press on AI/compliance/transformation."""
    queries = list(_DEFAULT_QUERIES)
    # Allow extra queries from env (comma-separated)
    extra = os.environ.get("EXTRA_NEWS_QUERIES", "")
    if extra:
        queries += [q.strip() for q in extra.split(",") if q.strip()]
    if custom_queries:
        queries += custom_queries

    signals: list[Signal] = []

    for query in queries:
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(rss_url)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            items = root.findall(".//item")[:limit]
            for item in items:
                title       = (item.findtext("title") or "").strip()
                link        = (item.findtext("link") or "").strip()
                pub_date    = (item.findtext("pubDate") or "").strip()
                description = (item.findtext("description") or "").strip()

                date = _parse_rss_date(pub_date) if pub_date else datetime.now(timezone.utc)
                if (datetime.now(timezone.utc) - date).days > days:
                    continue

                company = _extract_company(title, description)
                if not company:
                    company = "Unknown (see link)"

                signals.append(Signal(
                    signal_type=SignalType.EXEC_INTERVIEW,
                    company_name=company,
                    date=date,
                    summary=title[:250],
                    source_url=link,
                    raw={"title": title, "description": description[:400], "query": query},
                ))
        except Exception as exc:
            logger.warning("News RSS failed for query '%s': %s", query, exc)

    logger.info("News RSS: fetched %d signals", len(signals))
    return signals
