import os
from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./sdr.db")

# Daily.co — free tier, 10K participant-minutes/month
DAILY_API_KEY = os.environ.get("DAILY_API_KEY", "")

# LLM routing — local Mistral via LiteLLM (free)
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "none")

# Cloud LLM fallback — only used when local times out
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# STT — Deepgram free tier: 12K minutes/year; set to empty to skip
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# TTS — edge-tts is free with no key; these are unused by default
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")

# Cal.com booking — free tier
CALCOM_API_KEY = os.environ.get("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = os.environ.get("CALCOM_EVENT_TYPE_ID", "")

# Sender identity
SENDER_NAME = os.environ.get("SENDER_NAME", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
CAL_LINK = os.environ.get("CAL_LINK", "")

# Email (Resend)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

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
    for var in ("DAILY_API_KEY", "LITELLM_BASE_URL"):
        if not os.environ.get(var):
            missing.append(var)
    return missing
