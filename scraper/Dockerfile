FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers are pre-installed in this image, 
# but we ensure the correct ones are available for the version in requirements.txt
RUN playwright install chromium

COPY scraper.py .

# Ensure output is unbuffered to see logs in real-time
ENV PYTHONUNBUFFERED=1

CMD ["python", "scraper.py"]
