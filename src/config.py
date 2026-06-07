import os
from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


DATABASE_URL = _req("DATABASE_URL")

# Vapi
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID", "")
VAPI_WEBHOOK_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET", "")

# LLM routing
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "none")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Voice providers (passed to Vapi)
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")

# Cal.com booking
CALCOM_API_KEY = os.environ.get("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = os.environ.get("CALCOM_EVENT_TYPE_ID", "")

# Sender identity
SENDER_NAME = os.environ.get("SENDER_NAME", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
CAL_LINK = os.environ.get("CAL_LINK", "")

# Email
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
CALL_WINDOW_START_HOUR = 8   # 8am prospect local time
CALL_WINDOW_END_HOUR = 21    # 9pm prospect local time
EMAIL_WAIT_DAYS = 5          # days after email before voice follow-up
MAX_CALL_ATTEMPTS = 2
VOICEMAIL_MAX_SECONDS = 25


def assert_voice_ready() -> list[str]:
    """Returns missing env vars needed before the agent can make calls."""
    missing = []
    for var in ("VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID", "CALCOM_API_KEY",
                "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY"):
        if not os.environ.get(var):
            missing.append(var)
    return missing
