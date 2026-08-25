# ──────────────────────────────────────────────
# storage.py — saving and loading vacancies
# ──────────────────────────────────────────────

import json
import os

import config
from models import Vacancy

from datetime import datetime, timedelta

# Default lifetime (in days) for a vacancy that has no expiry date from the site.
DEFAULT_LIFETIME_DAYS = 21  # 3 weeks


# ── Temp storage (temp.json) ─────────────────────

def load_temp() -> dict:
    """Load temp data: {'vacancies': [...], 'count': N, 'date': 'YYYY-MM-DD'}."""
    try:
        with open(config.TEMP_JSON, encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"vacancies": [], "count": 0, "date": ""}
            return json.loads(content)
    except FileNotFoundError:
        return {"vacancies": [], "count": 0, "date": ""}


def save_temp(vacancies: list[Vacancy]) -> None:
    """Save new vacancies to temp.json with count and current date."""
    data = {
        "vacancies": [v.to_dict() for v in vacancies],
        "count": len(vacancies),
        "date": datetime.utcnow().date().isoformat(),
    }
    with open(config.TEMP_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_temp() -> None:
    """Clear temp.json (write empty structure)."""
    save_temp([])


def load_temp_vacancies() -> list[Vacancy]:
    """Load the new vacancies saved during the last scan from temp.json."""
    data = load_temp()
    return [Vacancy(**d) for d in data.get("vacancies", [])]


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
        today = datetime.utcnow().date()
        for v in to_add:
            # Stamp when it was first stored
            if not v.added_date:
                v.added_date = today.isoformat()
            # Resolve expiry:
            #   - if site gave a real expiry label, use it (parse to ISO);
            #   - else default to 3 weeks after the added date.
            if not v.expiry_date:
                site_exp = _expiry_from_label(v.expires) if v.expires else None
                if site_exp:
                    v.expiry_date = site_exp.isoformat()
                else:
                    base = (
                        datetime.fromisoformat(v.added_date).date()
                        if v.added_date else today
                    )
                    v.expiry_date = (
                        base + timedelta(days=DEFAULT_LIFETIME_DAYS)
                    ).isoformat()
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
    """Remove vacancies whose effective expiry date has passed."""
    today = datetime.today().date()
    active = []

    for v in vacancies:
        expiry = _effective_expiry(v)
        if expiry is None:
            # No date info at all — keep it (shouldn't normally happen)
            active.append(v)
            continue
        if expiry >= today:
            active.append(v)
        else:
            print(f"  [expired] {v.title} — expires {expiry.isoformat()}")

    return active


def _expiry_from_label(label: str):
    """Parse a site expiry label like 'Beidzas: 22.06.2026' into a date, or None."""
    if not label:
        return None
    try:
        date_str = label.split(": ")[-1].strip()
        return datetime.strptime(date_str, "%d.%m.%Y").date()
    except (ValueError, IndexError):
        return None


def _effective_expiry(v: Vacancy):
    """Resolve the vacancy's effective expiry date (date object or None).

    Priority:
      1. explicit expiry_date (ISO) if present
      2. parsed site expiry label (expires: 'Beidzas: 22.06.2026')
      3. 3 weeks after added_date
      4. None if nothing is known
    """
    # 1) explicit ISO expiry_date
    if v.expiry_date:
        try:
            return datetime.fromisoformat(v.expiry_date).date()
        except ValueError:
            pass
    # 2) raw site label e.g. "Beidzas: 22.06.2026"
    if v.expires:
        try:
            date_str = v.expires.split(": ")[-1].strip()
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        except (ValueError, IndexError):
            pass
    # 3) default lifetime from added_date
    if v.added_date:
        try:
            added = datetime.fromisoformat(v.added_date).date()
            return added + timedelta(days=DEFAULT_LIFETIME_DAYS)
        except ValueError:
            pass
    # 4) nothing known
    return None

def clean_expired() -> int:
    """Remove expired vacancies from the store. Returns count of removed."""
    all_v = load_all()
    active = remove_expired(all_v)
    removed = len(all_v) - len(active)
    if removed > 0:
        save_all(active)
        print(f"  Removed {removed} expired vacancies")
    return removed

