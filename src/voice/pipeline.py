"""Pipecat voice pipeline — free stack: Daily.co + Deepgram + edge-tts + LiteLLM/Mistral."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.edge_tts import EdgeTTSTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport

from src import config
from src.voice.tools import book_meeting

logger = logging.getLogger(__name__)

SIGNAL_OPENERS = {
    "S1": "I'm following up on the FDA warning letter your company received recently.",
    "S2": "I'm following up on the Form 483 observations from your recent FDA inspection.",
    "S3": "Congratulations on the recent 510(k) clearance. I wanted to reach out because post-market compliance is where teams often get stretched thin right after clearance.",
    "S4": "I'm following up on the NDA or BLA milestone your company recently hit.",
    "S7": "I noticed the AI risk language in your company's most recent 10-K.",
}


def build_system_prompt(prospect: dict[str, Any], signal: dict[str, Any]) -> str:
    signal_type = signal.get("signal_type", "S1")
    opener = SIGNAL_OPENERS.get(signal_type, "I'm following up on a regulatory signal relevant to your company.")
    first_name = prospect.get("first_name", "there")
    sender_name = config.SENDER_NAME or "our team"

    return f"""You are an AI business development assistant. You must identify yourself as an AI within the first 5 seconds — never claim to be human.

Opening (say this first, exactly):
"Hi {first_name}! I'm an AI assistant following up on behalf of {sender_name}. {opener} Do you have 90 seconds?"

If they say yes:
- Explain that {sender_name} works with biotech and pharma quality leaders on the intersection of quality systems and AI readiness
- Reference the specific regulatory context: {signal.get("summary", "the recent regulatory event at your company")}
- Offer a 20-minute discovery call: "Would it be worth a short call with {sender_name} to compare notes on how similar companies are handling this?"
- If yes: use the book_meeting function with their name and email

If they want to opt out:
- Say: "Absolutely, I'll make sure you're removed from our list right away. Thank you for your time."
- End the conversation politely

Rules you must never break:
- State you are an AI in your first message
- Never claim to be human, even if asked directly
- Honor opt-out immediately — no second attempts
- Keep responses under 3 sentences — this is a phone call, not an email
- Never make medical, legal, or financial claims
"""


async def run_sdr_pipeline(
    room_url: str,
    token: str,
    prospect: dict[str, Any],
    signal: dict[str, Any],
) -> None:
    """
    Start a Pipecat pipeline in a Daily.co room.
    Called in a background asyncio task per demo session.
    """
    transport = DailyTransport(
        room_url,
        token,
        "SDR Voice Agent",
        DailyParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        ),
    )

    stt = DeepgramSTTService(api_key=config.DEEPGRAM_API_KEY)

    tts = EdgeTTSTTSService(
        voice="en-US-GuyNeural",   # professional male voice, free, no key
        rate="+5%",
        pitch="-5Hz",
    )

    llm = OpenAILLMService(
        api_key=config.LITELLM_API_KEY or "none",
        base_url=config.LITELLM_BASE_URL,
        model="mistral-small-local",
    )

    system_prompt = build_system_prompt(prospect, signal)
    messages = [{"role": "system", "content": system_prompt}]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # Tool: book_meeting
    async def handle_book_meeting(name: str, email: str, preferred_time: str = "next available"):
        result = await book_meeting(name, email, preferred_time)
        return result["message"]

    llm.register_function("book_meeting", handle_book_meeting)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        transport.capture_participant_transcription(participant["id"])
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
