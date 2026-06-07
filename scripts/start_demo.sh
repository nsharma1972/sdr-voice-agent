#!/usr/bin/env bash
# start_demo.sh — one-command demo-day startup for SDR Voice Agent
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }

PIDS=()
LITELLM_BIN="${LITELLM_BIN:-litellm}"
UVICORN_BIN="${UVICORN_BIN:-uvicorn}"
if [ -x .venv/bin/litellm ]; then LITELLM_BIN=".venv/bin/litellm"; fi
if [ -x .venv/bin/uvicorn ]; then UVICORN_BIN=".venv/bin/uvicorn"; fi
if [ -x .venv/bin/python ]; then
  CERT_FILE=$(.venv/bin/python -c 'import certifi; print(certifi.where())' 2>/dev/null || true)
  if [ -n "$CERT_FILE" ]; then
    export SSL_CERT_FILE="$CERT_FILE"
    export REQUESTS_CA_BUNDLE="$CERT_FILE"
  fi
fi

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

LIVEKIT_URL=$(grep -s "^LIVEKIT_URL=" .env | cut -d= -f2-)
LIVEKIT_KEY=$(grep -s "^LIVEKIT_API_KEY=" .env | cut -d= -f2-)
LIVEKIT_SECRET=$(grep -s "^LIVEKIT_API_SECRET=" .env | cut -d= -f2-)
DEEPGRAM_KEY=$(grep -s "^DEEPGRAM_API_KEY=" .env | cut -d= -f2)
LITELLM_URL=$(grep -s "^LITELLM_BASE_URL=" .env | cut -d= -f2 || echo "http://localhost:4000/v1")

[ -n "$LIVEKIT_URL" ] && ok "LIVEKIT_URL set" || warn "LIVEKIT_URL missing — browser demo won't work"
[ -n "$LIVEKIT_KEY" ] && ok "LIVEKIT_API_KEY set" || warn "LIVEKIT_API_KEY missing — browser demo won't work"
[ -n "$LIVEKIT_SECRET" ] && ok "LIVEKIT_API_SECRET set" || warn "LIVEKIT_API_SECRET missing — browser demo won't work"
[ -n "$DEEPGRAM_KEY" ] && ok "DEEPGRAM_API_KEY set" || warn "DEEPGRAM_API_KEY missing — STT won't work"

if [ -z "$LIVEKIT_URL" ] || [ -z "$LIVEKIT_KEY" ] || [ -z "$LIVEKIT_SECRET" ] || [ -z "$DEEPGRAM_KEY" ]; then
  echo ""
  fail "Voice demo is not ready. Add LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and DEEPGRAM_API_KEY to .env, then rerun make demo."
  exit 1
fi

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
if curl -sf http://localhost:4000/v1/models > /dev/null 2>&1; then
  ok "LiteLLM already running"
else
  if [ -f litellm.config.yaml ]; then
    "$LITELLM_BIN" --host 127.0.0.1 --port 4000 --config litellm.config.yaml > /tmp/litellm.log 2>&1 &
    PIDS+=($!)
    MAX_WAIT=20; elapsed=0
    until curl -sf http://localhost:4000/v1/models > /dev/null 2>&1 || [ $elapsed -ge $MAX_WAIT ]; do
      sleep 1; elapsed=$((elapsed+1))
    done
    if curl -sf http://localhost:4000/v1/models > /dev/null 2>&1; then
      ok "LiteLLM started on :4000"
    else
      fail "LiteLLM failed to start — check /tmp/litellm.log"
      tail -20 /tmp/litellm.log
      exit 1
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
  "$UVICORN_BIN" src.main:app --host 127.0.0.1 --port 8000 > /tmp/backend.log 2>&1 &
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
