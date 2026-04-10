import os
from dotenv import load_dotenv

load_dotenv("/home/mi/greenhouse_v2/.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

HOME_ASSISTANT_URL = os.getenv("HA_BASE_URL", "").strip()
if not HOME_ASSISTANT_URL:
    HOME_ASSISTANT_URL = os.getenv("HA_URL", "").strip()

HOME_ASSISTANT_TOKEN = os.getenv("HA_TOKEN", "").strip()

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
STATUS_PUSH_TIMES = os.getenv("STATUS_PUSH_TIMES", "10:00,23:00").strip()
