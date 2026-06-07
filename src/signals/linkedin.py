"""
Hiring signal ingestion (Issue #7) — SignalType.HIRING_SIGNAL (S5).

A company posting roles like "Head of AI Governance", "VP Data Compliance",
"Director of Quality" is actively building and budgeting for the exact problem
we solve — the strongest buying-intent signal we have.

Default backend = Google News RSS biased to hiring/careers. It is zero-key,
zero-friction, and reliable (LinkedIn's job pages block unauthenticated scraping,
so we don't depend on them). Two upgrade paths are stubbed behind the same
interface and can be enabled later without touching the pipeline:
  - LinkedIn guest job RSS  (LINKEDIN_JOBS_RSS=true)  — fragile, best-effort
  - Adzuna API              (ADZUNA_APP_ID/KEY set)   — clean JSON, free tier

Wire-in: add `("LinkedIn_Jobs", fetch_hiring_signals(days, custom_queries=...))`
to the task list in src/qualify/pipeline.py (already done).
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from src.signals.base import Signal, SignalType
from src.signals.news import _parse_rss_date, _extract_company  # reuse shared helpers

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SDR-Voice-Agent/0.1)"}

# Generic, cross-industry buyer roles. Override per vertical via queries.py packs
# or the EXTRA_HIRING_QUERIES env var (comma-separated).
_DEFAULT_ROLES = [
    "Head of AI",
    "VP Data Governance",
    "Director of Compliance",
    "Chief Data Officer",
    "Head of Data Quality",
    "AI Governance",
]

# bias the news query toward active hiring so results read as job activity
_HIRING_BIAS = '(hiring OR "now hiring" OR "job opening" OR careers OR "we\'re hiring")'

# "<Company> is hiring", "jobs at <Company>", "<Company> careers"
_HIRING_COMPANY_PATTERNS = [
    re.compile(r"\bat\s+([A-Z][A-Za-z0-9&\.']+(?:\s+[A-Z][A-Za-z0-9&\.']+){0,3})", ),
    re.compile(r"^([A-Z][A-Za-z0-9&\.']+(?:\s+[A-Z][A-Za-z0-9&\.']+){0,3})\s+(?:is hiring|hiring|careers|seeks|looks to hire|expands)"),
]


def _extract_hiring_company(title: str, description: str) -> str:
    for pat in _HIRING_COMPANY_PATTERNS:
        m = pat.search(title)
        if m:
            return m.group(1).strip()
    return _extract_company(title, description)


async def fetch_hiring_signals(
    days: int = 90,
    limit: int = 12,
    custom_queries: list[str] | None = None,
) -> list[Signal]:
    """Return HIRING_SIGNAL (S5) signals. Zero key (Google News RSS by default)."""
    if os.environ.get("LINKEDIN_JOBS_RSS", "").lower() in ("1", "true", "yes"):
        try:
            sigs = await _fetch_via_linkedin(custom_queries or _DEFAULT_ROLES, days, limit)
            if sigs:
                return sigs
            logger.warning("LinkedIn RSS returned nothing — falling back to News RSS")
        except Exception as exc:
            logger.warning("LinkedIn RSS failed (%s) — falling back to News RSS", exc)

    return await _fetch_via_news(custom_queries, days, limit)


async def _fetch_via_news(
    custom_queries: list[str] | None,
    days: int,
    limit: int,
) -> list[Signal]:
    roles = list(custom_queries) if custom_queries else list(_DEFAULT_ROLES)
    extra = os.environ.get("EXTRA_HIRING_QUERIES", "")
    if extra:
        roles += [q.strip() for q in extra.split(",") if q.strip()]

    signals: list[Signal] = []
    seen: set[str] = set()

    for role in roles:
        query = f'"{role}" {_HIRING_BIAS}'
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(rss_url)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                description = (item.findtext("description") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)

                date = _parse_rss_date(pub_date) if pub_date else datetime.now(timezone.utc)
                if (datetime.now(timezone.utc) - date).days > days:
                    continue

                company = _extract_hiring_company(title, description) or "Unknown (see link)"
                signals.append(Signal(
                    signal_type=SignalType.HIRING_SIGNAL,
                    company_name=company,
                    date=date,
                    summary=title[:250],
                    source_url=link,
                    raw={"role": role, "title": title, "query": query},
                ))
        except Exception as exc:
            logger.warning("Hiring News RSS failed for role '%s': %s", role, exc)

    logger.info("Hiring signals (news backend): fetched %d", len(signals))
    return signals


async def _fetch_via_linkedin(roles: list[str], days: int, limit: int) -> list[Signal]:
    """Best-effort LinkedIn guest job RSS. Often rate-limited/blocked; opt-in only."""
    signals: list[Signal] = []
    seconds = days * 86400
    for role in roles:
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={quote_plus(role)}&f_TPR=r{seconds}&location=United%20States"
        )
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        # LinkedIn returns HTML job cards, not RSS
        cards = re.findall(r'<h3[^>]*job-search-card__title[^>]*>(.*?)</h3>.*?'
                           r'(?:subtitle[^>]*>)(.*?)<', resp.text, re.S)
        for title_raw, company_raw in cards[:limit]:
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            company = re.sub(r"<[^>]+>", "", company_raw).strip()
            if not company:
                continue
            signals.append(Signal(
                signal_type=SignalType.HIRING_SIGNAL,
                company_name=company,
                date=datetime.now(timezone.utc),
                summary=f"Hiring: {title}"[:250],
                source_url=url,
                raw={"role": role, "title": title, "backend": "linkedin"},
            ))
    return signals
