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
    # python-dotenv not installed; rely on environment variables
    pass

# ── Telegram ───────────────────────────────────
# Get token from @BotFather, chat_id from @userinfobot
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Time zone and daily schedule
TIMEZONE   = pytz.timezone("Europe/Riga")
SCAN_TIME  = t(hour=20, minute=55, tzinfo=TIMEZONE)  # scrape + write temp.json
CHECK_TIME = t(hour=21, minute=0,  tzinfo=TIMEZONE)  # send notification from temp.json

# ── Scraper ────────────────────────────────────
# Categories to search. Empty list = all vacancies.
# Available codes:
#   INFORMATION_TECHNOLOGY, FINANCE_ACCOUNTING, MARKETING_PR,
#   SALES, ADMINISTRATION, LOGISTICS, ENGINEERING, MEDICINE,
#   CONSTRUCTION, EDUCATION, LAW, MANAGEMENT, CUSTOMER_SERVICE,
#   DESIGN, HR, PRODUCTION, TRANSPORT, OTHER
CATEGORIES = ["INFORMATION_TECHNOLOGY"]

# Site language: "ru" | "lv" | "en"
LANGUAGE = "en"

# How many result pages to process per check (20 vacancies per page)
MAX_PAGES = 1

# Delay between requests in seconds (below 1.0 risks getting banned)
DELAY = 1.5

# True  — use Playwright (for JS-rendered pages, slower)
# False — try requests first (fast), auto-switch to Playwright if needed
# cvmarket.lv filters by category only through its JS widget, so Playwright
# is REQUIRED for the category filter to work.
USE_PLAYWRIGHT = True

# ── Storage ────────────────────────────────────
# Files that store vacancies state
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

# ── Selectors ──────────────────────────────────
CARD_SELECTORS = [
    "a[data-id]",
    ".vacancy-item",
    "[class*='VacancyCard']",
    "[class*='vacancy-card']",
    "article",
]

