import asyncio
import json
import os
import csv
from typing import List
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Bot

SEARCH_URL = "https://www.olx.pl/goluchow_115019/q-iphone/?search[dist]=50&search[filter_float_price:from]=450&search[filter_float_price:to]=2400&search[order]=created_at:desc"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)  # <- DODAJ TO!
SEEN_FILE = "seen_ads.json"
CSV_FILE = "iphone_prices.csv"

def load_seen_ads() -> List[str]:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return []

def save_seen_ads(seen: List[str]):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)

def save_price_to_csv(title: str, price: str, date: str, url: str):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "title", "price", "date", "url"])
        writer.writerow([datetime.now().isoformat(), title, price, date, url])

async def send_telegram_message(bot: Bot, message: str):
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")

async def fetch_ads(bot: Bot):
    seen_ads = load_seen_ads()
    new_ads = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(SEARCH_URL, timeout=60000)
        cards = await page.query_selector_all('div[data-cy="l-card"]')

        for idx, card in enumerate(cards, start=1):
            try:
                title_el = await card.query_selector("h4")
                title = await title_el.inner_text() if title_el else "brak tytułu"
                title = title.strip() if title else "brak tytułu"

                price_el = await card.query_selector("p[data-testid='ad-price']")
                price = await price_el.inner_text() if price_el else "brak ceny"

                date_el = await card.query_selector("p[data-testid='location-date']")
                date = await date_el.inner_text() if date_el else "brak daty"

                url_el = await card.query_selector("a")
                url = await url_el.get_attribute("href") if url_el else "brak linku"
                full_url = f"https://www.olx.pl{url}" if url and url.startswith("/") else url or "brak linku"
                ad_id = full_url.split("-")[-1].replace(".html", "")

                if ad_id not in seen_ads:
                    message = f"<b>{title}</b>\n{price}\n{date}\n{full_url}"
                    await send_telegram_message(bot, message)
                    save_price_to_csv(title, price, date, full_url)
                    seen_ads.append(ad_id)
                    new_ads.append(ad_id)
            except Exception as e:
                print(f"Błąd w ogłoszeniu {idx}: {e}")

        await browser.close()
        save_seen_ads(seen_ads)

async def main_loop():
    while True:
        try:
            await fetch_ads(bot)
        except Exception as e:
            print(f"❌ Błąd: {e}")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
