# ──────────────────────────────────────────────
# main.py — run scraper without the bot
# Useful for testing the scraper separately
#
# Run: python main.py
# ──────────────────────────────────────────────

import config
import scraper
import storage


def main():
    cats = ", ".join(config.CATEGORIES) if config.CATEGORIES else "all categories"
    print(f"🔍 Category: {cats} | language: {config.LANGUAGE}")
    print(f"   Pages: {config.MAX_PAGES}  |  Delay: {config.DELAY}s\n")

    vacancies = scraper.run()
    storage.add_vacancies(vacancies)

    print(f"\n✅ Done. Total in store: {len(storage.load_all())}")

    print("\n── Preview: first 3 vacancies ──")
    for v in vacancies[:3]:
        print()
        print(v.short())
        if v.description:
            print(f"   📝 {v.description[:200]}...")



if __name__ == "__main__":
    main()
