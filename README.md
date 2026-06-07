# SDR Voice Agent

Signal-triggered outbound voice AI for B2B sales development.  
**Free stack:** Pipecat + LiveKit Cloud + Deepgram free tier + local Mistral via LiteLLM.

## What it does

1. A regulatory/market signal fires (FDA warning letter, 510(k) clearance, 10-K AI risk disclosure, etc.)
2. Email goes out → no reply in 5 days → voice follow-up session dispatched
3. AI agent identifies itself as an AI, references the specific regulatory trigger, offers a discovery call
4. Prospect can book a meeting via Cal.com mid-conversation
5. All outcomes logged to database → reviewed in portal

## Free stack

| Layer | Choice | Cost |
|---|---|---|
| Voice transport | LiveKit Cloud (WebRTC) | Free tier, no credit card required |
| STT | Deepgram Nova-3 | Free tier (12K min/yr) |
| TTS | Deepgram Aura | Uses Deepgram key |
| LLM primary | Mistral Small 3 7B (local via Ollama/exo) | Free |
| LLM fallback | GPT-4o mini (optional) | ~$0.0012/call |
| Voice pipeline | Pipecat (open source) | Free |
| Meeting booking | Cal.com | Free tier |
| Database | SQLite (demo) / Postgres (prod) | Free |

**Minimum API keys for demo:** `LIVEKIT_URL` + `LIVEKIT_API_KEY` + `LIVEKIT_API_SECRET` + `DEEPGRAM_API_KEY`
Everything else runs locally or on free tiers.

## Quick start

```bash
git clone https://github.com/nsharma1972/sdr-voice-agent
cd sdr-voice-agent

# 1. Install dependencies
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Fill in LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and DEEPGRAM_API_KEY

# 3. Start local LLM (Ollama example)
ollama pull mistral
ollama serve
# Then start LiteLLM router:
litellm --config litellm.config.yaml

# 4. Start the app
uvicorn src.main:app --reload --port 8000

# 5. Open browser
open http://localhost:8000
```

## Demo flow

1. Open `http://localhost:8000`
2. Enter prospect name, company, pick a regulatory signal type
3. Click **Start Demo Call**
4. Allow microphone access
5. The AI agent speaks first, you respond — full bidirectional voice conversation
6. If you say you want to meet, the agent calls Cal.com and books a slot

## Architecture

```
Browser (LiveKit JS SDK)
       ↕ WebRTC
LiveKit Cloud (free tier)
       ↕
Pipecat pipeline (Python, your server)
   ├── Deepgram Nova-3 (STT)
   ├── LiteLLM → Mistral Small 3 7B local (LLM)
   └── Deepgram Aura (TTS)
       ↓
   Cal.com (meeting booking tool)
```

## Project structure

```
src/
  voice/
    pipeline.py   Pipecat pipeline (STT → LLM → TTS)
    demo.py       LiveKit token creation + bot session management
    tools.py      Cal.com booking tool
    scheduler.py  APScheduler queue (Phase 2 — outbound calling)
    caller.py     Vapi outbound dispatch (Phase 2 — real phone calls)
    assistant.py  Vapi assistant config (Phase 2)
    webhook.py    Vapi webhooks (Phase 2)
  config.py       env-var config
  main.py         FastAPI app
static/
  index.html      browser demo UI
migrations/
  007_voice.sql   call_queue + calls tables
litellm.config.yaml   LiteLLM router config
docs/
  BLUEPRINT.md    full solution design (34 ADRs)
```

## Phase 2 — real outbound calls (after hackathon)

After the browser demo, add Vapi outbound for real phone calls:
- Add `VAPI_API_KEY` + `VAPI_PHONE_NUMBER_ID`
- Use `src/voice/caller.py` to dispatch real phone calls
- Use `src/voice/webhook.py` for Vapi event handling
- Deploy migration `007_voice.sql` for persistent call queue

## License

Apache 2.0 — use freely, fork freely.
