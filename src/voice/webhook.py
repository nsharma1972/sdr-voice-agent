"""Vapi webhook handlers."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import Header, HTTPException, Request

from src import config
from src.db import insert_call, mark_queue_status
from src.voice.assistant import build_assistant_payload
from src.voice.tools import book_meeting, suppress_contact

logger = logging.getLogger(__name__)


def _verify_vapi_hmac(body: bytes, signature: str | None) -> None:
    if not config.VAPI_WEBHOOK_SECRET:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Vapi signature")
    expected = hmac.new(
        config.VAPI_WEBHOOK_SECRET.encode(), body, hashlib.sha256
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

    match msg.get("type"):
        case "assistant-request":   return await _handle_assistant_request(msg)
        case "function-call":       return await _handle_function_call(msg)
        case "end-of-call-report":
            await _handle_end_of_call(msg)
            return {"status": "ok"}
        case "status-update":
            logger.debug("call status: %s", msg.get("call", {}).get("status"))
            return {"status": "ok"}
        case _:
            return {"status": "ok"}


async def _handle_assistant_request(msg: dict) -> dict:
    call = msg.get("call", {})
    meta = call.get("metadata", {})
    prospect_id = meta.get("prospect_id")

    if not prospect_id:
        return {
            "assistant": {
                "name": "sdr-generic",
                "firstMessage": "Hi, I'm an AI assistant following up on a recent signal. Do you have 90 seconds?",
                "model": {
                    "provider": "custom-llm",
                    "url": config.LITELLM_BASE_URL,
                    "model": "mistral-small-local",
                    "systemPrompt": "You are an AI SDR assistant. Identify yourself as an AI immediately.",
                    "temperature": 0.3,
                },
            }
        }

    prospect = {"id": prospect_id, "first_name": meta.get("first_name", "there")}
    signal = {
        "signal_type": meta.get("signal_type", "S1"),
        "summary": meta.get("signal_summary", ""),
    }
    model = _route_model(prospect, signal)
    return {"assistant": build_assistant_payload(prospect, signal, model)}


async def _handle_function_call(msg: dict) -> dict:
    fn = msg.get("functionCall", {})
    name = fn.get("name")
    params = fn.get("parameters", {})
    prospect_id = msg.get("call", {}).get("metadata", {}).get("prospect_id", "")

    match name:
        case "book_meeting":
            result = await book_meeting(
                prospect_name=params.get("prospect_name", ""),
                prospect_email=params.get("prospect_email", ""),
                preferred_time=params.get("preferred_time", "next available"),
            )
            logger.info("book_meeting prospect=%s status=%s", prospect_id, result.get("status"))
            return {"result": result["message"]}
        case "suppress_contact":
            await suppress_contact(prospect_id, params.get("reason", "opt_out"))
            return {"result": "Contact suppressed. Ending call."}
        case _:
            return {"result": "Action not available."}


async def _handle_end_of_call(msg: dict) -> None:
    call = msg.get("call", {})
    analysis = msg.get("analysis", {})
    meta = call.get("metadata", {})

    outcome_map = {
        "booked": "booked", "not_interested": "not_interested",
        "voicemail": "voicemail", "no_answer": "no_answer",
        "callback_requested": "callback_requested",
    }
    raw = analysis.get("successEvaluation", "no_answer")
    outcome = outcome_map.get(raw, "no_answer")

    queue_id = meta.get("call_queue_id")
    company  = meta.get("company_name", "unknown")
    signal_t = meta.get("signal_type", "")

    await insert_call(
        company_name=company,
        signal_type=signal_t,
        outcome=outcome,
        call_queue_id=queue_id or None,
        duration_seconds=call.get("duration"),
        model_used=meta.get("model_used"),
        transcript_text=msg.get("artifact", {}).get("transcript"),
        cost_usd=msg.get("cost"),
        booked_meeting=(outcome == "booked"),
    )

    if queue_id:
        await mark_queue_status(queue_id, "completed")

    logger.info(
        "call ended company=%s outcome=%s duration=%.1fs cost=$%.4f",
        company, outcome, call.get("duration", 0), msg.get("cost", 0),
    )


def _route_model(prospect: dict, signal: dict) -> str:
    high_value = {"S1", "S2", "S4"}
    if prospect.get("fit_score", 0) >= 80 and signal.get("signal_type") in high_value:
        return "gpt-4o-mini"
    return "mistral-small-local"
