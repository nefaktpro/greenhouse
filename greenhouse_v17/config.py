import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", os.getenv("HA_BASE_URL", "http://127.0.0.1:8123"))
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", os.getenv("HA_TOKEN", ""))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
