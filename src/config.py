import os
from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./sdr.db")

# Daily.co — legacy transport; not used by the no-card browser demo
DAILY_API_KEY = os.environ.get("DAILY_API_KEY", "")

# LiveKit — no-card browser WebRTC demo transport
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# LLM routing — Groq (free) preferred; falls back to local LiteLLM
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
LLM_MODEL        = os.environ.get("LLM_MODEL", "mistral-small-local")
LITELLM_API_KEY  = os.environ.get("LITELLM_API_KEY", "none")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# STT — Deepgram free tier: 12K minutes/year; set to empty to skip
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# Cartesia — ~75ms TTFB, free tier 1K chars/day
CARTESIA_API_KEY  = os.environ.get("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID = os.environ.get("CARTESIA_VOICE_ID", "")

# ElevenLabs — Flash v2.5 TTS, free tier user-created voices only
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")

# Local LLM — set to route to exo cluster via LiteLLM instead of Groq
# Example: LOCAL_LLM_MODEL=qwen3-30b
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "")

# Cal.com booking — free tier
CALCOM_API_KEY = os.environ.get("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = os.environ.get("CALCOM_EVENT_TYPE_ID", "")

# Sender identity
SENDER_NAME = os.environ.get("SENDER_NAME", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
CAL_LINK = os.environ.get("CAL_LINK", "")

# Email (Resend)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

# Vapi outbound phone calling — Phase 2 only, not needed for browser demo
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID", "")

# Portal
PORTAL_PASSWORD = os.environ.get("PORTAL_PASSWORD", "")
PORTAL_SESSION_SECRET = os.environ.get("PORTAL_SESSION_SECRET", "dev-only-secret")
PORTAL_HOST = os.environ.get("PORTAL_HOST", "127.0.0.1")
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", "8000"))

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# Scoring thresholds
SCORE_CONTACT_THRESHOLD = 60
SCORE_NURTURE_THRESHOLD = 40
WEEKLY_CONTACT_QUOTA = 20

# Voice call settings
CALL_WINDOW_START_HOUR = 8
CALL_WINDOW_END_HOUR = 21
EMAIL_WAIT_DAYS = 5
MAX_CALL_ATTEMPTS = 2


def assert_voice_ready() -> list[str]:
    """Returns missing env vars needed before demo sessions can run."""
    missing = []
    for var in (
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "DEEPGRAM_API_KEY",
        "LITELLM_BASE_URL",
    ):
        if not os.environ.get(var):
            missing.append(var)
    return missing
