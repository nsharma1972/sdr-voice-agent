# SDR Voice Agent

**Signal-triggered AI SDR — detects buying signals, qualifies leads, and runs live voice calls to book meetings.**

Built at Sundai Club (June 2026). Runs on a fully free stack: **LiveKit · Deepgram · Groq · FastAPI · SQLite**.

---

## What it does

1. **Detect** — pulls real-time buying signals from the open web: SEC filings, funding/press news, and hiring activity.
2. **Qualify** — groups signals by company, scores each 0–100 (recency, multiple signals, urgency), and tiers them **CONTACT / NURTURE / ARCHIVE**.
3. **Call** — for CONTACT-tier leads, an AI agent places a live browser voice call, opens with the *specific* signal ("…about your recent funding round"), handles the conversation, and books a meeting.
4. **Log** — every call's transcript, outcome, and booking status is saved and reviewed in a portal.

No cold lists, no manual research — it only calls companies showing a real reason to talk.

---

## Architecture (two halves)

```
SIGNALS ──▶ QUALIFY ──▶ call_queue ──▶ VOICE CALL ──▶ DB / PORTAL
 (L1)        (L2)        (contract)      (L3)           (L4)
```

**Lead intelligence (L1–L2)** decides *who to call and why*.
**Voice + persistence (L3–L4)** *makes the call and records it.*

Voice pipeline:
```
Browser ⇄ LiveKit (WebRTC) ⇄ Deepgram STT ─▶ Groq LLM ─▶ Deepgram TTS ─▶ back to Browser
```

Full details: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md).

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Signal sources | SEC EDGAR · Google News · GlobeNewswire · job postings | free, no API key |
| Qualification | custom scorer (Python) | deterministic, explainable |
| Voice transport | LiveKit (WebRTC) | free tier, no card |
| Speech-to-text | Deepgram nova-2 | free tier |
| LLM | Groq `llama-3.1-8b-instant` (~200ms) | local Ollama/Mistral fallback |
| Text-to-speech | Deepgram Aura (ElevenLabs optional) | uses Deepgram key |
| API + DB | FastAPI · SQLite | portal + persistence |

## Quick start

```bash
git clone https://github.com/nsharma1972/sdr-voice-agent
cd sdr-voice-agent

# 1. install
pip install -e ".[dev]"

# 2. configure
cp .env.example .env
#   required: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, DEEPGRAM_API_KEY
#   LLM: set GROQ_API_KEY (fast, free)  — OR run Ollama locally (see below)

# 3. (only if NOT using Groq) local LLM
ollama serve && ollama pull mistral     # then point LITELLM_BASE_URL at Ollama

# 4. run
uvicorn src.main:app --port 8000
open http://localhost:8000
```

**Lead generation needs no keys at all** — the signal + qualification pipeline runs on free public data. Keys are only needed for the voice call.

## Demo flow

1. Open `http://localhost:8000` → **Leads** tab → **Refresh Signals**
   → live signals are fetched, scored, and ranked; CONTACT leads queued.
2. Pick a CONTACT lead → **Call** → allow mic.
3. The AI opens with the specific signal, you talk, and on "yes" it books and closes.
4. **Calls** tab shows the transcript + outcome.

## Project structure

```
src/
  signals/      L1 — signal ingestion (free web sources)
    sec.py        SEC EDGAR 10-K AI/risk filings
    news.py       Google News RSS (exec interviews / news)
    press.py      GlobeNewswire (funding / announcements)
    linkedin.py   hiring signals (job postings)
    openfda.py    FDA pack (opt-in)
    enrich.py     per-company enrichment (more signals per lead)
    queries.py    industry query packs (INDUSTRY_PACK)
    normalize.py  company-name canonicalization
    base.py       Signal model + SignalType + base scores
  qualify/      L2 — qualification
    pipeline.py   orchestrates sources → enrich → score → enqueue
    scorer.py     0–100 scoring + CONTACT/NURTURE/ARCHIVE tiers
  voice/        L3 — voice (LiveKit + Deepgram + Groq via Pipecat)
    pipeline.py   STT → SDRTurnPolicy (LLM) → TTS
    demo.py       LiveKit room + bot session
    caller.py / assistant.py / webhook.py   Vapi real-phone path (Phase 2)
  db.py         L4 — SQLite (call_queue + calls)
  main.py       FastAPI app (routes)
static/
  index.html    portal UI (Leads / Demo Call / Calls)
docs/
  HOW_IT_WORKS.md   architecture + end-to-end
  ICP.md            ideal customer profile
```

## Roadmap

- **Real outbound phone** — wire Vapi/Twilio for PSTN calls to mobile numbers.
- **Live calendar booking** — auto-send a Cal.com invite the moment a prospect agrees.
- **Contact enrichment** — company → named decision-maker + phone (the gap before real dialing).
- **Auto-generated targeting** — turn a product description into the signal queries via an LLM.
- **CRM push** — booked meetings + transcripts into Salesforce / HubSpot.

## Team

- **Karthik Godugolla** — lead intelligence (L1–L2): signal ingestion, enrichment, company normalization, scoring/qualification, industry packs.
- **Narendra Sharma** — voice + platform (L3–L4): LiveKit/Deepgram/Groq pipeline, turn-taking, DB, portal.

## License

Apache 2.0.
