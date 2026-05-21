# ──────────────────────────────────────────────
# scraper.py — cv.lv parsing logic
# ──────────────────────────────────────────────

import time
import requests
from bs4 import BeautifulSoup

import config
from models import Vacancy


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def get_search_url(page: int = 0) -> str:
    """Build the search results URL for a given page number.

    Example (IT category, page 2):
    https://cv.lv/en/search?limit=20&offset=20&categories[0]=INFORMATION_TECHNOLOGY
    """
    offset = page * 20
    base = f"https://www.cv.lv/{config.LANGUAGE}/search?limit=20&offset={offset}"

    if not config.CATEGORIES:
        return base

    category_params = "&".join(
        f"categories%5B{i}%5D={cat}"
        for i, cat in enumerate(config.CATEGORIES)
    )
    return f"{base}&{category_params}"


def get_text(tag) -> str:
    """Safely extract stripped text from a BeautifulSoup tag."""
    return tag.get_text(strip=True) if tag else ""


def parse_card(card) -> dict:
    """Extract fields from a single vacancy card element."""

    link_tag = card.select_one("[data-testid*='vacancy-item-link-title']")
    href = link_tag.get("href", "") if link_tag else ""
    if href and not href.startswith("http"):
        href = "https://www.cv.lv" + href
    
    title_tag = (
        card.select_one("h3") or
        card.select_one("[class*='title']") or
        card.select_one("[class*='Title']")
    )
    company_tag  = card.select_one("[data-testid*='vacancy-item-link-employer']")
    salary_tag   = card.select_one("[class*='salary']")

    return {
        "title":    get_text(title_tag),
        "company":  get_text(company_tag),
        "salary":   get_text(salary_tag),
        "url":      href,
    }


def parse_vacancy_list(html: str) -> list[dict]:
    """Parse vacancy cards from a search results page."""
    soup = BeautifulSoup(html, "html.parser")

    cards = []
    for selector in config.CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            break

    if not cards:
        print("  [!] No vacancy cards found — the page is likely JS-rendered.")
        print("      Set USE_PLAYWRIGHT = True in config.py")
        return []

    return [parse_card(card) for card in cards]


def parse_vacancy_detail(html: str) -> str:
    """Extract the description text from an individual vacancy page."""
    soup = BeautifulSoup(html, "html.parser")

    for selector in config.DESCRIPTION_SELECTORS:
        block = soup.select_one(selector)
        if block:
            return get_text(block)

    return "[Description not found]"


# ──────────────────────────────────────────────
# MODE 1: REQUESTS (fast)
# ──────────────────────────────────────────────

def fetch_html(url: str) -> str | None:
    """Download a page's HTML via requests."""
    try:
        response = requests.get(url, headers=config.HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  [requests] Error: {e}")
        return None


def scrape_simple() -> list[Vacancy]:
    """Full scraping cycle using requests + BeautifulSoup."""
    all_vacancies = []

    for page_num in range(config.MAX_PAGES):
        url = get_search_url(page_num)
        print(f"\n📄 Page {page_num + 1}: {url}")

        html = fetch_html(url)
        if not html:
            break

        cards = parse_vacancy_list(html)
        if not cards:
            break

        print(f"  Found {len(cards)} cards")

        for i, card in enumerate(cards, 1):
            print(f"  [{i}/{len(cards)}] {card['title']} — {card['company']}")

            vacancy = Vacancy(
                **{k: card[k] for k in Vacancy.__dataclass_fields__ if k in card}
            )

            if card["url"]:
                time.sleep(config.DELAY)
                detail_html = fetch_html(card["url"])
                if detail_html:
                    vacancy.description = parse_vacancy_detail(detail_html)

            all_vacancies.append(vacancy)
            time.sleep(config.DELAY)

    return all_vacancies


# ──────────────────────────────────────────────
# MODE 2: PLAYWRIGHT (JS rendering)
# ──────────────────────────────────────────────

def _wait_for_cards(page) -> bool:
    try:
        page.wait_for_selector(", ".join(config.CARD_SELECTORS), timeout=10000)
        return True
    except Exception:
        return False


def _fetch_detail_playwright(page, url: str) -> str:
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
        page.wait_for_selector(", ".join(config.DESCRIPTION_SELECTORS), timeout=8000)
    except Exception:
        pass
    return page.content()


def scrape_playwright() -> list[Vacancy]:
    """Scraping via Playwright — for JS-rendered pages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed.")
        print("Run: pip install playwright && playwright install chromium")
        return []

    all_vacancies = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=config.HEADERS["User-Agent"],
            locale="en-US",
        )
        page = context.new_page()

        for page_num in range(config.MAX_PAGES):
            url = get_search_url(page_num)
            print(f"\n📄 Page {page_num + 1}: {url}")

            page.goto(url, wait_until="networkidle", timeout=30000)

            if not _wait_for_cards(page):
                print("  [!] Cards did not load.")
                break

            cards = parse_vacancy_list(page.content())
            if not cards:
                print("  [!] Cards could not be parsed.")
                break

            print(f"  Found {len(cards)} cards")

            for i, card in enumerate(cards, 1):
                print(f"  [{i}/{len(cards)}] {card['title']} — {card['company']}")

                vacancy = Vacancy(
                    **{k: card[k] for k in Vacancy.__dataclass_fields__ if k in card}
                )

                if card["url"]:
                    time.sleep(config.DELAY)
                    detail_html = _fetch_detail_playwright(page, card["url"])
                    vacancy.description = parse_vacancy_detail(detail_html)

                all_vacancies.append(vacancy)
                time.sleep(config.DELAY)

        browser.close()

    return all_vacancies


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

def run() -> list[Vacancy]:
    """Run scraping. Auto-switches to Playwright if requests returns nothing."""
    if config.USE_PLAYWRIGHT:
        return scrape_playwright()

    vacancies = scrape_simple()

    if not vacancies:
        print("\n⚙️  requests found nothing — switching to Playwright...")
        vacancies = scrape_playwright()

    return vacancies
