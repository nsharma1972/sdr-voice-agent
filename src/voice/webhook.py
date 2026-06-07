"""Vapi webhook handlers."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import Header, HTTPException, Request

from src import config
from src.voice.assistant import build_assistant_payload
from src.voice.tools import book_meeting, suppress_contact

logger = logging.getLogger(__name__)


def _verify_vapi_hmac(body: bytes, signature: str | None) -> None:
    if not config.VAPI_WEBHOOK_SECRET:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Vapi signature")
    expected = hmac.new(
        config.VAPI_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Vapi signature")


async def handle_vapi_webhook(
    request: Request,
    x_vapi_signature: str | None = Header(None),
) -> dict[str, Any]:
    body = await request.body()
    _verify_vapi_hmac(body, x_vapi_signature)

    payload = await request.json()
    msg = payload.get("message", {})
    msg_type = msg.get("type")

    match msg_type:
        case "assistant-request":
            return await _handle_assistant_request(msg)
        case "function-call":
            return await _handle_function_call(msg)
        case "end-of-call-report":
            await _handle_end_of_call(msg)
            return {"status": "ok"}
        case "status-update":
            _handle_status_update(msg)
            return {"status": "ok"}
        case _:
            logger.debug("Unhandled Vapi message type: %s", msg_type)
            return {"status": "ok"}


async def _handle_assistant_request(msg: dict) -> dict:
    """Return per-call assistant config at call-start time."""
    call = msg.get("call", {})
    metadata = call.get("metadata", {})
    prospect_id = metadata.get("prospect_id")

    # In a real deployment, fetch prospect + signal from DB here.
    # For hackathon: return a generic assistant if no metadata.
    if not prospect_id:
        return {
            "assistant": {
                "name": "sdr-generic",
                "firstMessage": "Hi, I'm an AI assistant following up on a recent email. Do you have 90 seconds?",
                "model": {
                    "provider": "custom-llm",
                    "url": config.LITELLM_BASE_URL,
                    "model": "mistral-small-local",
                    "systemPrompt": "You are an AI SDR assistant. Identify yourself as an AI immediately.",
                    "temperature": 0.3,
                },
            }
        }

    prospect = {"id": prospect_id, "first_name": metadata.get("first_name", "there")}
    signal = {
        "signal_type": metadata.get("signal_type", "S1"),
        "summary": metadata.get("signal_summary", ""),
        "wl_office": metadata.get("wl_office", "FDA"),
    }

    model = _route_model(prospect, signal)
    assistant = build_assistant_payload(prospect, signal, model)
    return {"assistant": assistant}


async def _handle_function_call(msg: dict) -> dict:
    """Execute a tool call requested by the LLM during the conversation."""
    fn = msg.get("functionCall", {})
    name = fn.get("name")
    params = fn.get("parameters", {})
    call_meta = msg.get("call", {}).get("metadata", {})
    prospect_id = call_meta.get("prospect_id", "")

    match name:
        case "book_meeting":
            result = await book_meeting(
                prospect_name=params.get("prospect_name", ""),
                prospect_email=params.get("prospect_email", ""),
                preferred_time=params.get("preferred_time", "next available"),
            )
            logger.info("book_meeting prospect=%s result=%s", prospect_id, result.get("status"))
            return {"result": result["message"]}

        case "suppress_contact":
            result = await suppress_contact(prospect_id, params.get("reason", "opt_out"))
            logger.info("suppress_contact prospect=%s reason=%s", prospect_id, params.get("reason"))
            return {"result": "Contact suppressed. Call ending."}

        case _:
            logger.warning("Unknown tool call: %s", name)
            return {"result": "Action not available."}


async def _handle_end_of_call(msg: dict) -> None:
    """Persist call outcome to database."""
    call = msg.get("call", {})
    analysis = msg.get("analysis", {})
    artifact = msg.get("artifact", {})

    outcome_map = {
        "booked": "booked",
        "not_interested": "not_interested",
        "voicemail": "voicemail",
        "no_answer": "no_answer",
        "callback_requested": "callback_requested",
    }
    raw_outcome = analysis.get("successEvaluation", "no_answer")
    outcome = outcome_map.get(raw_outcome, "no_answer")

    logger.info(
        "call ended vapi_call_id=%s outcome=%s duration=%.1fs cost=$%.4f",
        call.get("id"),
        outcome,
        call.get("duration", 0),
        msg.get("cost", 0),
    )
    # TODO: persist to calls table via DB session


def _handle_status_update(msg: dict) -> None:
    status = msg.get("call", {}).get("status")
    logger.debug("call status update: %s", status)


def _route_model(prospect: dict, signal: dict) -> str:
    """Route to cloud model for high-value prospects, local otherwise."""
    fit_score = prospect.get("fit_score", 0)
    high_value_signals = {"S1", "S2", "S4"}
    if fit_score >= 80 and signal.get("signal_type") in high_value_signals:
        return "gpt-4o-mini"
    return "mistral-small-local"
