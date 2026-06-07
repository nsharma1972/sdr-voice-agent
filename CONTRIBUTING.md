# Contributing — SDR Voice Agent

## Work division

| Owner | Scope |
|-------|-------|
| **Narendra** | Voice agent, lead scoring, DB, portal UI |
| **Karthik** | Signal sources, ICP definition, outreach templates, demo script |

---

## Current signal sources (already built)

### 1. SEC EDGAR 10-K filings — `src/signals/sec.py`
- Queries: `"artificial intelligence" "material risk"`, `"AI governance" "regulatory"`, `"machine learning" "data integrity" risk`, `"cybersecurity" "AI" "material weakness"`, `"generative AI" risk disclosure`
- Pulls public company annual filings where they disclosed AI/data risk to their board
- Free, no API key — 73 companies in last run

### 2. Google News RSS — `src/signals/news.py`
- Queries: exec interviews about AI governance, data compliance, digital transformation, regulatory pressure
- Free, no API key — 29 signals returned, but company name extraction from headlines is imprecise
- Tip: add tighter queries via `EXTRA_NEWS_QUERIES` env var (comma-separated)

### 3. Press Releases — GlobeNewswire RSS — `src/signals/press.py`
- Catches funding rounds (Series A–E, IPO) and AI/data initiative announcements
- Free, no API key — currently returning 0 (GlobeNewswire may be rate-limiting; investigate)

---

## What's missing — Karthik's issues

### Issue #6 — Industry-specific signal query packs

Right now all queries are generic. Adding vertical-specific queries produces far warmer leads.

**How to add:** create `src/signals/queries.py` with a dict of vertical → query list, then pass them as `custom_queries` to `fetch_exec_interviews()` in `pipeline.py`. Or add a new source file (e.g. `src/signals/fintech.py`) and wire it into `pipeline.py` the same way SEC EDGAR is wired.

Example verticals to target:
- **FinTech** — `"FDIC enforcement" AI`, `"AML compliance" "machine learning"`
- **HealthTech** — `"CMS penalty" "data integrity"`, `"HIPAA" "AI risk"`
- **SaaS / Enterprise** — `"Series B" "AI governance"`, `"data quality" "enterprise" initiative`

### Issue #7 — LinkedIn hiring signal (`src/signals/linkedin.py`)

LinkedIn job postings are the strongest buying-intent signal. A company posting "Head of AI Governance" or "VP of Data Compliance" is actively building — they need tooling.

**Free approach:** LinkedIn publishes a job search RSS feed:
```
https://www.linkedin.com/jobs/search/?keywords=AI+governance&f_TPR=r604800
```
Parse titles for roles like: `Head of AI`, `VP Data Governance`, `Director of Compliance`, `Chief Data Officer`.

Map to `SignalType.HIRING_SIGNAL` (S5), wire into `pipeline.py` alongside the other sources.

---

## Why this matters for lead scoring

Every company currently has only **1 signal → max score ~35 → all ARCHIVE tier**.

The scoring formula rewards multi-signal companies:

```
base score (35) + multi-signal bonus (+8 per extra signal) + cluster bonus (+5)
= 35 + 8 + 5 = 48  → NURTURE
= 35 + 8 + 8 + 5 = 56  → close to CONTACT
= 35 + 10 (urgency) + 8 + 5 = 58  → NURTURE (one more signal → CONTACT)
```

A company appearing in **SEC EDGAR + LinkedIn jobs** = two signals = score jumps to 55–65 = **CONTACT tier** = Narendra calls them.

---

## How to run locally

```bash
git clone https://github.com/nsharma1972/sdr-voice-agent.git
cd sdr-voice-agent
cp .env.example .env
make demo          # starts Ollama check + FastAPI on :8000
```

Open http://localhost:8000 — Leads tab loads automatically.

## Adding a new signal source

1. Create `src/signals/<name>.py` — return `list[Signal]`
2. Add it to the task list in `src/qualify/pipeline.py` (see how `fetch_10k_ai_risk` is wired)
3. Use `SignalType` from `src/signals/base.py` — add a new type there if needed
4. Test: `POST http://localhost:8000/signals/refresh` then check the Leads tab
