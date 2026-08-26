# Base image — lightweight Python 3.12
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency list first (Docker caches this layer separately —
# so reinstall only happens when requirements.txt actually changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install Playwright dependencies for Chromium
RUN playwright install-deps chromium

# Copy the rest of the project files
COPY . .

# Start the bot
CMD ["python", "bot.py"]
