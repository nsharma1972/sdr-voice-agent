"""Builds the Vapi assistant payload for a given prospect + signal."""
from __future__ import annotations

from typing import Any

from src import config


SIGNAL_OPENERS = {
    "S1": "I'm calling about the FDA warning letter your company received from the {wl_office} office.",
    "S2": "I'm calling about the Form 483 observations from your recent FDA inspection.",
    "S3": "Congratulations on the recent 510(k) clearance for {product_name}. I'm reaching out because post-market compliance is where teams often get stretched thin right after clearance.",
    "S4": "I'm calling about the NDA or BLA milestone your company recently hit — those timelines tend to compress quality and data-integrity work into a very short window.",
    "S7": "I noticed the AI risk language in your company's most recent 10-K and wanted to follow up.",
}

VOICEMAIL_SCRIPTS = {
    "S1": (
        "Hi {first_name}, this is an AI assistant calling on behalf of {sender_name}. "
        "I'm following up on an email about the {wl_office} FDA warning letter. "
        "We help quality leaders resolve warning letters and AI readiness as one program — "
        "it usually takes less time than teams expect. "
        "I'll send a quick follow-up. Thanks."
    ),
    "S7": (
        "Hi {first_name}, AI assistant calling for {sender_name}. "
        "Quick follow-up on the AI risk disclosure in your 10-K. "
        "We build the governance layer inside the existing QMS — "
        "happy to compare notes on how peers are handling this. "
        "Email follow-up coming. Thanks."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """You are an AI business development assistant calling on behalf of {sender_name} at {sender_company}. You are NOT {sender_name} — you must identify yourself as an AI within the first 5 seconds.

Opening (mandatory, exact wording):
"Hi, is this {first_name}? — Great, I'm an AI assistant calling for {sender_name}. {signal_opener} I have a quick question — do you have 90 seconds?"

If they say yes:
- Explain that {sender_name} works with {icp_description} on the intersection of quality systems and AI readiness
- Reference the specific regulatory signal: {signal_context}
- Offer to book a 20-minute discovery call: "Would it be worth a 20-minute call with {sender_name} to compare notes on how similar companies are handling this?"
- If yes: use the book_meeting tool to find and reserve a slot

If they want to opt out:
- Acknowledge immediately: "Absolutely, I'll remove you from our list right now."
- Call the suppress_contact tool
- End the call politely

Voicemail mode (if voicemail detected):
- Leave the script exactly as provided in the voicemail_script field
- Do not improvise or extend it — 18–25 seconds maximum

Compliance rules (non-negotiable):
- State you are an AI within the first 5 seconds — never claim to be human
- Honor any opt-out immediately — no second attempts in the same call
- Never make medical, legal, or financial claims
- Never discuss competitors by name
"""


def build_assistant_payload(
    prospect: dict[str, Any],
    signal: dict[str, Any],
    model_name: str = "mistral-small-local",
) -> dict[str, Any]:
    signal_type = signal.get("signal_type", "S1")
    opener = SIGNAL_OPENERS.get(signal_type, "I'm following up on a regulatory signal relevant to your company.")
    opener = opener.format(**{**prospect, **signal})

    voicemail_script = VOICEMAIL_SCRIPTS.get(signal_type, (
        "Hi {first_name}, AI assistant for {sender_name}. "
        "Following up on an email about recent regulatory activity at your company. "
        "Will send a note. Thanks."
    )).format(
        first_name=prospect.get("first_name", "there"),
        sender_name=config.SENDER_NAME,
        **signal,
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        sender_name=config.SENDER_NAME,
        sender_company="",
        first_name=prospect.get("first_name", "there"),
        icp_description="biotech and pharmaceutical quality leaders",
        signal_opener=opener,
        signal_context=signal.get("summary", ""),
    )

    return {
        "name": f"sdr-call-{prospect['id']}",
        "model": {
            "provider": "custom-llm",
            "url": config.LITELLM_BASE_URL,
            "model": model_name,
            "systemPrompt": system_prompt,
            "temperature": 0.3,
            "maxTokens": 200,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": config.ELEVENLABS_VOICE_ID,
            "model": "eleven_flash_v2_5",
            "stability": 0.5,
            "similarityBoost": 0.8,
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-3",
            "language": "en-US",
        },
        "firstMessage": (
            f"Hi, is this {prospect.get('first_name', 'there')}? "
            "— I'm an AI assistant calling for a quick follow-up."
        ),
        "voicemailMessage": voicemail_script,
        "endCallFunctionEnabled": True,
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 300,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "book_meeting",
                    "description": "Book a discovery call on the calendar when the prospect agrees to meet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prospect_name": {"type": "string"},
                            "prospect_email": {"type": "string"},
                            "preferred_time": {
                                "type": "string",
                                "description": "ISO 8601 datetime the prospect mentions, or 'next available'",
                            },
                        },
                        "required": ["prospect_name", "prospect_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "suppress_contact",
                    "description": "Immediately suppress this contact from all future outreach when they opt out.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "enum": ["not_interested", "opt_out", "wrong_number", "dnc"],
                            },
                        },
                        "required": ["reason"],
                    },
                },
            },
        ],
        "metadata": {
            "prospect_id": str(prospect["id"]),
            "signal_type": signal_type,
            "call_queue_id": str(prospect.get("call_queue_id", "")),
        },
    }
