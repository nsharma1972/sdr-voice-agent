"""Pipecat voice pipeline — LiveKit + Deepgram + LiteLLM/Mistral."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.livekit import LiveKitParams, LiveKitTransport

from src import config
from src.signals.base import SignalType
from src.voice.tools import book_meeting

logger = logging.getLogger(__name__)

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

    llm = OpenAILLMService(
        api_key=config.LITELLM_API_KEY or "none",
        base_url=config.LITELLM_BASE_URL,
        model=config.LLM_MODEL,
    )

    system_prompt = build_system_prompt(prospect, signal)
    context = OpenAILLMContext([{"role": "system", "content": system_prompt}])
    context_aggregator = llm.create_context_aggregator(context)

    async def handle_book_meeting(name: str, email: str, preferred_time: str = "next available"):
        result = await book_meeting(name, email, preferred_time)
        return result["message"]

    llm.register_function("book_meeting", handle_book_meeting)

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_first_participant_joined")
    async def on_joined(transport, participant_id):
        opening_line = build_opening_line(prospect, signal)
        context.add_message(
            {
                "role": "assistant",
                "content": opening_line,
            }
        )
        await task.queue_frames([TTSSpeakFrame(opening_line)])

    @transport.event_handler("on_participant_left")
    async def on_left(transport, participant_id, reason):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
