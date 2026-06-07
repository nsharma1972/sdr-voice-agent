"""
Industry-specific signal query packs (Issue #6).

Generic queries catch broad signal with low precision. Vertical packs filter to
the right buyers. The agent OWNER picks a vertical at runtime via the
INDUSTRY_PACK env var (e.g. INDUSTRY_PACK=fintech). With none set, the always-on
generic queries run, so the system stays industry-agnostic by default.

Each pack supplies:
  - news_queries    -> passed to fetch_exec_interviews(custom_queries=...)
  - hiring_queries  -> passed to fetch_hiring_signals(custom_queries=...)  [roles]

To add a vertical: add an entry below. No code changes elsewhere.
"""
from __future__ import annotations

import os

INDUSTRY_QUERIES: dict[str, dict[str, list[str]]] = {
    "fintech": {
        "news_queries": [
            '"fintech" "compliance" OR "AML" funding',
            '"payments" company "SOC 2" OR "audit"',
            '"FDIC" OR "OCC" OR "CFPB" enforcement fintech',
            'fintech "Chief Compliance Officer" appointed',
        ],
        "hiring_queries": [
            "AML Compliance",
            "BSA Officer",
            "Head of Financial Crime",
            "VP Risk fintech",
        ],
    },
    "healthtech": {
        "news_queries": [
            '"healthtech" "HIPAA" OR "compliance" funding',
            '"CMS penalty" OR "OCR settlement" "data"',
            'health system "AI" "data integrity" initiative',
            'digital health "Chief Compliance Officer" OR "CISO" named',
        ],
        "hiring_queries": [
            "Healthcare Compliance",
            "HIPAA Privacy Officer",
            "Director of Quality healthcare",
            "Head of Clinical Data",
        ],
    },
    "saas": {
        "news_queries": [
            '"Series B" OR "Series C" "AI governance" SaaS',
            'enterprise SaaS "data quality" initiative',
            'B2B software "SOC 2" OR "ISO 27001" compliance',
            'SaaS company "VP of Data" OR "Head of AI" appointed',
        ],
        "hiring_queries": [
            "Head of AI",
            "ML Platform Lead",
            "Data Governance Manager",
            "VP Engineering SaaS",
        ],
    },
}


def get_active_pack() -> tuple[str | None, dict[str, list[str]]]:
    """Return (pack_name, pack) for the INDUSTRY_PACK env var, or (None, {})."""
    name = os.environ.get("INDUSTRY_PACK", "").strip().lower()
    if name and name in INDUSTRY_QUERIES:
        return name, INDUSTRY_QUERIES[name]
    return None, {}


def pack_news_queries() -> list[str]:
    return get_active_pack()[1].get("news_queries", [])


def pack_hiring_queries() -> list[str]:
    return get_active_pack()[1].get("hiring_queries", [])


def available_packs() -> list[str]:
    return sorted(INDUSTRY_QUERIES.keys())
