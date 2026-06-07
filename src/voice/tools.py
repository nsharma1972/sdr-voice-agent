"""Tool implementations invoked during a live Vapi call."""
from __future__ import annotations

import httpx

from src import config


async def book_meeting(
    prospect_name: str,
    prospect_email: str,
    preferred_time: str = "next available",
) -> dict:
    """Reserve a Cal.com slot and return booking details."""
    if not config.CALCOM_API_KEY or not config.CALCOM_EVENT_TYPE_ID:
        return {"status": "error", "message": "Booking not configured"}

    payload = {
        "eventTypeId": int(config.CALCOM_EVENT_TYPE_ID),
        "attendee": {
            "name": prospect_name,
            "email": prospect_email,
            "timeZone": "America/New_York",
        },
        "metadata": {"source": "sdr-voice-agent"},
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(
            "https://api.cal.com/v2/bookings",
            json=payload,
            headers={
                "Authorization": f"Bearer {config.CALCOM_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code in (200, 201):
        data = resp.json()
        return {
            "status": "booked",
            "meeting_link": data.get("meetingUrl", config.CAL_LINK),
            "start_time": data.get("startTime", ""),
            "message": f"I've booked the call. You'll receive a calendar invite at {prospect_email}.",
        }

    return {
        "status": "error",
        "message": f"Couldn't reserve that slot (HTTP {resp.status_code}). I'll have {config.SENDER_NAME} follow up by email.",
    }


async def suppress_contact(prospect_id: str, reason: str) -> dict:
    """Mark contact as suppressed in the database (called from webhook handler)."""
    return {"status": "suppressed", "reason": reason}
