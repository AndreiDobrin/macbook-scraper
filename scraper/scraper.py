from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import sqlite3
import re
import asyncio
import telegram
from telegram.request import HTTPXRequest
import time
import os
import random

telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_token = os.getenv("TELEGRAM_CHAT_ID")

if not telegram_token or not chat_token:
    print("CRITICAL ERROR: Telegram credentials not found in environment!")
    exit(1)

async def alert_new(titlu, pret_oferta, link, platforma, pret_intreg="Necunoscut"):
    longer_request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = telegram.Bot(token=telegram_token, request=longer_request)
    async with bot:
        await bot.send_message(text=f"Produs nou pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}\n{link}", chat_id=chat_token)

async def alert_sold(titlu, pret_oferta, platforma, pret_intreg="Necunoscut"):
    longer_request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = telegram.Bot(token=telegram_token, request=longer_request)
    async with bot:
        await bot.send_message(text=f"Produs vandut pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}", chat_id=chat_token)

def extract_macbook_specs(title):
    clean_title = " ".join(title.split())
    specs = {
        "type": "N/A", "size": "N/A", "cpu": "N/A", "cpu_cores": "N/A",
        "gpu_cores": "N/A", "ram": "N/A", "storage": "N/A", "color": "N/A",
        "nano_texture": 0, "sealed": 1, "category": "Laptop", "connectivity": "N/A"
    }

    if "RESIGILAT" in clean_title:
        specs["sealed"] = 0
    if "MacBook Air" in clean_title:
        specs["type"] = "MacBook Air"
    elif "MacBook Pro" in clean_title:
        specs["type"] = "MacBook Pro"

    size_match = re.search(r'(\d+(\.\d+)?)(?="| -inch|-inch)', clean_title)
    if size_match:
        specs["size"] = float(size_match.group(1))

    cpu_match = re.search(r'cu procesor (Apple M\w+(?: Pro| Max| Ultra)?)', clean_title, re.IGNORECASE)
    if cpu_match:
        specs["cpu"] = cpu_match.group(1)

    cpu_cores_match = re.search(r'(\d+)\s*nuclee CPU', clean_title)
    if cpu_cores_match:
        specs["cpu_cores"] = int(cpu_cores_match.group(1))

    gpu_cores_match = re.search(r'(\d+)\s*nuclee GPU', clean_title)
    if gpu_cores_match:
        specs["gpu_cores"] = int(gpu_cores_match.group(1))

    memory_matches = re.findall(r'(\d+)\s*(GB|TB)', clean_title)
    found_ram = False
    found_storage = False

    for amount, unit in memory_matches:
        amount = int(amount)
        if unit == "TB":
            specs["storage"] = amount * 1024
            found_storage = True
        elif unit == "GB":
            if not found_ram and amount in [8, 16, 18, 24, 32, 36, 48, 64, 96, 128]:
                 if f"{amount} {unit} SSD" in clean_title or f"{amount}{unit} SSD" in clean_title:
                     specs["storage"] = amount
                     found_storage = True
                 else:
                     specs["ram"] = amount
                     found_ram = True
            elif amount >= 256:
                specs["storage"] = amount
                found_storage = True
            elif found_ram and not found_storage:
                 specs["storage"] = amount
                 found_storage = True

    known_colors = ["Silver", "Space Grey", "Space Gray", "Midnight", "Starlight", "Space Black", "Sky Blue", "Gold", "Rose Gold"]
    for color in known_colors:
        if color.lower() in clean_title.lower():
            specs["color"] = color
            break

    if "Textura Nano" in clean_title or "Nano-texture" in clean_title:
        specs["nano_texture"] = 1
    else:
        specs["nano_texture"] = 0

    return specs

def extract_ipad_specs(title):
    clean_title = " ".join(title.split())
    specs = {
        "type": "N/A", "size": "N/A", "cpu": "N/A", "cpu_cores": 0,
        "gpu_cores": 0, "ram": 0, "storage": "N/A", "color": "N/A",
        "nano_texture": 0, "sealed": 1, "category": "Tablet", "connectivity": "Wi-Fi"
    }

    if "RESIGILAT" in clean_title:
        specs["sealed"] = 0
    
    if "iPad Pro" in clean_title:
        specs["type"] = "iPad Pro"
    elif "iPad Air" in clean_title:
        specs["type"] = "iPad Air"
    elif "iPad mini" in clean_title:
        specs["type"] = "iPad mini"
    elif "iPad" in clean_title:
        specs["type"] = "iPad"

    size_match = re.search(r'(\d+(\.\d+)?)(?="|\s*-inch|-inch)', clean_title)
    if size_match:
        specs["size"] = float(size_match.group(1))

    cpu_match = re.search(r'(M\d|A\d+\s*Pro|A\d+)', clean_title)
    if cpu_match:
        specs["cpu"] = cpu_match.group(1)

    if "Wi-Fi + Cellular" in clean_title or "Cellular" in clean_title:
        specs["connectivity"] = "Wi-Fi + Cellular"
    else:
        specs["connectivity"] = "Wi-Fi"

    memory_matches = re.findall(r'(\d+)\s*(GB|TB)', clean_title)
    for amount, unit in memory_matches:
        amount = int(amount)
        if unit == "TB":
            specs["storage"] = amount * 1024
        elif unit == "GB":
            if amount >= 32:
                specs["storage"] = amount

    known_colors = ["Silver", "Space Grey", "Space Gray", "Midnight", "Starlight", "Space Black", "Purple", "Blue", "Pink", "Yellow"]
    for color in known_colors:
        if color.lower() in clean_title.lower():
            specs["color"] = color
            break

    if "Textura Nano" in clean_title or "Nano-texture" in clean_title:
        specs["nano_texture"] = 1

    return specs

def setupDatabase():
    connection = sqlite3.connect('/data/macbooks.db')
    cursor = connection.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS model (
        id_model INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        title TEXT NOT NULL, 
        size NUMERIC NOT NULL,
        cpu TEXT NOT NULL,
        cpu_cores INTEGER NOT NULL,
        gpu_cores INTEGER NOT NULL,
        ram INTEGER NOT NULL,
        storage INTEGER NOT NULL,
        color TEXT NOT NULL,
        nano_texture INTEGER NOT NULL check(nano_texture = 0 or nano_texture = 1),
        category TEXT DEFAULT 'Laptop',
        connectivity TEXT DEFAULT 'N/A'
    )
    ''')

    cursor.execute("PRAGMA table_info(model)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'category' not in columns:
        cursor.execute("ALTER TABLE model ADD COLUMN category TEXT DEFAULT 'Laptop'")
    if 'connectivity' not in columns:
        cursor.execute("ALTER TABLE model ADD COLUMN connectivity TEXT DEFAULT 'N/A'")
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product (
        id_product INTEGER PRIMARY KEY AUTOINCREMENT,
        id_model INTEGER NOT NULL,
        link TEXT NOT NULL UNIQUE,
        current_price NUMERIC,
        last_seen TEXT DEFAULT (datetime('now', 'localtime')),
        platform TEXT,
        active INTEGER check(active = 0 or active = 1),
        sealed INTEGER check(sealed = 0 or sealed = 1),
        description TEXT,
        FOREIGN KEY (id_model) REFERENCES model(id_model)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id_history INTEGER PRIMARY KEY AUTOINCREMENT,
        id_product INTEGER NOT NULL,
        full_price NUMERIC,      
        offer_price NUMERIC NOT NULL, 
        is_sale INTEGER CHECK(is_sale = 0 OR is_sale = 1), 
        recorded_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (id_product) REFERENCES product(id_product)
    )
    ''')

    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS update_current_price 
    AFTER INSERT ON price_history
    BEGIN
        UPDATE product 
        SET current_price = NEW.offer_price 
        WHERE id_product = NEW.id_product;
    END;
    ''')

    connection.commit()
    connection.close()

async def emag_scraper(page, connection, cursor, link="https://www.emag.ro/laptopuri/brand/apple/resigilate/c?ref=lst_leftbar_6407_resealed", is_ipad=False):
    print(f"Scraping link: {link}")
    try:
        # Human-like delay
        await asyncio.sleep(random.uniform(2, 5))
        
        await page.goto(link, timeout=60000, wait_until="domcontentloaded")
        
        # Check for block
        if "Robot" in await page.title() or await page.locator("text=Verify you are human").count() await page.locator("text=Verif").count() > 0:
            print("CRITICAL: Blocked by bot protection!")
            return

        # Resilient wait
        try:
            await page.wait_for_selector(".card-standard", timeout=20000)
        except:
            print(f"No cards found on {link}. Maybe empty or layout changed.")
            return

        product_cards = await page.locator(".card-standard").all()

        for product in product_cards:
            try:
                title_elem = product.locator(".card-v2-title")
                if await title_elem.count() == 0: continue
                product_title = await title_elem.inner_text(timeout=5000)
                
                if is_ipad and "Apple" not in product_title and "iPad" not in product_title:
                    continue

                price_elem = product.locator(".product-new-price")
                if await price_elem.count() == 0: continue
                product_offerprice_text = await price_elem.inner_text(timeout=5000)
                
                specs = extract_ipad_specs(product_title) if is_ipad else extract_macbook_specs(product_title)
                
                match = re.search(r'[\d\.,]+', product_offerprice_text)
                if match:
                    raw_price = match.group(0) 
                    product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
                else:
                    continue
                    
                pricing_elem = product.locator(".pricing")
                product_fullprice_text = "0"
                if await pricing_elem.count() > 0:
                    product_fullprice_text = await pricing_elem.inner_text(timeout=5000)
                
                is_sale = 0
                if "PRP" not in product_fullprice_text:
                    match = re.search(r'[\d\.,]+', product_fullprice_text)
                    if match:
                        raw_price = match.group(0)
                        product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                        if specs["sealed"] == 1:
                            is_sale = 1
                    else:
                        product_fullprice = product_offerprice
                else:
                    product_fullprice = product_offerprice
                    
                link_elem = product.locator(".card-v2-thumb")
                if await link_elem.count() == 0: continue
                product_link = await link_elem.get_attribute("href", timeout=5000)
                
                print(f"Found: {product_title} - {product_offerprice} RON")

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
                    cursor.execute(query_insert_product, (id_model, product_link, 'EMAG', 1, specs['sealed'], ""))
                    id_product = cursor.lastrowid
                    
                    cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                    connection.commit()
                    
                    print(f"New product: {product_title}")
                    await alert_new(product_title, product_offerprice, product_link, 'EMAG', product_fullprice)
                else:
                    id_product = product_result[0]
                    cursor.execute("UPDATE product SET last_seen = datetime('now', 'localtime'), active = 1 WHERE id_product = ?", (id_product,))
                    
                    cursor.execute("SELECT offer_price, full_price FROM price_history WHERE id_product = ? ORDER BY recorded_at DESC LIMIT 1", (id_product,))
                    latest_price = cursor.fetchone()
                    
                    if latest_price is None or latest_price[0] != product_offerprice or latest_price[1] != product_fullprice:
                        cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                        print(f"Price update for: {product_title}")
                        
                    connection.commit()
            except Exception as e:
                print(f"Error processing product card: {e}")
                continue

    except Exception as e:
        print(f"Error in emag_scraper for {link}: {e}")

async def get_emag_sealed(page, connection, cursor, link="https://www.emag.ro/laptopuri/brand/apple/filter/emag-genius-f9538,livrate-de-emag-v30/c?ref=lst_leftbar_9538_30", is_ipad=False):
    print(f"Scraping sealed link: {link}")
    try:
        await asyncio.sleep(random.uniform(2, 5))
        await page.goto(link, timeout=60000, wait_until="domcontentloaded")
        
        while True:
            # Check for block
            if "Robot" in await page.title() or await page.locator("text=Verify you are human").count() > 0:
                print("CRITICAL: Blocked by bot protection!")
                return

            try:
                await page.wait_for_selector(".card-standard", timeout=20000)
            except:
                break

            product_cards = await page.locator(".card-standard").all()
            if not product_cards: break

            for product in product_cards:
                try:
                    is_sale = 0
                    active = 1
                    
                    title_elem = product.locator(".card-v2-title")
                    if await title_elem.count() == 0: continue
                    product_title = await title_elem.inner_text(timeout=5000)
                    
                    if is_ipad and "Apple" not in product_title and "iPad" not in product_title:
                        continue

                    specs = extract_ipad_specs(product_title) if is_ipad else extract_macbook_specs(product_title)
                    price_elem = product.locator(".product-new-price")
                    if await price_elem.count() == 0: continue
                    product_offerprice_text = await price_elem.inner_text(timeout=5000)
                    
                    match = re.search(r'[\d\.,]+', product_offerprice_text)
                    if match:
                        raw_price = match.group(0) 
                        product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
                    else:
                        continue
                    
                    pricing_elem = product.locator(".pricing")
                    product_fullprice_text = "0"
                    if await pricing_elem.count() > 0:
                        product_fullprice_text = await pricing_elem.inner_text(timeout=5000)

                    if "PRP" not in product_fullprice_text:
                        match = re.search(r'[\d\.,]+', product_fullprice_text)
                        if match:
                            raw_price = match.group(0)
                            product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                            if specs["sealed"] == 1:
                                is_sale = 1
                        else:
                            product_fullprice = product_offerprice
                    else:
                        product_fullprice = product_offerprice
                    
                    stock_elem = product.locator(".text-availability-out_of_stock")
                    if await stock_elem.count() > 0:
                        active = 0

                    link_elem = product.locator(".card-v2-thumb")
                    if await link_elem.count() == 0: continue
                    product_link = await link_elem.get_attribute("href", timeout=5000)
                    
                    query_model = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ? AND category = ? AND connectivity = ?"
                    cursor.execute(query_model, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], specs['category'], specs['connectivity']))
                    model_result = cursor.fetchone()

                    if model_result is None:
                        query_insert_model = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture, category, connectivity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                        cursor.execute(query_insert_model, (specs["type"], product_title, specs["size"], specs["cpu"], specs["cpu_cores"], specs["gpu_cores"], specs["ram"], specs["storage"], specs["color"], specs["nano_texture"], specs["category"], specs["connectivity"]))
                        id_model = cursor.lastrowid
                    else:
                        id_model = model_result[0]

                    cursor.execute("SELECT id_product FROM product WHERE link = ?", (product_link,))
                    product_result = cursor.fetchone()

                    if product_result is None:
                        query_insert_product = "INSERT INTO product (id_model, link, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?)"
                        cursor.execute(query_insert_product, (id_model, product_link, "EMAG", active, 1, ""))
                        id_product = cursor.lastrowid
                        
                        cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                        connection.commit()
                    else:
                        id_product = product_result[0]
                        cursor.execute("UPDATE product SET active = ?, last_seen = datetime('now', 'localtime') WHERE id_product = ?", (active, id_product))
                        
                        cursor.execute("SELECT offer_price, full_price FROM price_history WHERE id_product = ? ORDER BY recorded_at DESC LIMIT 1", (id_product,))
                        latest_price = cursor.fetchone()
                        
                        if latest_price is None or latest_price[0] != product_offerprice or latest_price[1] != product_fullprice:
                            cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                            
                        connection.commit()
                except Exception as e:
                    print(f"Error processing sealed product card: {e}")
                    continue

            try:
                next_page_btn = page.locator("a.js-change-page[aria-label='Next']")
                if await next_page_btn.count() > 0 and await next_page_btn.is_visible():
                    await next_page_btn.scroll_into_view_if_needed()
                    await next_page_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(random.uniform(1, 3))
                else:
                    break
            except:
                break

    except Exception as e:
        print(f"Error in get_emag_sealed for {link}: {e}")

async def checkDBlastSeen(cursor, connection, script_start_time):
    query = '''
        SELECT p.platform, m.title, 
               (SELECT offer_price FROM price_history WHERE id_product = p.id_product ORDER BY recorded_at DESC LIMIT 1), 
               p.id_product
        FROM product p 
        JOIN model m ON p.id_model = m.id_model 
        WHERE p.last_seen < ? AND p.sealed = 0 AND p.active = 1
    '''
    cursor.execute(query, (script_start_time, ))
    results = cursor.fetchall()
    
    for result in results:
        platform = result[0]
        title = result[1]
        offer_price = result[2]
        id_product = result[3]
        
        await alert_sold(title, offer_price, platform)
        cursor.execute("UPDATE product SET active = 0 WHERE id_product = ?", (id_product, ))
        
    connection.commit()

async def run_scrape_cycle():
    ipad_resealed_link = "https://www.emag.ro/tablete/resigilate/filter/producator-procesor-f7884,apple-v-4875704/c?ref=lst_leftbar_6407_resealed"
    ipad_sealed_link = "https://www.emag.ro/tablete/stoc/filter/producator-procesor-f7884,apple-v-4875704/c?ref=lst_leftbar_6407_stock"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        await stealth_async(page)

        while True:
            print("Starting scrape cycle...")
            connection = None
            try:
                connection = sqlite3.connect('/data/macbooks.db')
                cursor = connection.cursor()

                cursor.execute("SELECT datetime('now', 'localtime')")
                script_start_time = cursor.fetchone()[0]

                # MacBooks
                await emag_scraper(page, connection, cursor)
                await get_emag_sealed(page, connection, cursor)

                # iPads
                await emag_scraper(page, connection, cursor, link=ipad_resealed_link, is_ipad=True)
                await get_emag_sealed(page, connection, cursor, link=ipad_sealed_link, is_ipad=True)

                await checkDBlastSeen(cursor, connection, script_start_time)

            except Exception as e:
                print("Error during scrape cycle:", e)
            finally:
                if connection:
                    connection.close()

            print("Cycle complete. Sleeping for 2 hours...")
            await asyncio.sleep(7200)

if __name__ == "__main__":
    setupDatabase()
    asyncio.run(run_scrape_cycle())
