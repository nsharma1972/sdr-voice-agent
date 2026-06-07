#!/usr/bin/env bash
# start_demo.sh — one-command demo-day startup for SDR Voice Agent
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }

PIDS=()
cleanup() {
  echo ""
  info "Shutting down…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  exit 0
}
trap cleanup INT TERM

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SDR Voice Agent — Demo Day Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── env checks ────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then warn ".env not found — copy .env.example and fill in keys"; fi

DAILY_KEY=$(grep -s "^DAILY_API_KEY=" .env | cut -d= -f2)
DEEPGRAM_KEY=$(grep -s "^DEEPGRAM_API_KEY=" .env | cut -d= -f2)
LITELLM_URL=$(grep -s "^LITELLM_BASE_URL=" .env | cut -d= -f2 || echo "http://localhost:4000/v1")

[ -n "$DAILY_KEY" ]   && ok "DAILY_API_KEY set"   || warn "DAILY_API_KEY missing — browser demo won't work"
[ -n "$DEEPGRAM_KEY" ] && ok "DEEPGRAM_API_KEY set" || warn "DEEPGRAM_API_KEY missing — STT won't work"

echo ""

# ── 1. Ollama ─────────────────────────────────────────────────────────────────
info "Checking Ollama…"
if curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
  ok "Ollama running"
else
  warn "Ollama not running — starting it"
  ollama serve > /tmp/ollama.log 2>&1 &
  PIDS+=($!)
  sleep 3
  if curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
    ok "Ollama started"
  else
    fail "Ollama failed to start — check /tmp/ollama.log"
  fi
fi

# ── 2. LiteLLM router ─────────────────────────────────────────────────────────
info "Starting LiteLLM router…"
if curl -sf http://localhost:4000/health > /dev/null 2>&1; then
  ok "LiteLLM already running"
else
  if [ -f litellm.config.yaml ]; then
    litellm --config litellm.config.yaml > /tmp/litellm.log 2>&1 &
    PIDS+=($!)
    sleep 4
    if curl -sf http://localhost:4000/health > /dev/null 2>&1; then
      ok "LiteLLM started on :4000"
    else
      warn "LiteLLM slow to start — check /tmp/litellm.log"
    fi
  else
    warn "litellm.config.yaml not found — skipping router (cloud fallback only)"
  fi
fi

# ── 3. FastAPI backend ────────────────────────────────────────────────────────
info "Starting FastAPI backend…"
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  ok "Backend already running on :8000"
else
  uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
  PIDS+=($!)
  sleep 3

  MAX_WAIT=15; elapsed=0
  until curl -sf http://localhost:8000/health > /dev/null 2>&1 || [ $elapsed -ge $MAX_WAIT ]; do
    sleep 1; elapsed=$((elapsed+1))
  done

  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "Backend ready on :8000"
  else
    fail "Backend failed to start — check /tmp/backend.log"
    cat /tmp/backend.log | tail -20
    exit 1
  fi
fi

# ── ready ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "All services ready"
echo ""
echo "  Portal:  http://localhost:8000"
echo "  API:     http://localhost:8000/docs"
echo "  Logs:    /tmp/backend.log  /tmp/litellm.log"
echo ""
echo "  Demo flow:"
echo "  1. Open http://localhost:8000 → Leads tab → Refresh Signals"
echo "  2. Click Call on any CONTACT-tier lead"
echo "  3. Allow mic → AI agent speaks first"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

open http://localhost:8000 2>/dev/null || true

# keep running until Ctrl+C
info "Press Ctrl+C to stop all services"
wait
