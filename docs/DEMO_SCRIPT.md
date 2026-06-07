# Hackathon Demo Script — SDR Voice Agent

**Total time: 3–4 minutes**
**Audience: judges, investors, technical evaluators**

---

## Setup (before judges arrive)

- [ ] Server running: `make demo` → confirm `http://localhost:8000` loads
- [ ] `.env` has `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`
- [ ] Browser tab open on the Leads page
- [ ] Mic tested (headphones recommended to avoid echo)
- [ ] Backup: demo data seeded via "⚡ Load Demo Data" button

---

## The pitch (30 seconds)

> "Most SDR tools help you send emails. This one listens to the market — regulatory filings, funding rounds, job postings — scores which companies are actively signaling a buying need, and then makes the outbound call for you using a voice AI that speaks like a rep, handles objections, and books the meeting."

---

## Live demo flow

### Step 1 — Show the leads page (45 seconds)

Open the **Leads** tab. Point at the table:

> "These leads came from real public sources — SEC 10-K filings, Google News, press releases. Every company here disclosed an AI governance risk, just raised funding, or is hiring a Head of AI. The scoring engine ranked them by buying intent. Anything above 60 is ready to call."

If no CONTACT leads: click **⚡ Load Demo Data** → 5 green CONTACT leads appear instantly.

Filter to **Contact** tier. Pick **Rippling** or **Glean**.

---

### Step 2 — Start the call (15 seconds)

Click **Call** on the lead → Demo Call tab opens pre-filled.

> "The agent already knows why we're calling — it picked up the signal automatically. I just click Start."

Click **Start Demo Call**. Allow microphone. Wait for the agent to speak.

---

### Step 3 — The live conversation (60–90 seconds)

Agent opens:
> *"Hi Alex, I'm an AI assistant calling for [sender]. I noticed recent activity at Rippling around AI governance. Do you have 90 seconds?"*

**Play the interested prospect:**

| You say | Agent does |
|---------|-----------|
| "Sure, go ahead." | Asks if AI governance is active for your team |
| "Yes, it is." | Asks to schedule a 15-min call |
| "Let's do it." | Asks for your email |
| "alex@rippling.com" | Confirms invite, ends gracefully |

**Alternative — play the skeptical prospect:**

| You say | Agent does |
|---------|-----------|
| "I'm busy right now." | Asks for a better time |
| "We already have this covered." | Probes whether it's fully internal or worth comparing notes |
| "Not interested." | Politely closes, no pushback |

---

### Step 4 — Show the call log (30 seconds)

Click **Calls** tab. The call record appears with:
- Outcome auto-set (interested / booked / not_interested)
- Transcript of the full conversation
- Review buttons (Interested / Booked / Not Qualified)

> "Every call is logged. The outcome was set automatically from the conversation — no rep needed to update a CRM. A human reviewer can flip the status and add notes."

---

## Judge questions — prepared answers

**"Is this real AI or scripted?"**
> "The STT and TTS are live Deepgram — real speech recognition and synthesis. The turn logic is deterministic for demo reliability, but the architecture supports a full LLM (Mistral is already wired in) for production."

**"How do you get the leads?"**
> "Three free public sources right now — SEC EDGAR 10-K filings, Google News RSS, and GlobeNewswire press releases. The enrichment layer cross-references companies across sources so a company with two signals scores high enough to call."

**"What does it cost to run?"**
> "For the demo stack: Deepgram free tier covers 12K minutes/year of STT. LiveKit free tier covers the WebRTC transport. The scoring and DB are local. Total cost to demo: effectively zero."

**"What's the path to production?"**
> "Replace the deterministic policy with the LLM layer (already built, just disabled for latency), add Twilio for real outbound phone calls, and plug Cal.com in for actual calendar invites. The signal ingestion and scoring engine stays exactly as is."

**"What's Karthik's role?"**
> "Karthik owns the signal layer — industry-specific query packs, LinkedIn hiring signals, ICP definitions. The engine is pluggable: add a new signal source file, wire it in, and the leads table updates automatically."

---

## Fallback if voice breaks

If LiveKit/Deepgram fails mid-demo:

1. Stay calm — pull up the Leads tab
2. Show the scored lead list and explain the signal sources
3. Open `src/voice/pipeline.py` and walk through `SDRTurnPolicy._reply()` to show the conversation logic
4. Show the Calls tab with any pre-existing call records

> "The infrastructure has an occasional cold-start — the core innovation is the signal scoring and conversation policy, which you can see directly in the code."
