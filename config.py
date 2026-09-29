# ──────────────────────────────────────────────
# config.py — all settings
# Edit only this file to customize the bot
# ──────────────────────────────────────────────
from datetime import time as t
import pytz
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Telegram ───────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TIMEZONE   = pytz.timezone("Europe/Riga")
SCAN_TIME  = t(hour=20, minute=55, tzinfo=TIMEZONE)
CHECK_TIME = t(hour=21, minute=0,  tzinfo=TIMEZONE)

# ── Scraper ────────────────────────────────────
CATEGORIES = ["INFORMATION_TECHNOLOGY"]
LANGUAGE = "en"
MAX_PAGES = 1

SEARCH_MODE = "keywords"  # 'category' | 'keywords' | 'both'
KEYWORDS = ["dizain", "design"]             # e.g. ["dizain", "design"]

# ── cvmarket.lv category (IT) ──────────────────────
CV_CATEGORY_ID   = 7
CV_CATEGORY_LABEL = "Mediji / Dizains / Radošie darbi"

DELAY = 1.5
USE_PLAYWRIGHT = True

# ── Storage ────────────────────────────────────
DATA_DIR = "data"
OUTPUT_JSON = f"{DATA_DIR}/vacancies.json"
SEEN_FILE   = f"{DATA_DIR}/seen.json"
TEMP_JSON   = f"{DATA_DIR}/temp.json"

# ── HTTP ───────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CARD_SELECTORS = [
    "a[data-id]",
    ".vacancy-item",
    "[class*='VacancyCard']",
    "[class*='vacancy-card']",
    "article",
]
