from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import sqlite3
import re
import asyncio
import os
import random

# We can safely import functions from our main scraper module
from scraper import extract_macbook_specs, extract_ipad_specs, alert_new, alert_sold, should_send_alert

async def altex_scraper(page, connection, cursor, link, is_ipad=False):
    print(f"Scraping Altex link: {link}")
    try:
        await asyncio.sleep(random.uniform(2, 5))
        await page.goto(link, timeout=60000, wait_until="domcontentloaded")
        
        # Accept cookies if present
        try:
            accept_btn = page.locator("text=Accepta")
            if await accept_btn.count() > 0:
                await accept_btn.first.click(timeout=3000)
        except:
            pass
            
        # We will look for product cards using typical Altex selectors
        try:
            await page.wait_for_selector(".Products-item", timeout=20000)
        except:
            print(f"No cards found on {link}. Maybe empty or layout changed.")
            return

        product_cards = await page.locator(".Products-item").all()

        for product in product_cards:
            try:
                title_elem = product.locator(".Product-name")
                if await title_elem.count() == 0: continue
                product_title = await title_elem.inner_text(timeout=5000)
                
                if is_ipad and not re.search(r'\b(Apple|iPad)\b', product_title, re.IGNORECASE):
                    continue
                if not is_ipad and not re.search(r'\b(Apple|MacBook)\b', product_title, re.IGNORECASE):
                    continue

                price_elem = product.locator(".Price-current")
                if await price_elem.count() == 0: continue
                product_offerprice_text = await price_elem.inner_text(timeout=5000)
                
                specs = extract_ipad_specs(product_title) if is_ipad else extract_macbook_specs(product_title)
                
                # Check for "resigilat" badge or text in title
                resigilat_badge = product.locator("text=Resigilat")
                if await resigilat_badge.count() > 0 or "resigilat" in product_title.lower():
                    specs["sealed"] = 0
                else:
                    specs["sealed"] = 1
                    
                match = re.search(r'[\d\.,]+', product_offerprice_text.replace('.', '').replace(',', '.'))
                if match:
                    # Altex format is often 5.499,90 lei
                    raw_price = match.group(0) 
                    product_offerprice = float(raw_price)
                else:
                    continue
                    
                pricing_elem_old = product.locator(".Price-old")
                product_fullprice = product_offerprice
                is_sale = 0
                if await pricing_elem_old.count() > 0:
                    product_fullprice_text = await pricing_elem_old.inner_text(timeout=5000)
                    match = re.search(r'[\d\.,]+', product_fullprice_text.replace('.', '').replace(',', '.'))
                    if match:
                        product_fullprice = float(match.group(0))
                        if specs["sealed"] == 1:
                            is_sale = 1

                link_elem = product.locator("a.Product-name")
                if await link_elem.count() == 0:
                    link_elem = product.locator("a")
                
                if await link_elem.count() == 0: continue
                product_link = await link_elem.first.get_attribute("href", timeout=5000)
                if product_link and product_link.startswith('/'):
                    product_link = 'https://altex.ro' + product_link
                
                print(f"Found on Altex: {product_title} - {product_offerprice} RON")

                # DB Logic
                query_model = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ? AND category = ? AND connectivity = ?"
                cursor.execute(query_model, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], specs['category'], specs['connectivity']))
                model_result = cursor.fetchone()
                
                if model_result is None:
                    query_insert_model = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture, category, connectivity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query_insert_model, (specs['type'], product_title, specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], specs['category'], specs['connectivity']))
                    id_model = cursor.lastrowid
                else:
                    id_model = model_result[0]

                cursor.execute("SELECT id_product FROM product WHERE link = ?", (product_link,))
                product_result = cursor.fetchone()

                if product_result is None:
                    query_insert_product = "INSERT INTO product (id_model, link, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?)"
                    cursor.execute(query_insert_product, (id_model, product_link, 'ALTEX', 1, specs['sealed'], ""))
                    id_product = cursor.lastrowid
                    
                    cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                    connection.commit()
                    
                    print(f"New product: {product_title}")
                    if await should_send_alert(cursor, specs, product_offerprice):
                        await alert_new(product_title, product_offerprice, product_link, 'ALTEX', product_fullprice)
                else:
                    id_product = product_result[0]
                    cursor.execute("UPDATE product SET last_seen = datetime('now', 'localtime'), active = 1 WHERE id_product = ?", (id_product,))
                    
                    cursor.execute("SELECT offer_price, full_price FROM price_history WHERE id_product = ? ORDER BY recorded_at DESC LIMIT 1", (id_product,))
                    latest_price = cursor.fetchone()
                    
                    if latest_price is None or latest_price[0] != product_offerprice or latest_price[1] != product_fullprice:
                        cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                        print(f"Price update for: {product_title}")
                        if await should_send_alert(cursor, specs, product_offerprice):
                            await alert_new(f"UPDATE PRET: {product_title}", product_offerprice, product_link, 'ALTEX', product_fullprice)
                        
                    connection.commit()
            except Exception as e:
                print(f"Error processing product card: {e}")
                continue

    except Exception as e:
        print(f"Error in altex_scraper for {link}: {e}")

async def run_altex_cycle():
    macbook_link = "https://altex.ro/laptopuri/cpl/filtru/brand-3180/apple/"
    ipad_link = "https://altex.ro/tablete/cpl/filtru/brand-3180/apple/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        await stealth_async(page)

        while True:
            print("Starting Altex scrape cycle...")
            connection = None
            try:
                connection = sqlite3.connect('/data/macbooks.db')
                cursor = connection.cursor()

                cursor.execute("SELECT datetime('now', 'localtime')")
                script_start_time = cursor.fetchone()[0]

                # MacBooks
                await altex_scraper(page, connection, cursor, link=macbook_link, is_ipad=False)
                
                # iPads
                await altex_scraper(page, connection, cursor, link=ipad_link, is_ipad=True)

                # Check DB last seen just for ALTEX
                query = '''
                    SELECT p.platform, m.title, 
                           (SELECT offer_price FROM price_history WHERE id_product = p.id_product ORDER BY recorded_at DESC LIMIT 1), 
                           p.id_product, m.category, m.type, m.ram, m.storage, p.sealed
                    FROM product p 
                    JOIN model m ON p.id_model = m.id_model 
                    WHERE p.last_seen < ? AND p.sealed = 0 AND p.active = 1 AND p.platform = 'ALTEX'
                '''
                cursor.execute(query, (script_start_time, ))
                results = cursor.fetchall()
                
                for result in results:
                    platform = result[0]
                    title = result[1]
                    offer_price = result[2]
                    id_product = result[3]
                    
                    specs = {
                        'category': result[4],
                        'type': result[5],
                        'ram': result[6],
                        'storage': result[7],
                        'sealed': result[8]
                    }
                    
                    if offer_price is not None and await should_send_alert(cursor, specs, offer_price):
                        await alert_sold(title, offer_price, platform)
                        
                    cursor.execute("UPDATE product SET active = 0 WHERE id_product = ?", (id_product, ))
                    
                connection.commit()

            except Exception as e:
                print("Error during scrape cycle:", e)
            finally:
                if connection:
                    connection.close()

            print("Cycle complete. Sleeping for 2 hours...")
            await asyncio.sleep(7200)

if __name__ == "__main__":
    asyncio.run(run_altex_cycle())
