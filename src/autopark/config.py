import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PREFERRED_LOCATION = os.getenv("PREFERRED_LOCATION", "")
RECEIPT_EMAIL = os.getenv("RECEIPT_EMAIL", "")

RUN_HOUR = int(os.getenv("RUN_HOUR", "9"))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", "5"))

CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_EXP = os.getenv("CARD_EXP", "")
CARD_CVV = os.getenv("CARD_CVV", "")
CARD_ZIP = os.getenv("CARD_ZIP", "")

LIVE_MODE = os.getenv("LIVE_MODE", "false").strip().lower() == "true"
HEADLESS = os.getenv("HEADLESS", "true").strip().lower() == "true"

DB_PATH = ROOT_DIR / "jobs.db"
SCREENSHOT_DIR = ROOT_DIR / "screenshots"
LOG_DIR = ROOT_DIR / "logs"

PARKING_URL = "https://paywithpassport.com/guest"


def require_bot_config():
    missing = [
        name
        for name, val in [
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")


def require_payment_config():
    missing = [
        name
        for name, val in [
            ("PREFERRED_LOCATION", PREFERRED_LOCATION),
            ("RECEIPT_EMAIL", RECEIPT_EMAIL),
            ("CARD_NUMBER", CARD_NUMBER),
            ("CARD_EXP", CARD_EXP),
            ("CARD_CVV", CARD_CVV),
            ("CARD_ZIP", CARD_ZIP),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")
