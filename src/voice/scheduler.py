"""APScheduler-based call queue — ticks every 60 seconds, dispatches due calls."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src import config
from src.voice.caller import dispatch_call

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _tick,
        trigger="interval",
        seconds=60,
        id="call-queue-tick",
        max_instances=1,
    )
    _scheduler.start()
    logger.info("Call queue scheduler started (60s tick)")


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)


async def _tick() -> None:
    """Dequeue and dispatch calls that are due and within the call window."""
    now = datetime.now(timezone.utc)
    logger.debug("scheduler tick at %s", now.isoformat())

    # TODO: replace with real DB query
    due_calls: list[dict] = await _fetch_due_calls(now)

    for item in due_calls:
        prospect = item["prospect"]
        signal = item["signal"]

        if not _in_call_window(prospect, now):
            logger.debug(
                "prospect %s outside call window — skipping",
                prospect["id"],
            )
            continue

        vapi_call_id = await dispatch_call(prospect, signal)
        if vapi_call_id:
            await _mark_dialing(item["queue_id"], vapi_call_id)
        else:
            await _mark_failed(item["queue_id"])


def _in_call_window(prospect: dict, now: datetime) -> bool:
    """
    Return True if current time falls within 8am–9pm in the prospect's timezone.
    Defaults to Eastern if timezone not set.
    """
    import zoneinfo

    tz_name = prospect.get("timezone", "America/New_York")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")

    local_now = now.astimezone(tz)
    return config.CALL_WINDOW_START_HOUR <= local_now.hour < config.CALL_WINDOW_END_HOUR


async def _fetch_due_calls(now: datetime) -> list[dict]:
    """Stub — replace with real DB query against call_queue table."""
    return []


async def _mark_dialing(queue_id: str, vapi_call_id: str) -> None:
    """Stub — update call_queue row to status='dialing'."""
    logger.info("queue_id=%s → dialing vapi_call_id=%s", queue_id, vapi_call_id)


async def _mark_failed(queue_id: str) -> None:
    """Stub — update call_queue row to status='failed'."""
    logger.warning("queue_id=%s → failed (dispatch error)", queue_id)
