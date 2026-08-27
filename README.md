# Vacancy Bot

Telegram bot for tracking vacancies from cv.lv.

## Features

- Automatic daily vacancy check
- Aggregated report: one message with the number of new vacancies
- New vacancies are saved to JSON
- Browse saved vacancies (/vacancies) with pagination
- Stats: total vacancies, notified count, breakdown by company

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install python-telegram-bot requests beautifulsoup4
```

## Configuration

Set `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` in `config.py` or via `.env`.

## Run

```bash
source venv/bin/activate
python bot.py
```

## Commands

- /start — welcome screen with buttons
- /check — manually check for new vacancies
- /vacancies — list saved vacancies
- /stats — show statistics

## Buttons

After a check:
- 📋 View vacancies — open vacancy list
- 🏠 Home page — go back to start
