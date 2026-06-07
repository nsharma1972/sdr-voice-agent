"""Pipecat voice pipeline — LiveKit + Deepgram demo SDR policy."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import certifi
from deepgram import LiveOptions

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import InterimTranscriptionFrame, TextFrame, TranscriptionFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.transports.services.livekit import LiveKitParams, LiveKitTransport

from src import config
from src.signals.base import SignalType

logger = logging.getLogger(__name__)


class ConversationProbe(FrameProcessor):
    """Log transcript/LLM text frames while passing all frames through unchanged."""

    def __init__(self, label: str):
        super().__init__()
        self._label = label

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            logger.info("%s transcript: %s", self._label, frame.text)
        elif isinstance(frame, TextFrame):
            logger.info("%s text: %s", self._label, frame.text)
        await self.push_frame(frame, direction)


class SDRTurnPolicy(FrameProcessor):
    """Deterministic SDR turn policy for the browser demo."""

    def __init__(self, signal: dict[str, Any], call_id: str | None = None):
        super().__init__()
        self._signal = signal
        self._call_id = call_id
        self._turn = 0
        self._pending_interim_text = ""
        self._pending_interim_task: asyncio.Task | None = None
        self._ignore_until = 0.0
        self._transcript: list[tuple[str, str]] = []  # (speaker, text)

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            self._cancel_pending_interim()
            if text and self._accept_user_text():
                self._transcript.append(("prospect", text))
                await self._send_reply(text)
            return
        if isinstance(frame, InterimTranscriptionFrame):
            text = frame.text.strip()
            if text and self._accept_user_text() and self._stable_interim_candidate(text):
                self._pending_interim_text = text
                self._cancel_pending_interim()
                self._pending_interim_task = asyncio.create_task(self._reply_after_interim_pause(text))
            return
        await self.push_frame(frame, direction)

    def _cancel_pending_interim(self) -> None:
        if self._pending_interim_task and not self._pending_interim_task.done():
            self._pending_interim_task.cancel()
        self._pending_interim_task = None

    async def _reply_after_interim_pause(self, text: str) -> None:
        try:
            await asyncio.sleep(0.6)
            if text == self._pending_interim_text:
                self._pending_interim_text = ""
                self._transcript.append(("prospect", text))
                await self._send_reply(text)
        except asyncio.CancelledError:
            pass

    async def _send_reply(self, user_text: str) -> None:
        reply = self._reply(user_text)
        # Scale ignore window to approximate TTS duration: ~0.08s/word + 0.8s buffer
        word_count = len(reply.split())
        self._ignore_until = asyncio.get_running_loop().time() + (word_count * 0.08) + 0.8
        self._transcript.append(("agent", reply))
        logger.info("sdr reply: %s", reply)
        await self.push_frame(TextFrame(reply))

    async def flush_transcript(self) -> None:
        """Persist collected transcript to the calls DB record."""
        if not self._call_id or not self._transcript:
            return
        text = "\n".join(f"{spk.upper()}: {line}" for spk, line in self._transcript)
        try:
            from src.db import update_call_review
            await update_call_review(self._call_id, notes=text)
        except Exception as exc:
            logger.warning("transcript flush failed: %s", exc)

    def _accept_user_text(self) -> bool:
        return asyncio.get_running_loop().time() >= self._ignore_until

    def _stable_interim_candidate(self, text: str) -> bool:
        normalized = text.lower().strip(" .,!?:;")
        if normalized in {"now", "um", "uh", "so", "well", "yeah", "yes", "no", "okay", "ok"}:
            return False
        if self._is_positive(normalized):
            return True
        return len(normalized.split()) >= 3

    def _reply(self, user_text: str) -> str:
        text = user_text.lower()
        sender_name = config.SENDER_NAME or "our team"

        if any(phrase in text for phrase in ("who are you", "what is this", "why are you calling")):
            return (
                f"I'm an AI assistant calling for {sender_name}, about a company signal "
                "that may affect AI governance and data controls."
            )

        if any(phrase in text for phrase in ("what do you do", "what is your company", "tell me more")):
            return (
                "We help teams compare how similar companies are handling AI governance and data controls, "
                f"would a short call with {sender_name} be useful?"
            )

        if any(phrase in text for phrase in ("send me", "email me", "send info", "send information")):
            self._turn = 2
            return "Of course — what email should I send it to?"

        if any(phrase in text for phrase in ("not the right person", "not my area", "someone else")):
            return "Got it — who is the right person for AI governance or data controls?"

        if any(phrase in text for phrase in ("already handled", "we have it covered", "not a priority")):
            return (
                "That makes sense. Is it fully handled internally, "
                "or would it be useful to compare notes with similar teams?"
            )

        if any(phrase in text for phrase in ("how much", "price", "pricing", "cost")):
            return "Pricing really depends on scope — the useful first step is a short fit call, would that work?"

        if any(phrase in text for phrase in ("remove me", "not interested", "no thanks", "stop calling")):
            self._turn = 99
            return "Understood, I won't take more of your time — thanks for speaking with me."

        if any(word in text for word in ("busy", "bad time", "call me later", "not now")):
            return "No problem at all — what would be a better time for a quick follow-up?"

        if "are you there" in text or "can you hear" in text:
            return "Yes, I can hear you — I was just calling to ask one quick question about AI governance. Do you have a moment?"

        email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", user_text)
        if email:
            self._turn = 99
            return "Perfect, I'll get that invite sent over — is there anything specific you would want covered on the call?"

        positive = self._is_positive(text)

        if self._turn == 0:
            self._turn = 1
            # Strong booking intent at turn 0 (user said "let's do it" to opener) → skip to email
            if self._is_booking_intent(text):
                self._turn = 3
                return f"Love that energy. What email should I use for the calendar invite with {sender_name}?"
            if positive:
                return (
                    f"Great, the quick reason I called is AI governance and data controls — "
                    "is that active for your team right now?"
                )
            return (
                "No worries, I will be quick. We work with teams on AI governance and data controls — "
                "is that on your radar?"
            )

        if self._turn == 1:
            self._turn = 2
            if positive or self._is_booking_intent(text):
                return f"Good to hear. What email should I use for a calendar invite with {sender_name}?"
            return "Understood — who on your team owns AI governance or data quality?"

        if self._turn == 2:
            self._turn = 3
            if positive or self._is_booking_intent(text):
                return f"Perfect, what email should I send the invite to?"
            return "Got it, I will note that and close out here — thanks for a few minutes."

        return "Thanks for that. Should I send a short note, or go ahead and send the calendar invite?"

    def _is_booking_intent(self, text: str) -> bool:
        """Strong booking signal — user explicitly wants to schedule, not just agreeing."""
        normalized = re.sub(r"[^a-z0-9\s']", " ", text.lower()).strip()
        booking_phrases = (
            "let's do it", "lets do it", "book it", "schedule it", "set it up",
            "set up a call", "have a call", "want to have a call", "i want a call",
            "i'd like a call", "i would like a call", "send invite", "send the invite",
            "calendar invite", "send me a calendar", "go ahead and book",
        )
        return any(re.search(rf"\b{re.escape(p)}\b", normalized) for p in booking_phrases)

    def _is_positive(self, text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9\s']", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        positive_phrases = (
            "yes",
            "yeah",
            "yep",
            "sure",
            "okay",
            "ok",
            "i do",
            "go ahead",
            "sounds good",
            "that works",
            "works for me",
            "let's do it",
            "lets do it",
            "book it",
            "schedule it",
            "set it up",
            "set up a call",
            "have a call",
            "want to have a call",
            "i want a call",
            "i'd like a call",
            "i would like a call",
            "send invite",
            "send the invite",
            "calendar invite",
            "i confirm",
            "confirmed",
            "i agree",
            "agreed",
            "perfect",
        )
        return any(re.search(rf"\b{re.escape(phrase)}\b", normalized) for phrase in positive_phrases)

# ── Signal-specific openers — industry-agnostic ──────────────────────────────
# Each opener references the concrete event so the prospect knows it's not a
# generic cold call. Parameterized with {summary} from the signal record.

SIGNAL_OPENERS: dict[str, str] = {
    SignalType.REGULATORY_ACTION.value: (
        "I'm following up because your company recently went through a regulatory action. "
        "That typically creates a compressed window to show remediation — "
        "and that's exactly the kind of situation we work through with leadership teams."
    ),
    SignalType.REGULATORY_FILING.value: (
        "I noticed your company recently disclosed AI or data governance risk in a public filing. "
        "Once that appears on record, the board and auditors tend to ask for a remediation plan "
        "on a shorter timeline than most teams expect."
    ),
    SignalType.PRODUCT_CLEARANCE.value: (
        "Congratulations on the recent clearance. Post-launch is usually when compliance "
        "and data requirements spike faster than the team anticipated — "
        "we help companies get ahead of that curve."
    ),
    SignalType.FUNDING_ROUND.value: (
        "Congratulations on the recent funding round. "
        "That kind of growth usually means your processes need to scale just as fast as headcount — "
        "especially on the data and compliance side."
    ),
    SignalType.HIRING_SIGNAL.value: (
        "I noticed your company is actively hiring for AI or data roles. "
        "That usually signals a build-out that comes with real governance questions "
        "that the hiring plan alone doesn't answer."
    ),
    SignalType.EXEC_INTERVIEW.value: (
        "I came across a recent interview where your leadership discussed AI and data strategy. "
        "I wanted to follow up because we work specifically at that intersection — "
        "bridging the gap between the strategy and the operational reality."
    ),
    SignalType.PRESS_RELEASE.value: (
        "I saw the recent announcement from your company "
        "and thought there might be an angle worth a quick conversation."
    ),
    SignalType.OTHER.value: (
        "I'm following up on some recent activity at your company that caught our attention."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """\
You are on a live outbound SDR voice call.

Sound like a concise sales development rep, not a narrator, teacher, tutorial, chatbot, or demo guide.
Never mention prompts, rules, bullet points, implementation, tools, transcripts, or what you are about to do.

Required behavior:
- Identify as an AI assistant in the first sentence.
- Keep every response to one or two short spoken sentences.
- Ask one question at a time.
- After asking a question, stop speaking and wait for the prospect's response.
- Do not fill silence, narrate waiting, or continue pitching without a new prospect response.
- If the prospect is busy, ask for a better time.
- If the prospect says no or asks to be removed, politely acknowledge and end the call.
- Never make legal, financial, medical, or regulatory claims.
- Never name competitors.

Offer only this meeting ask when there is interest:
"Would a short call with {sender_name} be worth it, just to compare notes on how similar companies are handling this?"
"""


def build_system_prompt(prospect: dict[str, Any], signal: dict[str, Any]) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        sender_name=config.SENDER_NAME or "our team",
    )


def build_opening_line(prospect: dict[str, Any], signal: dict[str, Any]) -> str:
    company = prospect.get("company") or "your company"
    context = f"I noticed recent activity at {company}"

    return (
        "Hi {first_name}, I'm an AI assistant calling for {sender_name}. "
        "{context} around AI governance. Do you have 90 seconds?"
    ).format(
        first_name=prospect.get("first_name", "there"),
        sender_name=config.SENDER_NAME or "our team",
        context=context,
    )


async def run_sdr_pipeline(
    livekit_url: str,
    token: str,
    room_name: str,
    prospect: dict[str, Any],
    signal: dict[str, Any],
    call_id: str | None = None,
) -> None:
    """Start a Pipecat pipeline in a LiveKit room."""
    transport = LiveKitTransport(
        livekit_url,
        token,
        room_name,
        LiveKitParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            audio_out_sample_rate=24000,
            audio_in_sample_rate=16000,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        ),
    )

    stt = DeepgramSTTService(
        api_key=config.DEEPGRAM_API_KEY,
        live_options=LiveOptions(
            endpointing=300,
            utterance_end_ms="1000",
            no_delay=True,
        ),
    )

    tts = DeepgramTTSService(api_key=config.DEEPGRAM_API_KEY, voice="aura-asteria-en")

    sdr_policy = SDRTurnPolicy(signal, call_id=call_id)

    pipeline = Pipeline([
        transport.input(),
        stt,
        ConversationProbe("stt"),
        sdr_policy,
        ConversationProbe("sdr"),
        tts,
        transport.output(),
    ])

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=False))
    opener_started = False

    @transport.event_handler("on_first_participant_joined")
    async def on_joined(transport, participant_id):
        nonlocal opener_started
        if opener_started:
            return
        opener_started = True
        await asyncio.sleep(0.5)
        opening_line = build_opening_line(prospect, signal)
        await task.queue_frames([TTSSpeakFrame(opening_line)])

    @transport.event_handler("on_participant_left")
    async def on_left(transport, participant_id, reason):
        await sdr_policy.flush_transcript()
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
