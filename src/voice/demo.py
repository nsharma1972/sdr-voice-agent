"""Demo session management using LiveKit rooms and Pipecat bots."""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import timedelta
from typing import Any

from livekit import api

from src import config

logger = logging.getLogger(__name__)

_active_sessions: dict[str, asyncio.Task] = {}


def _create_token(
    *,
    room_name: str,
    identity: str,
    name: str,
    ttl_seconds: int = 600,
) -> str:
    return (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_ttl(timedelta(seconds=ttl_seconds))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )


async def start_demo_session(
    prospect: dict[str, Any],
    signal: dict[str, Any],
) -> dict[str, str]:
    """
    Create LiveKit join credentials, launch the Pipecat bot, and return browser
    join credentials to the caller.
    """
    from src.voice.pipeline import run_sdr_pipeline

    if not config.LIVEKIT_URL or not config.LIVEKIT_API_KEY or not config.LIVEKIT_API_SECRET:
        raise RuntimeError("LiveKit is not configured")

    room_name = f"sdr-demo-{secrets.token_urlsafe(8)}"
    browser_token = _create_token(
        room_name=room_name,
        identity=f"prospect-{secrets.token_urlsafe(6)}",
        name=prospect.get("first_name") or "Prospect",
    )
    bot_token = _create_token(
        room_name=room_name,
        identity=f"sdr-agent-{secrets.token_urlsafe(6)}",
        name="SDR Voice Agent",
    )

    task = asyncio.create_task(
        run_sdr_pipeline(config.LIVEKIT_URL, bot_token, room_name, prospect, signal),
        name=f"bot-{room_name}",
    )
    _active_sessions[room_name] = task
    task.add_done_callback(lambda t: _active_sessions.pop(room_name, None))

    logger.info("demo session started room=%s", room_name)
    return {
        "livekit_url": config.LIVEKIT_URL,
        "token": browser_token,
        "room_name": room_name,
    }
