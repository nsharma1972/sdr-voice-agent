# SDR Voice Agent

Signal-triggered outbound voice AI for B2B sales development. Built on Vapi + LiteLLM.

## What it does

1. A regulatory/market signal fires (FDA warning letter, 510(k) clearance, 10-K AI risk disclosure, etc.)
2. Email goes out → no reply in 5 days → voice follow-up call dispatched
3. Vapi places the call; AI agent identifies itself as an AI, references the specific regulatory trigger, offers a discovery call
4. If prospect answers: books a meeting via Cal.com tool call mid-conversation
5. If no answer: leaves an 18–25 second signal-specific voicemail (raises email reply rate ~115%)
6. All outcomes logged to Postgres → reviewed in a portal

## Architecture

```
Signal (openFDA/SEC/ClinTrials) → Score → Email → [5 days, no reply] → Voice
                                                                          ↓
                                                     Vapi (STT: Deepgram Nova-3)
                                                          ↓
                                               LiteLLM Router (local cluster)
                                              /                          \
                                   Mistral Small 3 7B              GPT-4o mini
                                   (local, ~80ms)                  (cloud fallback)
                                              \                          /
                                           ElevenLabs Flash v2.5 (TTS)
                                                          ↓
                                             Cal.com booking tool
                                                          ↓
                                              Postgres → Portal review
```

## Stack

| Layer | Choice |
|---|---|
| Voice infra | Vapi |
| STT | Deepgram Nova-3 |
| TTS | ElevenLabs Flash v2.5 |
| LLM primary | Mistral Small 3 7B (local, Apache 2.0) |
| LLM fallback | GPT-4o mini |
| LLM router | LiteLLM (latency-based routing) |
| Meeting booking | Cal.com |
| Backend | Python / FastAPI |
| Database | Postgres |

## ICP (default configuration)

Biotech / Pharma / Medical Device companies:
- 300–3,000 employees, US-HQ, active FDA exposure
- Buyer personas: Head of Quality, Head of ClinOps, VP IT
- Fit score ≥ 60 required before any outreach

## Compliance (TCPA / FCC)

- AI disclosure within first 5 seconds (FCC 2024 ruling)
- Business landlines only in Phase 1 (TCPA mobile consent requirement)
- DNC registry scrub before first call, every 31 days
- Real-time opt-out suppression (< 10 seconds)
- 8am–9pm prospect local time enforcement

## Quick start

```bash
cp .env.example .env
# fill in VAPI_API_KEY, LITELLM_BASE_URL, CALCOM_API_KEY, DATABASE_URL
pip install -e ".[dev]"
python -m src.main
```

## Project structure

```
src/
  voice/
    assistant.py   # Vapi assistant config builder
    webhook.py     # FastAPI webhook handlers (assistant-request, function-call, end-of-call)
    caller.py      # outbound call dispatcher
    scheduler.py   # APScheduler call queue (60s tick)
    tools.py       # Cal.com booking tool implementation
  config.py        # env-var config
  models.py        # SQLAlchemy / Pydantic models
  main.py          # FastAPI app entry point
migrations/
  007_voice.sql    # call_queue + calls tables
docs/
  BLUEPRINT.md     # full solution design (34 ADRs)
```

## License

Apache 2.0
