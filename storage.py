# ──────────────────────────────────────────────
# storage.py — saving and loading vacancies
# ──────────────────────────────────────────────

import json
import os

import config
from models import Vacancy


# ── Vacancy store (vacancies.json) ─────────────

def load_all() -> list[Vacancy]:
    """Load all saved vacancies from JSON."""
    try:
        with open(config.OUTPUT_JSON, encoding="utf-8") as f:
            return [Vacancy(**d) for d in json.load(f)]
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

def load_seen() -> set[str]:
    """Load the set of already-notified vacancy URLs."""
    try:
        with open(config.SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_seen(seen: set[str]) -> None:
    """Persist the set of notified URLs."""
    with open(config.SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def filter_new(vacancies: list[Vacancy]) -> list[Vacancy]:
    """Return only vacancies that have not been notified yet."""
    seen = load_seen()
    return [v for v in vacancies if v.url not in seen]


def mark_seen(vacancies: list[Vacancy]) -> None:
    """Mark a list of vacancies as notified."""
    seen = load_seen()
    seen.update(v.url for v in vacancies)
    save_seen(seen)
