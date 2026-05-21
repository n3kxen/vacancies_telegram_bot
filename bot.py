# ──────────────────────────────────────────────
# bot.py — Telegram bot
#
# Commands:
#   /start      — welcome message
#   /vacancies  — browse saved vacancies (paginated)
#   /check      — manually trigger a new vacancy check
#   /stats      — show total saved / seen counts
#
# Install:
#   pip install python-telegram-bot requests beautifulsoup4
#   pip install playwright && playwright install chromium  # only if USE_PLAYWRIGHT=True
#
# Run:
#   python bot.py
# ──────────────────────────────────────────────

import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import config
import scraper
import storage

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# How many vacancies to show per page in /vacancies
PAGE_SIZE = 5


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def format_vacancy(v, index: int | None = None) -> str:
    """Format a single vacancy as a Telegram message (HTML)."""
    header = f"<b>#{index}  {v.title}</b>" if index else f"<b>{v.title}</b>"
    salary = f"\n💰 <i>{v.salary}</i>" if v.salary else ""
    desc = v.description[:300].strip() + "…" if v.description else ""

    return (
        f"{header}\n"
        f"🏢 {v.company}\n"
        f"{salary}\n"
        f"🔗 <a href='{v.url}'>Open vacancy</a>\n\n"
        f"{desc}"
    )


def build_pagination(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Build Prev / Next navigation buttons."""
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page:{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{page + 1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([[]])


# ──────────────────────────────────────────────
# COMMAND HANDLERS
# ──────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cats = ", ".join(config.CATEGORIES) if config.CATEGORIES else "all categories"
    interval_min = config.CHECK_INTERVAL // 60

    await update.message.reply_text(
        f"👋 <b>CV.lv Vacancy Bot</b>\n\n"
        f"📂 Category: <code>{cats}</code>\n"
        f"🕐 Checks every <b>{interval_min} min</b>\n\n"
        f"Commands:\n"
        f"  /vacancies — browse saved vacancies\n"
        f"  /check     — check for new vacancies now\n"
        f"  /stats     — show counts",
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    all_v = storage.load_all()
    seen  = storage.load_seen()
    await update.message.reply_text(
        f"📊 <b>Stats</b>\n\n"
        f"💾 Saved vacancies: <b>{len(all_v)}</b>\n"
        f"✅ Already notified: <b>{len(seen)}</b>",
        parse_mode="HTML",
    )


async def cmd_vacancies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the first page of saved vacancies."""
    vacancies = storage.load_all()

    if not vacancies:
        await update.message.reply_text(
            "No saved vacancies yet.\nTry /check to fetch them now."
        )
        return

    total_pages = (len(vacancies) + PAGE_SIZE - 1) // PAGE_SIZE
    await _send_vacancy_page(update.message.reply_text, vacancies, page=0, total_pages=total_pages)


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger a vacancy check."""
    msg = await update.message.reply_text("🔍 Checking for new vacancies…")
    count = await _do_check(ctx)

    if count:
        await msg.edit_text(f"✅ Found and sent <b>{count}</b> new vacancies!", parse_mode="HTML")
    else:
        await msg.edit_text("😴 No new vacancies found.")


# ──────────────────────────────────────────────
# PAGINATION CALLBACK
# ──────────────────────────────────────────────

async def on_page_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Prev / Next button presses in /vacancies."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":")[1])
    vacancies = storage.load_all()
    total_pages = (len(vacancies) + PAGE_SIZE - 1) // PAGE_SIZE

    # Replace the existing message instead of sending a new one
    await _send_vacancy_page(
        send_fn=lambda text, **kw: query.edit_message_text(text, **kw),
        vacancies=vacancies,
        page=page,
        total_pages=total_pages,
    )


async def _send_vacancy_page(send_fn, vacancies, page: int, total_pages: int) -> None:
    """Render one page of vacancies and send it via send_fn."""
    start = page * PAGE_SIZE
    chunk = vacancies[start : start + PAGE_SIZE]

    lines = [f"📋 <b>Vacancies</b>  (page {page + 1}/{total_pages})\n"]
    for i, v in enumerate(chunk, start=start + 1):
        salary = f" · 💰 {v.salary}" if v.salary else ""
        lines.append(
            f"<b>{i}. {v.title}</b>\n"
            f"   🏢 {v.company} {salary}\n"
            f"   🔗 <a href='{v.url}'>Open</a>"
        )

    text = "\n\n".join(lines)
    keyboard = build_pagination(page, total_pages)

    await send_fn(text, parse_mode="HTML", reply_markup=keyboard,
                  disable_web_page_preview=True)


# ──────────────────────────────────────────────
# CORE: CHECK & NOTIFY
# ──────────────────────────────────────────────

async def _do_check(ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Scrape cv.lv, save new vacancies, send Telegram notifications.
    Returns the number of new vacancies sent.
    """
    log.info("Running vacancy check…")

    # Run blocking scraper in a thread so the event loop stays free
    loop = asyncio.get_event_loop()
    vacancies = await loop.run_in_executor(None, scraper.run)

    if not vacancies:
        log.info("No vacancies returned by scraper.")
        return 0

    new = storage.filter_new(vacancies)
    log.info(f"Total scraped: {len(vacancies)}, new: {len(new)}")

    if not new:
        return 0

    # Save to store and mark as seen before sending
    storage.add_vacancies(new)
    storage.mark_seen(new)

    for v in new:
        text = format_vacancy(v)
        try:
            await ctx.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.error(f"Failed to send message: {e}")

    return len(new)


async def scheduled_check(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job called by the scheduler every CHECK_INTERVAL seconds."""
    await _do_check(ctx)


# ──────────────────────────────────────────────
# STARTUP & MAIN
# ──────────────────────────────────────────────

async def on_startup(app: Application) -> None:
    """Schedule the periodic vacancy check after the bot starts."""
    app.job_queue.run_repeating(
        scheduled_check,
        interval=config.CHECK_INTERVAL,
        first=10,  # first check 10 seconds after start
    )
    log.info(f"Scheduler started. Interval: {config.CHECK_INTERVAL}s")


def main() -> None:
    if config.TELEGRAM_TOKEN == "YOUR_BOT_TOKEN":
        print("❌ Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in config.py first!")
        return

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("vacancies",  cmd_vacancies))
    app.add_handler(CommandHandler("check",      cmd_check))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CallbackQueryHandler(on_page_button, pattern=r"^page:\d+$"))

    log.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
