"""Demo session management — creates Daily.co rooms and launches Pipecat bots."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from src import config

logger = logging.getLogger(__name__)

DAILY_BASE = "https://api.daily.co/v1"

_active_sessions: dict[str, asyncio.Task] = {}


async def create_room(ttl_seconds: int = 600) -> dict[str, str]:
    """
    Create a Daily.co room valid for ttl_seconds.
    Returns {"room_url": ..., "room_name": ...}.
    Raises RuntimeError if DAILY_API_KEY is not set.
    """
    if not config.DAILY_API_KEY:
        raise RuntimeError("DAILY_API_KEY not configured")

    exp = int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp())
    payload = {
        "properties": {
            "exp": exp,
            "max_participants": 2,
            "enable_screenshare": False,
            "enable_recording": "local",
        }
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{DAILY_BASE}/rooms",
            json=payload,
            headers={"Authorization": f"Bearer {config.DAILY_API_KEY}"},
        )

    resp.raise_for_status()
    data = resp.json()
    return {"room_url": data["url"], "room_name": data["name"]}


async def create_bot_token(room_name: str) -> str:
    """Create a meeting token for the bot participant (is_owner=True)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{DAILY_BASE}/meeting-tokens",
            json={"properties": {"room_name": room_name, "is_owner": True}},
            headers={"Authorization": f"Bearer {config.DAILY_API_KEY}"},
        )
    resp.raise_for_status()
    return resp.json()["token"]


async def start_demo_session(
    prospect: dict[str, Any],
    signal: dict[str, Any],
) -> dict[str, str]:
    """
    Create a room, launch the Pipecat bot in a background task, return the room URL.
    The caller (browser user) joins the same room via Daily.co JS SDK.
    """
    from src.voice.pipeline import run_sdr_pipeline

    room = await create_room()
    bot_token = await create_bot_token(room["room_name"])

    task = asyncio.create_task(
        run_sdr_pipeline(room["room_url"], bot_token, prospect, signal),
        name=f"bot-{room['room_name']}",
    )

    _active_sessions[room["room_name"]] = task
    task.add_done_callback(lambda t: _active_sessions.pop(room["room_name"], None))

    logger.info("demo session started room=%s", room["room_name"])
    return {"room_url": room["room_url"], "room_name": room["room_name"]}
