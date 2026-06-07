# Hackathon Demo Script & E2E Runbook — Issue #9

**Target: under 4 minutes. Live demo, no slides.**
Flow: Hook → Pick a vertical → Refresh signals → Review a lead → Live call → Wrap.

## The angle

> "Cold calling converts at ~2%. We only call when there's a *specific* reason — a
> regulatory filing, a funding round, a new compliance hire. And it retargets to any
> industry by flipping one environment variable."

## Pre-flight checklist (BEFORE you present)

- [ ] `make install` (or `pip install -e ".[dev]"`) + deps: `aiosqlite`, `httpx`
- [ ] Local LLM up: `ollama serve` + `litellm --config litellm.config.yaml`
- [ ] `.env` has `DAILY_API_KEY` + `DEEPGRAM_API_KEY`
- [ ] Network reaches `news.google.com` and `efts.sec.gov`
- [ ] `make demo` boots and `http://localhost:8000` loads the Leads tab
- [ ] One full dry run with Naren as the prospect, timed
- [ ] **Fallback ready:** screenshot of the lead list + a saved transcript

## Smoke test (proves L1/L2 + S5 hiring source work)

```bash
# generic
curl -s -X POST "localhost:8000/signals/refresh?days=120" | python3 -m json.tool
# vertical pack (Issue #6) — note LinkedIn_Jobs count = S5 signals (Issue #7)
INDUSTRY_PACK=fintech make dev    # then in another shell:
curl -s -X POST "localhost:8000/signals/refresh?days=120" | python3 -m json.tool
```
Expect `signal_counts` to include `SEC_EDGAR`, `News_RSS`, `LinkedIn_Jobs`, and an
`industry_pack` field.

## The 3-minute script

**1. Hook (20s)** — the line above.

**2. Pick a vertical (20s)**
> "Watch me point it at fintech." Show `INDUSTRY_PACK=fintech` and open
> `src/signals/queries.py` — "this file is the whole ICP; swap it for healthtech or
> saas and the agent retargets."

**3. Refresh signals (35s)**
```bash
curl -X POST "localhost:8000/signals/refresh?days=120"
```
> "That just pulled live signals — SEC 10-K filings, news, and **hiring posts** —
> scored every company, and queued the hot ones." Point at `signal_counts`
> (including `LinkedIn_Jobs`) and `contact_count`.

**4. Review a lead (30s)**
> Open the Leads tab (or `GET /leads`). Pick the top lead, show its **score
> breakdown** — base signal scores, multi-signal bonus, urgency bonus. "This is
> *why* it's worth a call, not a guess."

**5. Live call (90s)**
> Force the call for the chosen company:
> ```bash
> curl -X POST "localhost:8000/leads/<Company>/enqueue"
> ```
> Then click **Start Call** in the portal. AI speaks first, identifies as AI,
> references the signal, you respond, it handles an objection, offers + books a
> meeting.

**6. Wrap (20s)**
> "Free stack — Pipecat, local Mistral, edge-TTS, Daily.co. Real signals, real
> voice, any industry in one line."

## Timing budget

| Section | Target |
|---|---|
| Hook | 0:20 |
| Pick vertical | 0:20 |
| Refresh | 0:35 |
| Lead review | 0:30 |
| Live call | 1:30 |
| Wrap | 0:20 |
| **Total** | **3:35** |

## Honest demo note — guaranteeing a callable lead

Enrichment (`src/signals/enrich.py`) + normalized grouping now produce CONTACT
leads organically: a recent run yielded **17 CONTACT** leads (e.g. Bank of New York
Mellon, American Express, Clarivate) auto-enqueued to the call queue. So the live
demo can pick a real CONTACT lead in the portal and call it.

Fallbacks if a given refresh is thin:
1. **Force the call** with `POST /leads/{company}/enqueue` on any lead — bypasses
   the tier gate.
2. Widen the window (`?days=180`) or set `INDUSTRY_PACK` to bias toward your vertical.

## Acceptance (from the issue) — log your run

```
Run date/time:
Industry pack:
signal_counts (incl. LinkedIn_Jobs):
# leads / # CONTACT:
Call connected? (y/n):
Meeting booked? (y/n):
Notes:
```
