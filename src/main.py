"""FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config
from src.db import count_calls, enqueue_call, init_db, list_calls

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="SDR Voice Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_pipeline_cache: dict = {}


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    missing = config.assert_voice_ready()
    if missing:
        logger.warning("Voice not ready — missing: %s", missing)
    else:
        from src.voice.scheduler import start_scheduler
        start_scheduler()
    logger.info("SDR Voice Agent started")


@app.on_event("shutdown")
async def shutdown() -> None:
    from src.voice.scheduler import stop_scheduler
    stop_scheduler()


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ── portal UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return HTMLResponse("<h1>SDR Voice Agent</h1><p>static/index.html not found</p>")


# ── demo session ──────────────────────────────────────────────────────────────

class DemoSessionRequest(BaseModel):
    first_name:     str = "Alex"
    last_name:      str = ""
    company:        str = ""
    signal_type:    str = "S1"
    signal_summary: str = ""


@app.post("/demo/start")
async def start_demo(req: DemoSessionRequest) -> dict:
    missing = config.assert_voice_ready()
    if missing:
        return {"error": f"Missing env vars: {missing}. Check .env.", "room_url": None}

    from src.voice.demo import start_demo_session
    prospect = {"id": "demo", "first_name": req.first_name, "company": req.company, "fit_score": 75}
    signal   = {"signal_type": req.signal_type,
                 "summary": req.signal_summary or f"Demo — signal type {req.signal_type}"}
    session = await start_demo_session(prospect, signal)
    return {"room_url": session["room_url"], "room_name": session["room_name"]}


# ── signal ingestion + lead qualification ─────────────────────────────────────

@app.post("/signals/refresh")
async def refresh_signals(days: int = 180) -> dict:
    """Ingest all signal sources, score leads, auto-enqueue CONTACTs. Takes 15–30s."""
    from src.qualify.pipeline import run_pipeline
    from src.qualify.scorer import Tier

    result = await run_pipeline(days=days, min_tier=Tier.ARCHIVE)  # cache all tiers
    _pipeline_cache.clear()
    _pipeline_cache.update({**result, "leads": [l.to_dict() for l in result["leads"]]})
    return {
        "status":        "ok",
        "contact_count": result["contact_count"],
        "nurture_count": result["nurture_count"],
        "total_leads":   result["total_leads"],
        "enqueued":      result.get("enqueued", 0),
        "signal_counts": result["signal_counts"],
        "run_at":        result["run_at"],
        "errors":        result["errors"],
    }


@app.get("/leads")
async def list_leads(tier: str = "ALL", limit: int = 100, offset: int = 0) -> dict:
    all_leads = _pipeline_cache.get("leads", [])
    if tier.upper() != "ALL":
        all_leads = [l for l in all_leads if l["tier"] == tier.upper()]
    return {
        "leads":  all_leads[offset: offset + limit],
        "total":  len(all_leads),
        "tier":   tier,
        "run_at": _pipeline_cache.get("run_at"),
    }


@app.get("/leads/{company_name}")
async def get_lead(company_name: str) -> dict:
    all_leads = _pipeline_cache.get("leads", [])
    match = next((l for l in all_leads if l["company_name"].lower() == company_name.lower()), None)
    if not match:
        raise HTTPException(404, "Lead not found — run POST /signals/refresh first.")
    return match


@app.post("/leads/{company_name}/enqueue")
async def manual_enqueue(company_name: str) -> dict:
    """Manually push a specific lead into the call queue."""
    all_leads = _pipeline_cache.get("leads", [])
    lead = next((l for l in all_leads if l["company_name"].lower() == company_name.lower()), None)
    if not lead:
        raise HTTPException(404, "Lead not found — run POST /signals/refresh first.")

    from datetime import datetime, timezone
    qid = await enqueue_call(
        company_name=lead["company_name"],
        signal_type=lead.get("primary_signal", "S9"),
        signal_summary=lead.get("summary", ""),
        source_url=lead.get("source_url", ""),
        scheduled_for=datetime.now(timezone.utc).isoformat(),
        priority=80 if lead["score"] >= 75 else 50,
    )
    if not qid:
        return {"status": "already_queued", "company": company_name}
    return {"status": "queued", "queue_id": qid, "company": company_name}


# ── calls ────────────────────────────────────────────────────────────────────

@app.get("/calls")
async def get_calls(limit: int = 50, offset: int = 0) -> dict:
    calls = await list_calls(limit=limit, offset=offset)
    total = await count_calls()
    return {"calls": calls, "total": total, "limit": limit, "offset": offset}


@app.post("/webhooks/vapi")
async def vapi_webhook(request) -> dict:
    from src.voice.webhook import handle_vapi_webhook
    return await handle_vapi_webhook(request)
