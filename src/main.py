"""FastAPI application entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import config
from src.voice.scheduler import start_scheduler, stop_scheduler
from src.voice.webhook import handle_vapi_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SDR Voice Agent",
    description="Signal-triggered outbound voice AI for B2B sales development",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    missing = config.assert_voice_ready()
    if missing:
        logger.warning("Voice not ready — missing env vars: %s", missing)
    else:
        start_scheduler()
        logger.info("SDR Voice Agent started")


@app.on_event("shutdown")
async def shutdown() -> None:
    stop_scheduler()


@app.post("/webhooks/vapi")
async def vapi_webhook(request):
    from fastapi import Header, Request
    from src.voice.webhook import handle_vapi_webhook
    return await handle_vapi_webhook(request)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0) -> dict:
    """Portal: recent calls with outcomes. TODO: query DB."""
    return {"calls": [], "total": 0, "limit": limit, "offset": offset}


@app.post("/calls/enqueue")
async def enqueue_call(prospect_id: str, signal_id: str, priority: int = 50) -> dict:
    """Manually enqueue a call for a given prospect + signal."""
    # TODO: insert into call_queue table
    return {"status": "queued", "prospect_id": prospect_id, "signal_id": signal_id}
