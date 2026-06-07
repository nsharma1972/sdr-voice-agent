"""
SQLite database layer. Defaults to sdr.db; override via DATABASE_URL=sqlite+aiosqlite:///./path.db
Tables are created on first startup — no separate migration step required for demo.
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

_DB_PATH = os.environ.get("DB_PATH", "sdr.db")

# SQLite-compatible schema (call_queue + calls)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS call_queue (
    id            TEXT PRIMARY KEY,
    company_name  TEXT NOT NULL,
    signal_type   TEXT,
    signal_summary TEXT,
    source_url    TEXT,
    priority      INTEGER NOT NULL DEFAULT 50,
    status        TEXT NOT NULL DEFAULT 'pending',
    scheduled_for TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    vapi_call_id  TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE INDEX IF NOT EXISTS idx_cq_status ON call_queue (status, scheduled_for);

CREATE TABLE IF NOT EXISTS calls (
    id              TEXT PRIMARY KEY,
    call_queue_id   TEXT REFERENCES call_queue(id),
    company_name    TEXT NOT NULL,
    signal_type     TEXT,
    outcome         TEXT,
    booked_meeting  INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    model_used      TEXT,
    transcript_text TEXT,
    cost_usd        REAL,
    reviewed        INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    started_at      TEXT,
    ended_at        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE INDEX IF NOT EXISTS idx_calls_company  ON calls (company_name);
CREATE INDEX IF NOT EXISTS idx_calls_outcome  ON calls (outcome);
CREATE INDEX IF NOT EXISTS idx_calls_reviewed ON calls (reviewed);
"""


async def init_db() -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
    finally:
        await db.close()


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── call_queue helpers ────────────────────────────────────────────────────────

async def enqueue_call(
    company_name: str,
    signal_type: str,
    signal_summary: str,
    source_url: str,
    scheduled_for: str,
    priority: int = 50,
) -> str | None:
    """
    Insert a pending call. Idempotent: skips if company already has a pending/dialing row.
    Returns the queue ID, or None if skipped.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM call_queue WHERE company_name=? AND status IN ('pending','dialing')",
            (company_name,),
        )
        row = await cursor.fetchone()
        if row:
            return None  # already queued
        qid = new_id()
        await db.execute(
            """INSERT INTO call_queue
               (id, company_name, signal_type, signal_summary, source_url,
                priority, status, scheduled_for)
               VALUES (?,?,?,?,?,?,'pending',?)""",
            (qid, company_name, signal_type, signal_summary, source_url, priority, scheduled_for),
        )
        await db.commit()
        return qid


async def fetch_due_calls(now_iso: str) -> list[dict]:
    """Return pending calls whose scheduled_for <= now."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM call_queue
               WHERE status='pending' AND scheduled_for <= ?
               ORDER BY priority DESC, scheduled_for ASC
               LIMIT 10""",
            (now_iso,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def mark_dialing(queue_id: str, vapi_call_id: str = "") -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE call_queue SET status='dialing', vapi_call_id=?, updated_at=? WHERE id=?",
            (vapi_call_id, now_iso(), queue_id),
        )
        await db.commit()


async def mark_queue_status(queue_id: str, status: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE call_queue SET status=?, updated_at=? WHERE id=?",
            (status, now_iso(), queue_id),
        )
        await db.commit()


# ── calls helpers ────────────────────────────────────────────────────────────

async def insert_call(
    company_name: str,
    signal_type: str,
    outcome: str,
    call_queue_id: str | None = None,
    duration_seconds: float | None = None,
    model_used: str | None = None,
    transcript_text: str | None = None,
    cost_usd: float | None = None,
    booked_meeting: bool = False,
) -> str:
    cid = new_id()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO calls
               (id, call_queue_id, company_name, signal_type, outcome,
                booked_meeting, duration_seconds, model_used, transcript_text, cost_usd)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cid, call_queue_id, company_name, signal_type, outcome,
             int(booked_meeting), duration_seconds, model_used, transcript_text, cost_usd),
        )
        await db.commit()
    return cid


async def list_calls(
    limit: int = 50,
    offset: int = 0,
    outcome: str | None = None,
    reviewed: bool | None = None,
) -> list[dict]:
    async with get_db() as db:
        where = []
        params: list = []
        if outcome:
            where.append("outcome=?")
            params.append(outcome)
        if reviewed is not None:
            where.append("reviewed=?")
            params.append(int(reviewed))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cursor = await db.execute(
            f"SELECT * FROM calls {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_calls(outcome: str | None = None, reviewed: bool | None = None) -> int:
    async with get_db() as db:
        where = []
        params: list = []
        if outcome:
            where.append("outcome=?")
            params.append(outcome)
        if reviewed is not None:
            where.append("reviewed=?")
            params.append(int(reviewed))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cursor = await db.execute(f"SELECT COUNT(*) FROM calls {where_sql}", params)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_call_review(
    call_id: str,
    *,
    outcome: str | None = None,
    reviewed: bool | None = None,
    notes: str | None = None,
    booked_meeting: bool | None = None,
    transcript_text: str | None = None,
) -> bool:
    async with get_db() as db:
        # outcome and transcript_text use direct SET (caller wins, no COALESCE)
        # so flush_transcript always overwrites the JS-set placeholder
        cursor = await db.execute(
            """UPDATE calls
               SET outcome=CASE WHEN ? IS NOT NULL THEN ? ELSE outcome END,
                   reviewed=COALESCE(?, reviewed),
                   notes=COALESCE(?, notes),
                   booked_meeting=CASE WHEN ? IS NOT NULL THEN ? ELSE booked_meeting END,
                   transcript_text=CASE WHEN ? IS NOT NULL THEN ? ELSE transcript_text END
               WHERE id=?""",
            (
                outcome, outcome,
                None if reviewed is None else int(reviewed),
                notes,
                None if booked_meeting is None else int(booked_meeting),
                None if booked_meeting is None else int(booked_meeting),
                transcript_text, transcript_text,
                call_id,
            ),
        )
        await db.commit()
        return cursor.rowcount > 0
