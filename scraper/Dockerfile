FROM python:3.11-slim

# Install system dependencies needed for Playwright installation
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their system dependencies
RUN playwright install chromium --with-deps

COPY scraper.py .

# Ensure output is unbuffered to see logs in real-time
ENV PYTHONUNBUFFERED=1

CMD ["python", "scraper.py"]
