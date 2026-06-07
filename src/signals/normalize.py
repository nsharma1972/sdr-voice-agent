"""
Company-name normalization + validity filtering.

Two jobs:
  1. normalize_company()  — canonical key so the SAME company from different
     sources groups together ("AMERICAN EXPRESS CO" == "American Express, Inc.").
  2. is_valid_company()   — drop junk that headline extraction produces
     (publications, job-board terms, sentence fragments, "Unknown (see link)").

Used by the qualifier when grouping signals into leads, and by enrichment.
"""
from __future__ import annotations

import re

# legal suffixes / filler stripped when building the canonical key
_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "llp",
    "lp", "ltd", "limited", "plc", "sa", "ag", "nv", "se", "gmbh", "holdings",
    "holding", "group", "the", "and",
}

# obvious non-company tokens — if a name is dominated by these it's noise
_JUNK_TOKENS = {
    "unknown", "see", "link", "weekly", "news", "daily", "times", "post",
    "journal", "review", "research", "report", "magazine", "media", "press",
    "careers", "career", "jobs", "hiring", "science", "governance",
    "challenges", "operational", "officer", "director", "associate", "named",
    "college", "university", "athletics", "interview", "executive", "deputy",
    "chief", "isn", "data", "center", "tech", "podcast", "blog", "newsletter",
    "how", "why", "what", "when", "the", "best", "top",
}


def normalize_company(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"[.,&/()'\"’]", " ", s)        # drop punctuation
    s = re.sub(r"\s+", " ", s).strip()
    tokens = [t for t in s.split(" ") if t and t not in _SUFFIXES]
    return " ".join(tokens).strip()


def is_valid_company(name: str) -> bool:
    """Conservative filter: keep things that plausibly name a company."""
    if not name:
        return False
    low = name.lower()
    if "unknown" in low:
        return False

    norm = normalize_company(name)
    if not norm:
        return False

    words = norm.split()
    # too long to be a company name (likely a headline fragment)
    if len(words) > 5:
        return False
    # single very short token like "ai", "is"
    if len(words) == 1 and len(words[0]) <= 2:
        return False
    # mostly junk tokens?
    junk = sum(1 for w in words if w in _JUNK_TOKENS)
    if junk and junk >= (len(words) + 1) // 2:
        return False
    # must contain at least one real-looking word (>=3 chars, alphabetic-ish)
    if not any(len(w) >= 3 and re.search(r"[a-z]", w) for w in words):
        return False
    return True


def pick_display_name(names: list[str]) -> str:
    """Among raw names that share a normalized key, pick the cleanest to show.
    Prefer Title/UPPER-cased, reasonably short, real-looking ones."""
    valid = [n for n in names if is_valid_company(n)] or names

    def _score(n: str) -> tuple:
        has_case = any(c.isupper() for c in n)
        wc = len(n.split())
        return (1 if has_case else 0, -abs(wc - 2), -len(n))

    return max(valid, key=_score).strip()
