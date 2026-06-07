"""FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config

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

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ── demo UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return HTMLResponse("<h1>SDR Voice Agent</h1><p>static/index.html not found</p>")


# ── demo session API ─────────────────────────────────────────────────────────

class DemoSessionRequest(BaseModel):
    first_name: str = "Alex"
    last_name: str = ""
    company: str = ""
    signal_type: str = "S1"
    signal_summary: str = ""


@app.post("/demo/start")
async def start_demo(req: DemoSessionRequest) -> dict:
    """
    Create a Daily.co room, launch the Pipecat bot, return the room URL.
    The browser joins the same room via Daily.co JS SDK.
    """
    missing = config.assert_voice_ready()
    if missing:
        return {
            "error": f"Missing env vars: {missing}. Check .env and README.",
            "room_url": None,
        }

    from src.voice.demo import start_demo_session

    prospect = {
        "id": "demo",
        "first_name": req.first_name,
        "last_name": req.last_name,
        "company": req.company,
        "fit_score": 75,
    }
    signal = {
        "signal_type": req.signal_type,
        "summary": req.signal_summary or f"Demo signal — type {req.signal_type}",
    }

    session = await start_demo_session(prospect, signal)
    return {"room_url": session["room_url"], "room_name": session["room_name"]}


# ── calls portal ─────────────────────────────────────────────────────────────

@app.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0) -> dict:
    return {"calls": [], "total": 0, "limit": limit, "offset": offset}
