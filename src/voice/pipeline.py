"""Pipecat voice pipeline — LiveKit + Deepgram STT/TTS + Mistral LLM."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import certifi
import httpx
from deepgram import LiveOptions

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.transports.services.livekit import LiveKitParams, LiveKitTransport

from src import config
from src.signals.base import SignalType

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an AI SDR on a live outbound voice call. You already introduced yourself in the opener.

STRICT RULES — follow every one or the call fails:
1. ONE sentence per response. Never more.
2. Maximum 12 words per response.
3. No filler words (well, so, um, actually, certainly, absolutely).
4. No emojis, punctuation beyond a period or question mark.
5. Ask only ONE question per turn.
6. Goal sequence: confirm interest → ask for a 15-min meeting → get their email → close.
7. If they agree to meet: ask "What email should I send the invite to?"
8. If they give an email address: respond ONLY with "Perfect, I will get that sent over."
9. If they decline or say not interested: respond ONLY with "Understood, thanks for your time."
10. Never pitch features, pricing, or competitors.
11. Never repeat yourself.

Signal context: {signal_summary}
You are calling on behalf of: {sender_name}
"""

# ── Signal-specific openers ────────────────────────────────────────────────────

_SIGNAL_OPENERS = {
    SignalType.REGULATORY_FILING.value: "calling about a compliance disclosure at {company}",
    SignalType.REGULATORY_ACTION.value: "calling about a regulatory action affecting {company}",
    SignalType.FUNDING_ROUND.value: "calling about {company}'s recent funding round",
    SignalType.HIRING_SIGNAL.value: "calling about AI hiring activity at {company}",
    SignalType.EXEC_INTERVIEW.value: "calling about a recent interview from {company}'s leadership",
    SignalType.PRESS_RELEASE.value: "calling about a recent announcement from {company}",
}


def build_opening_line(prospect: dict[str, Any], signal: dict[str, Any]) -> str:
    company  = prospect.get("company") or "your company"
    sig_type = signal.get("signal_type", "")
    context  = _SIGNAL_OPENERS.get(sig_type, "calling about recent activity at {company}").format(company=company)
    return (
        "Hi {first_name}, I'm an AI assistant for {sender_name} — {context}. "
        "Do you have 60 seconds?"
    ).format(
        first_name  = prospect.get("first_name", "there"),
        sender_name = config.SENDER_NAME or "our team",
        context     = context,
    )


# ── LLM-backed turn processor ─────────────────────────────────────────────────

class SDRTurnPolicy(FrameProcessor):
    """Calls Mistral (via Ollama) for every user turn. One sentence, max 12 words."""

    def __init__(
        self,
        signal: dict[str, Any],
        opener: str,
        call_id: str | None = None,
    ):
        super().__init__()
        self._call_id  = call_id
        self._outcome  = "needs_review"
        self._responding = False
        self._bot_speaking = False   # true while TTS audio is playing
        self._ignore_until = 0.0
        self._transcript: list[tuple[str, str]] = [("agent", opener)]

        system = _SYSTEM_PROMPT.format(
            signal_summary = signal.get("summary", "AI governance signal"),
            sender_name    = config.SENDER_NAME or "our team",
        )
        self._messages: list[dict] = [
            {"role": "system",    "content": system},
            {"role": "assistant", "content": opener},
        ]

    # ── frame routing ──────────────────────────────────────────────────────────

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            # small cooldown after bot finishes so the mic tail doesn't trigger
            self._ignore_until = asyncio.get_running_loop().time() + 0.4
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text and not self._bot_speaking and not self._responding and self._ready():
                await self._handle_turn(text)
            return
        await self.push_frame(frame, direction)

    def _ready(self) -> bool:
        return asyncio.get_running_loop().time() >= self._ignore_until

    # ── LLM call ──────────────────────────────────────────────────────────────

    async def _handle_turn(self, user_text: str) -> None:
        self._responding  = True
        self._ignore_until = asyncio.get_running_loop().time() + 0.4
        self._transcript.append(("prospect", user_text))

        try:
            # Email detection first — no LLM needed
            reply = self._check_email(user_text)
            if reply is None:
                reply = await self._call_llm(user_text)
                self._detect_outcome(reply)
            self._transcript.append(("agent", reply))
            logger.info("SDR → %s", reply)
            await self.push_frame(TextFrame(reply))
        except Exception as exc:
            logger.warning("turn handler error: %s", exc)
            await self.push_frame(TextFrame("Sorry — could you say that again?"))
        finally:
            self._responding = False

    def _check_email(self, user_text: str) -> str | None:
        """Return a closing line if user gave an email, else None."""
        # Match typed or spoken: "alex at rippling dot com"
        normalised = re.sub(r"\s+at\s+", "@", user_text, flags=re.IGNORECASE)
        normalised = re.sub(r"\s+dot\s+", ".", normalised, flags=re.IGNORECASE)
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", normalised):
            self._outcome = "booked"
            return "Perfect, I will get that invite sent over."
        return None

    async def _call_llm(self, user_text: str) -> str:
        self._messages.append({"role": "user", "content": user_text})
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "http://localhost:4000/v1/chat/completions",
                    headers={"Authorization": "Bearer none"},
                    json={
                        "model":       "mistral-small-local",
                        "messages":    self._messages,
                        "max_tokens":  40,
                        "temperature": 0.3,
                        "stream":      False,
                    },
                )
            resp.raise_for_status()
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown, bullet points, multi-sentence overflow
            reply = re.sub(r"[*_`#]", "", reply)
            reply = reply.split(".")[0].strip() + ("." if not reply.endswith("?") else "")
            reply = reply[:120]  # hard cap
        except Exception as exc:
            logger.warning("LLM error: %s", exc)
            reply = "Could you say that again?"
        self._messages.append({"role": "assistant", "content": reply})
        return reply

    def _detect_outcome(self, reply: str) -> None:
        low = reply.lower()
        if any(p in low for p in ("thanks for your time", "thank you for", "won't take more", "goodbye", "take care")):
            self._outcome = "not_interested"
        elif any(p in low for p in ("invite", "calendar", "email", "schedule", "book")):
            self._outcome = "interested"

    # ── transcript persistence ─────────────────────────────────────────────────

    async def flush_transcript(self) -> None:
        if not self._call_id:
            return
        text = "\n".join(f"{spk.upper()}: {line}" for spk, line in self._transcript) or None
        try:
            from src.db import update_call_review
            await update_call_review(
                self._call_id,
                outcome         = self._outcome,
                booked_meeting  = self._outcome == "booked",
                transcript_text = text,
            )
            logger.info("call %s flushed: outcome=%s", self._call_id, self._outcome)
        except Exception as exc:
            logger.warning("flush failed: %s", exc)


# ── Pipeline entry point ──────────────────────────────────────────────────────

async def run_sdr_pipeline(
    livekit_url: str,
    token: str,
    room_name: str,
    prospect: dict[str, Any],
    signal: dict[str, Any],
    call_id: str | None = None,
) -> None:
    transport = LiveKitTransport(
        livekit_url,
        token,
        room_name,
        LiveKitParams(
            audio_out_enabled    = True,
            audio_in_enabled     = True,
            audio_out_sample_rate = 24000,
            audio_in_sample_rate  = 16000,
            vad_enabled          = True,
            vad_analyzer         = SileroVADAnalyzer(),
            vad_audio_passthrough = True,
        ),
    )

    stt = DeepgramSTTService(
        api_key      = config.DEEPGRAM_API_KEY,
        live_options = LiveOptions(
            model            = "nova-2",
            endpointing      = 200,
            utterance_end_ms = "1000",
            smart_format     = False,
        ),
    )

    tts = DeepgramTTSService(
        api_key = config.DEEPGRAM_API_KEY,
        voice   = "aura-asteria-en",
    )

    opening_line = build_opening_line(prospect, signal)
    sdr_policy   = SDRTurnPolicy(signal, opener=opening_line, call_id=call_id)

    pipeline = Pipeline([
        transport.input(),
        stt,
        sdr_policy,
        tts,
        transport.output(),
    ])

    task          = PipelineTask(pipeline, PipelineParams(allow_interruptions=False))
    opener_fired  = False

    @transport.event_handler("on_first_participant_joined")
    async def on_joined(transport, participant_id):
        nonlocal opener_fired
        if opener_fired:
            return
        opener_fired = True
        await asyncio.sleep(0.5)
        await task.queue_frames([TTSSpeakFrame(opening_line)])

    @transport.event_handler("on_participant_left")
    async def on_left(transport, participant_id, reason):
        await sdr_policy.flush_transcript()
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
