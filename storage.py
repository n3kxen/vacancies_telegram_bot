# ──────────────────────────────────────────────
# storage.py — saving and loading vacancies
# ──────────────────────────────────────────────

import json
import os

import config
from models import Vacancy

from datetime import datetime


# ── Vacancy store (vacancies.json) ─────────────

def load_all() -> list[Vacancy]:
    """Load all saved vacancies from JSON."""
    try:
        with open(config.OUTPUT_JSON, encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return[]
            return [Vacancy(**d) for d in json.loads(content)]
    except FileNotFoundError:
        return []


def save_all(vacancies: list[Vacancy]) -> None:
    """Overwrite the vacancy store with the given list."""
    with open(config.OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump([v.to_dict() for v in vacancies], f, ensure_ascii=False, indent=2)


def add_vacancies(new: list[Vacancy]) -> None:
    """Merge new vacancies into the store (no duplicates by URL)."""
    existing = load_all()
    existing_urls = {v.url for v in existing}
    to_add = [v for v in new if v.url not in existing_urls]
    if to_add:
        save_all(existing + to_add)


# ── Seen tracker (seen.json) ───────────────────

def load_seen() -> dict[str, dict]:
    """Load the seen tracker: {url: {"last_seen": iso_str}}."""
    try:
        with open(config.SEEN_FILE, encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            data = json.loads(content)
            if isinstance(data, list):
                return {url: {"last_seen": datetime.utcnow().isoformat()} for url in data}
            return data
    except FileNotFoundError:
        return {}


def save_seen(seen: dict[str, dict]) -> None:
    """Persist the seen tracker."""
    with open(config.SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)


from datetime import datetime, timedelta

# How many days before a previously seen vacancy can be considered "new again"
SEEN_REFRESH_DAYS = 7


def filter_new(vacancies: list[Vacancy]) -> list[Vacancy]:
    """
    Return only vacancies that are either unseen or were last notified
    more than SEEN_REFRESH_DAYS ago.
    """
    seen = load_seen()
    now = datetime.utcnow()
    fresh = []

    for v in vacancies:
        entry = seen.get(v.url)

        if entry is None:
            fresh.append(v)
            continue

        last_seen = datetime.fromisoformat(entry.get("last_seen", ""))
        if now - last_seen > timedelta(days=SEEN_REFRESH_DAYS):
            fresh.append(v)

    return fresh


def mark_seen(vacancies: list[Vacancy]) -> None:
    """Mark a list of vacancies as notified."""
    seen = load_seen()
    for v in vacancies:
        seen[v.url] = {"last_seen": datetime.utcnow().isoformat()}
    save_seen(seen)


def remove_expired(vacancies: list[Vacancy]) -> list[Vacancy]:
    """Remove vacancies whose expiry date has passed."""
    today = datetime.today()
    active = []

    for v in vacancies:
        if not v.expires:
            active.append(v)
            continue

        # Parse date from "Beidzas: 22.06.2026"
        try:
            date_str = v.expires.split(": ")[-1].strip()
            expiry = datetime.strptime(date_str, "%d.%m.%Y")
            if expiry >= today:
                active.append(v)
            else:
                print(f"  [expired] {v.title} — {v.expires}")
        except ValueError:
            active.append(v)  # if date can't be parsed, keep it

    return active

def clean_expired() -> int:
    """Remove expired vacancies from the store. Returns count of removed."""
    all_v = load_all()
    active = remove_expired(all_v)
    removed = len(all_v) - len(active)
    if removed > 0:
        save_all(active)
        print(f"  Removed {removed} expired vacancies")
    return removed

