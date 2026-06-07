# ICP & Targeting — Issue #5

The agent is **industry-agnostic**: the same engine works for any vertical. The
agent owner picks a target by setting `INDUSTRY_PACK` (see `src/signals/queries.py`,
Issue #6). With none set, generic cross-industry queries run.

## Signal types (from `src/signals/base.py`) and what they mean

| Code | SignalType | Buying meaning | Base score |
|---|---|---|---|
| S1 | REGULATORY_ACTION | Enforcement / fine / FTC / SEC action | 35 (high urgency) |
| S2 | REGULATORY_FILING | 10-K AI/risk disclosure, material weakness | 25 (high urgency) |
| S3 | PRODUCT_CLEARANCE | 510(k), launch, patent, CE mark | 20 |
| S4 | FUNDING_ROUND | Series A–D, IPO, SPAC — budget appeared | 25 (high urgency) |
| S5 | HIRING_SIGNAL | Hiring for AI/data/compliance/quality roles | 15 |
| S6 | EXEC_INTERVIEW | Public interview/quote about AI/data/risk | 15 |
| S7 | PRESS_RELEASE | Company announcement / partnership | 10 |
| S9 | OTHER | Catch-all | 5 |

## Scoring & tiers (from `src/qualify/scorer.py`)

```
company score = Σ(signal base × freshness)         # 1.0 ≤30d, 0.75 ≤60d, 0.5 ≤90d, 0.25 older
             + (#signals − 1) × 8                   # multi-signal bonus
             + 10 if any signal is high-urgency     # S1 / S2 / S4
             + 5  if ≥2 signals within 30 days       # active buying window
clamped 0–100
```

| Tier | Score | Action |
|---|---|---|
| CONTACT | ≥ 60 | hand to voice layer (auto-enqueued) |
| NURTURE | 40–59 | monitor, re-score next cycle |
| ARCHIVE | < 40 | skip |

**Key dynamic:** a single signal tops out around 35 → ARCHIVE. CONTACT tier
essentially requires a company to appear in **two or more sources** (e.g. SEC 10-K
+ a hiring post), which trips the multi-signal + urgency + cluster bonuses. That is
why the hiring source (S5, Issue #7) matters: it creates second signals on
companies already surfaced by SEC/news.

## Example ICPs (shipped as packs in `src/signals/queries.py`)

### FinTech — `INDUSTRY_PACK=fintech`
- **Verticals:** payments, neobank, lending, crypto
- **Buyers:** Chief Compliance Officer, Head of Compliance, BSA/AML Officer, VP Risk
- **Hardest-hitting signal:** S1 regulatory (FDIC/OCC/CFPB), then S4 funding
- **Disqualifiers:** pre-revenue, non-US/EU, no regulated product

### HealthTech — `INDUSTRY_PACK=healthtech`
- **Verticals:** digital health, health systems, medtech
- **Buyers:** Chief Compliance Officer, HIPAA Privacy Officer, Director of Quality, CISO
- **Hardest-hitting signal:** S1 (CMS penalty / OCR settlement), S2 disclosures
- **Disqualifiers:** non-covered entity, research-only

### SaaS / Enterprise — `INDUSTRY_PACK=saas`
- **Verticals:** B2B software, AI/ML platforms, data tooling
- **Buyers:** VP Engineering, Head of AI, ML Platform Lead, Data Governance Manager
- **Hardest-hitting signal:** S4 funding, S5 hiring, S3 launch
- **Disqualifiers:** no production AI, consumer-only

## Buyer personas (demo set)

1. **Compliance lead** (CCO / Head of Compliance) — triggered by S1/S2; pain is
   audit exposure and proving controls fast; objection: "we already have a tool."
2. **Engineering/AI lead** (VP Eng / Head of AI) — triggered by S4/S5/S3; pain is
   shipping AI without regressions/governance; objection: "we'll build it."
3. **Risk/Data exec** (VP Risk / CDO) — triggered by S2/S6; pain is board-level
   risk disclosure; objection: "send me something to review."

## Disqualifiers (applied before outreach)

Drop a lead regardless of score if: no real company name (`Unknown (see link)`),
out of target geography, pre-revenue/too small for the ICP, or consumer-only with
no regulated/AI surface.

## Cross-source matching & enrichment (implemented)

Raw single-source signals top out around 35 → ARCHIVE. Two pieces fix this:

1. **`src/signals/normalize.py`** — canonical company keys so the same company
   matches across SEC + news + hiring ("AMERICAN EXPRESS CO" == "American Express"),
   plus a junk filter that drops headline noise ("Unknown", "Computer Weekly").
2. **`src/signals/enrich.py`** — anchors on real (SEC) company names and searches
   news/hiring for each, so a company gains 2nd/3rd signals → multi-signal + urgency
   bonuses → CONTACT.

Result on a live run: 17 CONTACT leads (vs 0 before), all real multi-signal
companies. Next precision lever: firmographic enrichment (employee count, verified
vertical, direct-dial phone) to gate by company size and improve dialing.
