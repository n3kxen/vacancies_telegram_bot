# ──────────────────────────────────────────────
# scraper_cvmarket.py — cvmarket.lv parsing logic
# ──────────────────────────────────────────────

import time

import config
from models import Vacancy

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.cvmarket.lv"

# Category IDs on cvmarket.lv and their human-readable labels (LV).
# The category filter is JS-only: the server ignores category params on a
# direct GET, so we must open the page in a real browser, pick the category
# from the widget, and submit the form. We select by label to stay robust.
CATEGORY_ID   = 8
CATEGORY_LABEL = "Informācijas tehnoloģijas"  # id 8 — IT


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def get_base_url() -> str:
    """Search URL before the category filter is applied via the UI."""
    return (
        f"{BASE_URL}/darba-piedavajumi"
        f"?op=search&search[job_salary]=3&search[keyword]=&start=0"
    )


def get_text(tag) -> str:
    """Safely extract stripped text from a BeautifulSoup tag."""
    return tag.get_text(strip=True) if tag else ""


def parse_card(card) -> dict | None:
    """Extract fields from a single vacancy card."""

    # Link — the card itself is the <a> tag with class jobad-url
    href = card.get("href", "")
    if href and not href.startswith("http"):
        href = BASE_URL + href

    title_tag   = card.select_one("h2")
    company_tag = card.select_one(".job-company")
    salary_tag  = card.select_one(".salary-block.hidden.lg\\:inline-block")
    location_tag = card.select_one(".location")

    title = get_text(title_tag)
    if not title:
        return None  # skip empty cards

    return {
        "title":   title,
        "company": get_text(company_tag),
        "salary":  get_text(salary_tag),
        "location": get_text(location_tag),
        "expires": "",   # cvmarket.lv does not show expiry date
        "url":     href,
        "source":  "cvmarket.lv",
    }


def parse_vacancy_list(html: str) -> list[dict]:
    """Parse vacancy cards from a cvmarket.lv search results page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.jobad-url")

    if not cards:
        print("  [cvmarket] No vacancy cards found on page.")
        return []

    results = []
    for card in cards:
        parsed = parse_card(card)
        if parsed:
            results.append(parsed)

    return results


# ──────────────────────────────────────────────
# FETCH (Playwright — JS-rendered filtering)
# ──────────────────────────────────────────────

def _apply_category(page) -> None:
    """
    Open the category widget, pick CATEGORY_LABEL, apply, and submit the
    search form so the server returns a category-filtered result set.
    """
    # Open the category selector
    page.locator("text=Meklēt pēc kategorijas").first.click()
    page.wait_for_timeout(1200)

    # Pick the target category from the dropdown
    page.locator(f"text={CATEGORY_LABEL}").first.click()
    page.wait_for_timeout(1200)

    # Confirm inside the widget (closes it)
    apply = page.locator("button:has-text('Pielietot')").filter(visible=True).first
    if apply.count():
        apply.click()
        page.wait_for_timeout(1500)

    # Submit the search form via JS to avoid click interception by overlays
    page.evaluate(
        "() => {"
        "  const f = document.getElementById('top_search_form');"
        "  if (f) { f.requestSubmit ? f.requestSubmit() : f.submit(); }"
        "}"
    )
    # Wait for the filtered list to render
    page.wait_for_selector("a.jobad-url", timeout=30000)
    page.wait_for_timeout(2000)


def _page_html(page) -> str:
    return page.content()


def run() -> list[Vacancy]:
    """
    Scrape cvmarket.lv (IT category) and return a list of Vacancy objects.

    The category filter only works through the site's JS widget, so this
    uses a headless browser to select the category and submit the form.
    """
    all_vacancies: list[Vacancy] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ── Page 0: load, apply category filter, capture filtered URL ──
        page.goto(get_base_url(), wait_until="networkidle", timeout=60000)
        page.wait_for_selector("a.jobad-url", timeout=30000)
        page.wait_for_timeout(2000)

        if CATEGORY_ID:
            print(f"  [cvmarket] Applying category filter: {CATEGORY_LABEL}")
            _apply_category(page)

        filtered_url = page.url
        print(f"\n📄 [cvmarket] Page 1: {filtered_url}")

        html = _page_html(page)
        cards = parse_vacancy_list(html)
        print(f"  Found {len(cards)} cards")

        for card in cards:
            all_vacancies.append(_to_vacancy(card))

        # ── Pages 2..N: paginate via start= on the filtered URL ──
        for page_num in range(1, config.MAX_PAGES):
            offset = page_num * 30
            url = f"{filtered_url}&start={offset}"
            print(f"\n📄 [cvmarket] Page {page_num + 1}: {url}")

            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_selector("a.jobad-url", timeout=30000)
            page.wait_for_timeout(1500)

            cards = parse_vacancy_list(page.content())
            if not cards:
                break
            print(f"  Found {len(cards)} cards")
            for card in cards:
                all_vacancies.append(_to_vacancy(card))

        browser.close()

    return all_vacancies


def _to_vacancy(card: dict) -> Vacancy:
    # cvmarket.lv does NOT expose a real expiry date, so we leave both
    # `expires` and `expiry_date` empty. storage.add_vacancies() then stamps
    # `added_date` (today) and `expiry_date` = added_date + 3 weeks, so the
    # vacancy auto-expires after 3 weeks in vacancies.json.
    v = Vacancy(
        title=card["title"],
        company=card["company"],
        salary=card["salary"],
        expires=card["expires"],   # "" — no expiry info from site
        url=card["url"],
        added_date="",             # stamped by storage on first save
        expiry_date="",            # "" => 3 weeks after added_date (storage)
    )
    print(f"  • {card['title']} — {card['company']}")
    time.sleep(config.DELAY)
    return v
