"""Pipecat voice pipeline — LiveKit + Deepgram demo SDR policy."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import certifi

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

    def __init__(self, signal: dict[str, Any]):
        super().__init__()
        self._signal = signal
        self._turn = 0

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                reply = self._reply(text)
                logger.info("sdr reply: %s", reply)
                await self.push_frame(TextFrame(reply))
            return
        if isinstance(frame, InterimTranscriptionFrame):
            return
        await self.push_frame(frame, direction)

    def _reply(self, user_text: str) -> str:
        text = user_text.lower()
        sender_name = config.SENDER_NAME or "our team"

        if any(word in text for word in ("remove me", "not interested", "no thanks", "stop calling")):
            self._turn = 99
            return "Understood. I won't take more time. Thanks for speaking with me."

        if any(word in text for word in ("busy", "bad time", "call me later", "not now")):
            return "No problem. What is a better time for a quick follow-up?"

        if "are you there" in text or "can you hear" in text:
            return "Yes, I'm here and I can hear you. I was calling to ask one quick question about your AI governance work."

        email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", user_text)
        if email:
            self._turn = 99
            return "Thanks. I'll note that for the follow-up invite. Anything specific you would want covered?"

        positive = any(word in text for word in ("yes", "yeah", "yep", "sure", "okay", "ok", "i do", "go ahead"))

        if self._turn == 0:
            self._turn = 1
            if positive:
                return (
                    "Thanks. The quick reason I called is that this kind of company activity often creates pressure "
                    "around AI governance and data controls. Is that something your team is actively working on?"
                )
            return (
                "Got it. The quick question is whether AI governance or data controls are becoming active priorities "
                "for your team right now."
            )

        if self._turn == 1:
            self._turn = 2
            if positive:
                return (
                    f"That makes sense. Would a short call with {sender_name} be worth it, "
                    "just to compare notes on how similar companies are handling this?"
                )
            return "Understood. Is there someone else on your team who owns AI governance or data controls?"

        if self._turn == 2:
            self._turn = 3
            if positive:
                return "Great. What email should the calendar invite go to?"
            return "No problem. I can mark this as not a fit for now. Thanks for the time."

        return "Thanks. I have that noted. Is there anything else I should include for the follow-up?"

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
    signal_type = signal.get("signal_type", SignalType.OTHER.value)
    opener = SIGNAL_OPENERS.get(signal_type, SIGNAL_OPENERS[SignalType.OTHER.value])

    summary = signal.get("summary", "")
    if summary and len(summary) > 20:
        opener = f"{opener} Specifically, {summary[:120].rstrip('.')}."

    return (
        "Hi {first_name}, I'm an AI assistant following up on behalf of {sender_name}. "
        "{opener} Do you have 90 seconds?"
    ).format(
        first_name=prospect.get("first_name", "there"),
        sender_name=config.SENDER_NAME or "our team",
        opener=opener,
    )


async def run_sdr_pipeline(
    livekit_url: str,
    token: str,
    room_name: str,
    prospect: dict[str, Any],
    signal: dict[str, Any],
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

    stt = DeepgramSTTService(api_key=config.DEEPGRAM_API_KEY)

    tts = DeepgramTTSService(api_key=config.DEEPGRAM_API_KEY, voice="aura-helios-en")

    pipeline = Pipeline([
        transport.input(),
        stt,
        ConversationProbe("stt"),
        SDRTurnPolicy(signal),
        ConversationProbe("sdr"),
        tts,
        transport.output(),
    ])

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))
    opener_started = False

    @transport.event_handler("on_first_participant_joined")
    async def on_joined(transport, participant_id):
        nonlocal opener_started
        if opener_started:
            return
        opener_started = True
        await asyncio.sleep(1.0)
        opening_line = build_opening_line(prospect, signal)
        await task.queue_frames([TTSSpeakFrame(opening_line)])

    @transport.event_handler("on_participant_left")
    async def on_left(transport, participant_id, reason):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
