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
    MessageHandler,
    filters,
    ContextTypes,
)

import config
import scraper
import scraper_cvmarket
import storage
import time as time_module
from models import Vacancy


# Scan time (5 min before notification)
SCAN_TIME = config.SCAN_TIME

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# How many vacancies to show per page
PAGE_SIZE = 5


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

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

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Vacancies", callback_data="action:vacancies"),
            InlineKeyboardButton("🔍 Check now", callback_data="action:check"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="action:stats"),
        ],
    ])

    target = update.message or (update.callback_query.message if update.callback_query else None)
    if target is None:
        return

    await target.reply_text(
        f"<b>💼 Vacancy Bot</b>\n\n"
        f"📂 Category: <code>{cats}</code>\n"
        f"📨 Notify at: <b>{config.CHECK_TIME.strftime('%H:%M')}</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    all_v = storage.load_all()
    seen  = storage.load_seen()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Vacancies", callback_data="action:vacancies"),
            InlineKeyboardButton("🔍 Check now", callback_data="action:check"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="action:stats"),
        ],
    ])

    cats = ", ".join(config.CATEGORIES) if config.CATEGORIES else "all categories"

    await update.message.reply_text(
        f"<b>💼 Vacancy Bot</b>\n\n"
        f"📂 Category: <code>{cats}</code>\n"
        f"📨 Notify at: <b>{config.CHECK_TIME.strftime('%H:%M')}</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "action:vacancies":
        await cmd_vacancies(update, ctx)
    elif query.data == "action:check":
        msg = await query.message.reply_text("🔍 Checking for new vacancies…")
        new_vacancies = await _do_check(ctx)

        reply_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Vacancies", callback_data="action:vacancies"),
                InlineKeyboardButton("📊 Stats", callback_data="action:stats"),
                InlineKeyboardButton("🏠 Home page", callback_data="action:start"),
            ]
        ])

        if new_vacancies:
            await msg.edit_text(f"✅ Found <b>{len(new_vacancies)}</b> new vacancies!", parse_mode="HTML", reply_markup=reply_keyboard)

            # Send second message with paginated list of new vacancies
            log.info(f"Sending new vacancies list, count: {len(new_vacancies)}")
            total_pages = (len(new_vacancies) + PAGE_SIZE - 1) // PAGE_SIZE
            await _send_new_vacancies_page(
                send_fn=lambda text, **kw: query.message.reply_text(text, **kw),
                vacancies=new_vacancies,
                page=0,
                total_pages=total_pages,
            )
        else:
            await msg.edit_text("😴 No new vacancies found.", reply_markup=reply_keyboard)
    elif query.data == "action:stats":
        all_v = storage.load_all()
        seen  = storage.load_seen()

        by_company: dict[str, int] = {}
        for v in all_v:
            company = (getattr(v, "company", "") or "").strip()
            if not company:
                continue
            by_company[company] = by_company.get(company, 0) + 1

        lines = [
            "📊 <b>Stats</b>\n",
            f"💾 Saved vacancies: <b>{len(all_v)}</b>",
            f"✅ Already notified: <b>{len(seen)}</b>",
        ]
        if by_company:
            lines.append("🏢 <b>Open vacancies by company:</b>")
            for company, count in sorted(by_company.items()):
                lines.append(f"• {company}: <b>{count}</b>")

        await query.message.reply_text("\n".join(lines), parse_mode="HTML")
    elif query.data == "action:start":
        await cmd_start(update, ctx)


async def cmd_vacancies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the first page of saved vacancies."""
    vacancies = list(reversed(storage.load_all()))

    message = update.message or update.callback_query.message

    if not vacancies:
        await message.reply_text(
            "No saved vacancies yet.\nTry /check to fetch them now."
        )
        return

    total_pages = (len(vacancies) + PAGE_SIZE - 1) // PAGE_SIZE
    await _send_vacancy_page(message.reply_text, vacancies, page=0, total_pages=total_pages)


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger a vacancy check."""
    msg = await update.message.reply_text("🔍 Checking for new vacancies…")
    new_vacancies = await _do_check(ctx)

    reply_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Vacancies", callback_data="action:vacancies"),
            InlineKeyboardButton("📊 Stats", callback_data="action:stats"),
            InlineKeyboardButton("🏠 Home page", callback_data="action:start"),
        ]
    ])

    if new_vacancies:
        await msg.edit_text(f"✅ Found <b>{len(new_vacancies)}</b> new vacancies!", parse_mode="HTML", reply_markup=reply_keyboard)

        # Send second message with paginated list of new vacancies
        log.info(f"Sending new vacancies list, count: {len(new_vacancies)}")
        total_pages = (len(new_vacancies) + PAGE_SIZE - 1) // PAGE_SIZE
        await _send_new_vacancies_page(
            send_fn=lambda text, **kw: update.message.reply_text(text, **kw),
            vacancies=new_vacancies,
            page=0,
            total_pages=total_pages,
        )
    else:
        await msg.edit_text("😴 No new vacancies found.", reply_markup=reply_keyboard)


# ──────────────────────────────────────────────
# PAGINATION CALLBACK
# ──────────────────────────────────────────────

async def on_page_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Prev / Next button presses in /vacancies."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":")[1])
    vacancies = list(reversed(storage.load_all()))
    total_pages = (len(vacancies) + PAGE_SIZE - 1) // PAGE_SIZE

    # Replace the existing message instead of sending a new one
    await _send_vacancy_page(
        send_fn=lambda text, **kw: query.edit_message_text(text, **kw),
        vacancies=vacancies,
        page=page,
        total_pages=total_pages,
    )


async def _send_vacancy_page(send_fn, vacancies, page: int, total_pages: int) -> None:
    start = page * PAGE_SIZE
    chunk = vacancies[start : start + PAGE_SIZE]

    lines = [f"📋 <b>Vacancies</b>  (page {page + 1}/{total_pages})\n"]
    for i, v in enumerate(chunk, start=start + 1):
        expires = f"   ⏳ Expires: {v.expiry_date}" if v.expiry_date else ""

        lines.append(
            f"<b>{i}. {v.title}</b>\n"
            f"   🏢 {v.company}\n"
            + (f"   💶 {v.salary}\n" if v.salary else "")
            + f"{expires}\n"
            f"   🔗 <a href='{v.url}'>Open</a>"
        )

    text = "\n\n".join(lines)
    keyboard = build_pagination(page, total_pages)

    await send_fn(text, parse_mode="HTML", reply_markup=keyboard,
                  disable_web_page_preview=True)


async def _send_new_vacancies_page(send_fn, vacancies: list[Vacancy], page: int, total_pages: int) -> None:
    """Send a page of newly found vacancies with pagination."""
    log.info(f"Sending new vacancies page {page+1}/{total_pages}, vacancies count: {len(vacancies)}")
    start = page * PAGE_SIZE
    chunk = vacancies[start : start + PAGE_SIZE]

    lines = [f"🆕 <b>New Vacancies</b>  (page {page + 1}/{total_pages})\n"]
    for i, v in enumerate(chunk, start=start + 1):
        expires = f"   ⏳ Expires: {v.expiry_date}" if v.expiry_date else ""

        lines.append(
            f"<b>{i}. {v.title}</b>\n"
            f"   🏢 {v.company}\n"
            + (f"   💶 {v.salary}\n" if v.salary else "")
            + f"{expires}\n"
            f"   🔗 <a href='{v.url}'>Open</a>"
        )

    text = "\n\n".join(lines)
    # Build keyboard with newpage: prefix
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"newpage:{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"newpage:{page + 1}"))
    keyboard = InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([[]])

    await send_fn(text, parse_mode="HTML", reply_markup=keyboard,
                  disable_web_page_preview=True)
    log.info("New vacancies page sent successfully")


async def on_new_page_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Prev / Next button presses for new vacancies list."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":")[1])
    # Load new vacancies from temp.json (written during the last scan)
    new_vacancies = storage.load_temp_vacancies()
    total_pages = (len(new_vacancies) + PAGE_SIZE - 1) // PAGE_SIZE

    if not new_vacancies:
        await query.edit_message_text("No new vacancies from last scan.")
        return

    if page >= total_pages:
        page = total_pages - 1

    await _send_new_vacancies_page(
        send_fn=lambda text, **kw: query.edit_message_text(text, **kw),
        vacancies=new_vacancies,
        page=page,
        total_pages=total_pages,
    )

# ──────────────────────────────────────────────
# CORE: CHECK & NOTIFY
# ──────────────────────────────────────────────

async def _do_check(ctx: ContextTypes.DEFAULT_TYPE) -> list[Vacancy]:
    """
    Scrape cv.lv and cvmarket.lv, merge, dedupe by (title, company)
    keeping the cv.lv variant first, save new vacancies to temp.json and the
    full store. Returns the list of new vacancies found.
    """
    # metrics removed
    # metrics removed
    log.info("Running vacancy scan…")

    try:
        # Clear temp.json at the start of every new scheduled scan
        storage.clear_temp()

        loop = asyncio.get_event_loop()
        # cv.lv first, then cvmarket.lv (cv.lv has priority on dedup)
        cv_v        = await loop.run_in_executor(None, scraper.run)
        cvmarket_v  = await loop.run_in_executor(None, scraper_cvmarket.run)

        # Merge and dedupe by (title, company); keep first occurrence (cv.lv wins)
        seen_keys: set[tuple[str, str]] = set()
        merged: list[Vacancy] = []
        for v in cv_v + cvmarket_v:
            key = (v.title.strip().lower(), v.company.strip().lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(v)

        vacancies = merged
        log.info(f"Merged: cv.lv={len(cv_v)}, cvmarket.lv={len(cvmarket_v)}, after dedup={len(vacancies)}")

        removed = storage.clean_expired()

        if removed:
            log.info(f"Removed {removed} expired vacancies")

        if not vacancies:
            log.info("No vacancies returned by scrapers.")
            # metrics removed
            return []

        new = storage.filter_new(vacancies)
        log.info(f"Total scraped: {len(vacancies)}, new: {len(new)}")

        if not new:
            # metrics removed
            return []

        storage.add_vacancies(new)        # append to full store (vacancies.json)
        storage.mark_seen(new)
        storage.save_temp(new)           # persist today's new vacancies to temp.json
        # metrics removed
        # metrics removed

        return new

    except Exception as e:
        # metrics removed
        log.error(f"Check failed: {e}")
        return []


async def scheduled_scan(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job at 20:55 — scan + write temp.json (no Telegram message)."""
    log.info("Scheduled scan started (20:55)")
    await _do_check(ctx)
    log.info("Scheduled scan finished — temp.json updated")


async def scheduled_notify(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job at 21:00 — read temp.json and send notification + list."""
    log.info("Scheduled notify started (21:00)")
    new_vacancies = storage.load_temp_vacancies()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Vacancies", callback_data="action:vacancies"),
            InlineKeyboardButton("📊 Stats", callback_data="action:stats"),
            InlineKeyboardButton("🏠 Home page", callback_data="action:start"),
        ]
    ])

    if new_vacancies:
        await ctx.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"✅ Found <b>{len(new_vacancies)}</b> new vacancies!",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        # Second message: paginated list of new vacancies from temp.json
        log.info(f"Sending new vacancies list, count: {len(new_vacancies)}")
        total_pages = (len(new_vacancies) + PAGE_SIZE - 1) // PAGE_SIZE
        await _send_new_vacancies_page(
            send_fn=lambda text, **kw: ctx.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text, **kw),
            vacancies=new_vacancies,
            page=0,
            total_pages=total_pages,
        )
    else:
        await ctx.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="😴 No new vacancies found.",
            reply_markup=keyboard,
        )


# ──────────────────────────────────────────────
# STARTUP & MAIN
# ──────────────────────────────────────────────

async def on_startup(app: Application) -> None:
    # 20:55 — scan + write temp.json (no message)
    app.job_queue.run_daily(scheduled_scan, time=config.SCAN_TIME)
    # 21:00 — read temp.json, send notification + list
    app.job_queue.run_daily(scheduled_notify, time=config.CHECK_TIME)
    log.info(f"Scheduler started. Scan at {config.SCAN_TIME}, notify at {config.CHECK_TIME}")

def main() -> None:
    # metrics removed
    log.info("Metrics server started on :8000")

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
    app.add_handler(CallbackQueryHandler(on_new_page_button, pattern=r"^newpage:\d+$"))
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^action:"))

    log.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
