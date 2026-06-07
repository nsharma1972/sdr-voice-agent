"""
SEC EDGAR signal ingestion — free, no API key.

Industry-agnostic: searches 10-K filings across ALL public companies
for AI risk, data governance, or material-weakness language.

Any company disclosing these risks is a potential buyer — the board
and auditors will eventually ask for a remediation plan.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from src.signals.base import Signal, SignalType

logger = logging.getLogger(__name__)

_EFTS = "https://efts.sec.gov/LATEST/search-index"
_HEADERS = {
    "User-Agent": "SDR-Voice-Agent/0.1 (open source; contact: noreply@example.com)"
}

# Cross-industry AI / data governance risk queries
_QUERIES = [
    '"artificial intelligence" "material risk"',
    '"AI governance" "regulatory"',
    '"machine learning" "data integrity" risk',
    '"cybersecurity" "AI" "material weakness"',
    '"generative AI" risk disclosure',
]


async def fetch_10k_ai_risk(days: int = 180, limit: int = 20) -> list[Signal]:
    """10-K filings (any industry) that disclose AI/data risk language."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    signals: list[Signal] = []

    for query in _QUERIES:
        url = (
            f"{_EFTS}"
            f"?q={query.replace(' ', '+')}"
            f"&forms=10-K"
            f"&dateRange=custom&startdt={since}"
            f"&hits.hits.total.value=true&hits.hits._source=true"
            f"&hits.hits.highlight=true"
        )
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS) as client:
                resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:limit]:
                src         = hit.get("_source", {})
                # EFTS returns display_names as a list: ['DOMO, INC.  (DOMO)  (CIK 0001234)']
                raw_names = src.get("display_names") or [src.get("entity_name", "")]
                entity = raw_names[0].split("(")[0].strip(" ,") if raw_names else ""
                if not entity:
                    continue
                file_date_s = src.get("file_date", "")
                try:
                    date = datetime.strptime(file_date_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except Exception:
                    date = datetime.now(timezone.utc)

                highlight = hit.get("highlight", {})
                snippet = ""
                for snippets in highlight.values():
                    if snippets:
                        snippet = (
                            snippets[0]
                            .replace("<em>", "")
                            .replace("</em>", "")[:300]
                        )
                        break

                signals.append(Signal(
                    signal_type=SignalType.REGULATORY_FILING,
                    company_name=entity,
                    date=date,
                    summary=f"10-K AI/data risk disclosure ({file_date_s}): {snippet}",
                    source_url=(
                        f"https://www.sec.gov/cgi-bin/browse-edgar"
                        f"?action=getcompany&company={entity.replace(' ', '+')}"
                        f"&type=10-K&dateb=&owner=include&count=5"
                    ),
                    raw=src,
                ))
        except Exception as exc:
            logger.warning("SEC EDGAR query '%s' failed: %s", query, exc)

    # deduplicate: keep most recent per company
    seen: dict[str, Signal] = {}
    for s in signals:
        key = s.company_name.lower()
        if key not in seen or s.date > seen[key].date:
            seen[key] = s

    result = list(seen.values())
    logger.info("SEC EDGAR 10-K: %d raw → %d unique", len(signals), len(result))
    return result
