"""APScheduler-based call queue — ticks every 60 seconds, dispatches due calls."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src import config
from src.db import fetch_due_calls, mark_dialing, mark_queue_status, now_iso
from src.voice.caller import dispatch_call

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if not config.VAPI_API_KEY or not config.VAPI_PHONE_NUMBER_ID:
        logger.info("Call queue scheduler disabled; Vapi is not configured")
        return
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
    now = datetime.now(timezone.utc)
    due = await fetch_due_calls(now.isoformat())
    if not due:
        return

    logger.info("scheduler tick: %d due calls", len(due))

    for item in due:
        prospect = {
            "id":           item["id"],
            "company_name": item["company_name"],
            "first_name":   "",
            "fit_score":    item.get("priority", 50),
            "timezone":     "America/New_York",
        }
        signal = {
            "signal_type": item.get("signal_type", "S1"),
            "summary":     item.get("signal_summary", ""),
        }

        if not _in_call_window(prospect, now):
            logger.debug("company=%s outside call window — skipping", item["company_name"])
            continue

        vapi_call_id = await dispatch_call(prospect, signal)
        if vapi_call_id:
            await mark_dialing(item["id"], vapi_call_id)
        else:
            await mark_queue_status(item["id"], "failed")


def _in_call_window(prospect: dict, now: datetime) -> bool:
    import zoneinfo
    tz_name = prospect.get("timezone", "America/New_York")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")
    local = now.astimezone(tz)
    return config.CALL_WINDOW_START_HOUR <= local.hour < config.CALL_WINDOW_END_HOUR
