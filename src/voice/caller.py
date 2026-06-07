"""Outbound call dispatcher — places calls via Vapi REST API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src import config

logger = logging.getLogger(__name__)

VAPI_BASE = "https://api.vapi.ai"


async def dispatch_call(
    prospect: dict[str, Any],
    signal: dict[str, Any],
) -> str | None:
    """
    Place an outbound call via Vapi.
    Returns the Vapi call ID on success, None on failure.

    The assistant is NOT embedded here — Vapi will fire the assistant-request
    webhook so we can return per-call config at call-start time.
    """
    if not config.VAPI_API_KEY or not config.VAPI_PHONE_NUMBER_ID:
        logger.error("VAPI_API_KEY or VAPI_PHONE_NUMBER_ID not configured")
        return None

    phone = prospect.get("phone_landline") or prospect.get("phone")
    if not phone:
        logger.warning("No phone number for prospect %s", prospect["id"])
        return None

    payload = {
        "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": phone,
            "name": f"{prospect.get('first_name', '')} {prospect.get('last_name', '')}".strip(),
        },
        "assistantOverrides": {
            "metadata": {
                "prospect_id": str(prospect["id"]),
                "first_name": prospect.get("first_name", ""),
                "signal_type": signal.get("signal_type", "S1"),
                "signal_summary": signal.get("summary", ""),
                "wl_office": signal.get("wl_office", ""),
                "fit_score": prospect.get("fit_score", 0),
            }
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{VAPI_BASE}/call/phone",
            json=payload,
            headers={
                "Authorization": f"Bearer {config.VAPI_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        vapi_call_id = data.get("id")
        logger.info(
            "call dispatched prospect=%s vapi_call_id=%s",
            prospect["id"],
            vapi_call_id,
        )
        return vapi_call_id

    logger.error(
        "Vapi call dispatch failed prospect=%s status=%s body=%s",
        prospect["id"],
        resp.status_code,
        resp.text[:200],
    )
    return None
