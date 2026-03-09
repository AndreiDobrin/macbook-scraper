## Introduction

This is an automated scraper that fetches sealed and resealed macbooks from (currently) eMag and adds them to a database in order to check their prices. It checks prices every 2 hours.

<img width="1920" height="1048" alt="image" src="https://github.com/user-attachments/assets/8cd2fe2e-782f-49a2-8855-d8984cc4b7c7" />


## Motivation

It is meant as a helpful tool to make an educated decision on how to spend your money as wisely as possible.

## Architecture

Scraper: Python, Selenium (Headless Chromium), SQLite, Telegram Bot

Web Dashboard: .NET 10 Minimal API, HTML/JS, Chart.js, Bootstrap

Infrastructure: Docker & Docker Compose


## Prerequisites

You need to have [Docker](https://docs.docker.com/engine/install/) and [Docker Compose](https://docs.docker.com/compose/) installed on your host machine.
You also need a [Telegram bot token](https://core.telegram.org/bots/tutorial) and your Telegram ID for phone notifications.
You can get your personal Telegram ID by messaging @userinfobot

## Clone the Repository
```Bash
git clone https://github.com/AndreiDobrin/macbook-scraper
cd mactracker
```

## Setup Environment Variables

For security, Telegram bot tokens are passed via environment variables. Create a .env file in the root directory:
```Bash
touch .env
```
Open the .env file and add your Telegram credentials:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```
## Create the Data Directory
The SQLite database lives on the host machine so it isn't deleted when the containers restart. Create the data folder before running Docker:
```Bash
mkdir data
```
## Build and Run the Containers

Use Docker Compose to build the images and start the services in detached mode (background):
```Bash
sudo docker compose up -d --build
```
## Access the Dashboard

Once the containers are running, the web dashboard will be available at:
http://your-server-ip:5000 (or http://localhost:5000 if running locally)


### Useful Docker Commands

Here is a quick cheat sheet for managing the application:

View live logs (to see the Python scraper running):
```Bash
sudo docker compose logs -f scraper
```

Restart the scraper (if you updated scraper.py):
```Bash
sudo docker compose restart scraper
```

Rebuild the web app (if you updated .NET or HTML code):
```Bash
sudo docker compose up -d --build web
```

Check if containers are running:
```Bash
sudo docker compose ps
```


Stop everything safely:
```Bash
sudo docker compose down
```


## Known Issues

I have personally not had any issues with encountering captchas using Selenium with Chromium (although I did with BeautifulSoup). Since I have not had this issue, it was hard for me to build a system for it, so currently there is nothing in place to counteract or notify you if the website throws a captcha; the program will time out.
