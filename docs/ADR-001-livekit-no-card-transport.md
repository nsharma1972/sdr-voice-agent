# ADR-001: Use LiveKit for the No-Card Browser Voice Demo

**Date:** 2026-06-07
**Status:** Accepted

## Context

The first browser demo implementation used Daily as the WebRTC transport for Pipecat. Daily room creation worked with the free account, but the Pipecat bot could not join the room. Daily returned:

```text
account-missing-payment-method
```

The project goal is an open-source-friendly demo path that does not require committing secrets and does not require adding a credit card just to validate the local browser voice agent.

## Decision

Use LiveKit Cloud for the browser WebRTC demo path.

Required local-only environment variables:

```bash
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```

These values must stay in `.env` and must not be committed. `.env.example` should show placeholder names only.

## Consequences

- Daily is no longer the preferred transport for the demo path.
- Daily may remain useful as a future paid/hosted transport option.
- The browser demo should migrate from Daily JS SDK to LiveKit client SDK.
- The server-side voice pipeline should migrate from `DailyTransport` to `LiveKitTransport`.
- Deepgram STT/TTS, LiteLLM, and local Ollama/Mistral remain part of the stack.
- Vapi remains Phase 2 for real outbound phone calls and should not block the browser demo.

## Alternatives Considered

- Add a Daily payment method: rejected for the current demo because the user explicitly wants a no-card path.
- Pipecat SmallWebRTC: attractive long-term local option, but requires a larger client/server migration.
- Twilio trial: no-card possible, but it changes the demo from browser WebRTC to telephony and has trial restrictions.
