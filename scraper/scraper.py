from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from telegram.request import HTTPXRequest
import sqlite3
import re
import asyncio
import telegram
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time

with open("telegram_token.txt", "r") as f:
    telegram_token = f.readline()[:-1]
    chat_token = f.readline()

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

async def alert_new(titlu, pret_oferta, link, platforma, pret_intreg="Necunoscut"):
    longer_request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = telegram.Bot(token=telegram_token, request=longer_request)
    async with bot:
        await bot.send_message(text=f"Mac nou pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}\n{link}", chat_id = chat_token)

async def alert_sold(titlu, pret_oferta, platforma, pret_intreg="Necunoscut"):
    longer_request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = telegram.Bot(token=telegram_token, request=longer_request)
    async with bot:
        await bot.send_message(text=f"Mac vandut pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}", chat_id = chat_token)

def extract_macbook_specs(title):
    clean_title = " ".join(title.split())
    specs = {
        "type": "N/A", "size": "N/A", "cpu": "N/A", "cpu_cores": "N/A",
        "gpu_cores": "N/A", "ram": "N/A", "storage": "N/A", "color": "N/A",
        "nano_texture": 0, "sealed": 1
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
        nano_texture INTEGER NOT NULL check(nano_texture = 0 or nano_texture = 1)
    )
    ''')
    

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product (
        id_product INTEGER PRIMARY KEY AUTOINCREMENT,
        id_model INTEGER NOT NULL,
        link TEXT NOT NULL UNIQUE,
        current_price NUMERIC,  -- Cached for fast website sorting/filtering
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


def emag_scraper(connection, cursor, link="https://www.emag.ro/laptopuri/brand/apple/resigilate/c?ref=lst_leftbar_6407_resealed"):
    driver = get_driver()
    driver.get(link)
    wait = WebDriverWait(driver, timeout=30)
    
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "card-standard")))
        product_cards = driver.find_elements(By.CLASS_NAME, "card-standard")

        for product in product_cards:
            product_title = product.find_element(By.CLASS_NAME, "card-v2-title").text
            product_offerprice = product.find_element(By.CLASS_NAME, "product-new-price").text
            specs = extract_macbook_specs(product_title)
            
            match = re.search(r'[\d\.,]+', product_offerprice)
            if match:
                raw_price = match.group(0) 
                product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
                
            product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
            is_sale = 0
            
            if "PRP" not in product_fullprice:
                match = re.search(r'[\d\.,]+', product_fullprice)
                if match:
                    raw_price = match.group(0)
                    product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                    if specs["sealed"] == 1:
                        is_sale = 1
            else:
                product_fullprice = product_offerprice
                
            product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
            product_description = ""
            
            print(product_title)
            print(product_fullprice)
            print(product_offerprice)
            print(product_link)
            print("=========================")


            query_model = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ?"
            cursor.execute(query_model, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))
            model_result = cursor.fetchone()
            
            if model_result is None:
                query_insert_model = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                cursor.execute(query_insert_model, (specs['type'], product_title, specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture']))
                id_model = cursor.lastrowid
            else:
                id_model = model_result[0]


            cursor.execute("SELECT id_product FROM product WHERE link = ?", (product_link,))
            product_result = cursor.fetchone()

            if product_result is None:

                query_insert_product = "INSERT INTO product (id_model, link, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?)"
                cursor.execute(query_insert_product, (id_model, product_link, 'EMAG', 1, specs['sealed'], product_description))
                id_product = cursor.lastrowid
                

                cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                connection.commit()
                
                print("Produs nou inserat in baza de date.")
                asyncio.run(alert_new(product_title, product_offerprice, product_link, 'EMAG', product_fullprice))
            else:
                id_product = product_result[0]
                

                cursor.execute("UPDATE product SET last_seen = datetime('now', 'localtime'), active = 1 WHERE id_product = ?", (id_product,))
                

                cursor.execute("SELECT offer_price, full_price FROM price_history WHERE id_product = ? ORDER BY recorded_at DESC LIMIT 1", (id_product,))
                latest_price = cursor.fetchone()
                

                if latest_price is None or latest_price[0] != product_offerprice or latest_price[1] != product_fullprice:
                    cursor.execute("INSERT INTO price_history (id_product, full_price, offer_price, is_sale) VALUES (?, ?, ?, ?)", (id_product, product_fullprice, product_offerprice, is_sale))
                    print(f"Update pret gasit si inregistrat pentru: {product_title}")
                else:
                    print("Produsul exista, pretul nu s-a schimbat.")
                    
                connection.commit()

    except Exception as e:
        print("Error: Timeout waiting for EMAG product cards.", e)
    finally:
        driver.quit()

def get_emag_sealed():
    link = "https://www.emag.ro/laptopuri/brand/apple/filter/emag-genius-f9538,livrate-de-emag-v30/c?ref=lst_leftbar_9538_30"
    driver = get_driver()
    driver.get(link)
    wait = WebDriverWait(driver, timeout=30)

    while True:
        try:
            connection = sqlite3.connect('/data/macbooks.db')
            cursor = connection.cursor()

            wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "card-standard")))
            product_cards = driver.find_elements(By.CLASS_NAME, "card-standard")

            for product in product_cards:
                is_sale = 0
                active = 1
                product_title = product.find_element(By.CLASS_NAME, "card-v2-title").text
                specs = extract_macbook_specs(product_title)
                product_offerprice = product.find_element(By.CLASS_NAME, "product-new-price").text
                
                match = re.search(r'[\d\.,]+', product_offerprice)
                if match:
                    raw_price = match.group(0) 
                    product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
                
                product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
                if "PRP" not in product_fullprice:
                    match = re.search(r'[\d\.,]+', product_fullprice)
                    if match:
                        raw_price = match.group(0)
                        product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                        if specs["sealed"] == 1:
                            is_sale = 1
                else:
                    product_fullprice = product_offerprice
                
                try:
                    if product.find_element(By.CLASS_NAME, "text-availability-out_of_stock"):
                        active = 0
                except NoSuchElementException:
                    pass

                product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
                

                query_model = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ?"
                cursor.execute(query_model, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))
                model_result = cursor.fetchone()

                if model_result is None:
                    query_insert_model = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query_insert_model, (specs["type"], product_title, specs["size"], specs["cpu"], specs["cpu_cores"], specs["gpu_cores"], specs["ram"], specs["storage"], specs["color"], specs["nano_texture"]))
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

            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.js-change-page[aria-label='Next']")))
            next_page_btn = driver.find_element(By.CSS_SELECTOR, "a.js-change-page[aria-label='Next']")
            driver.execute_script("arguments[0].scrollIntoView();", next_page_btn)
            driver.execute_script("window.scrollBy(0, -150);")
            next_page_btn.click()
            WebDriverWait(driver, 10).until(EC.staleness_of(product_cards[0]))

        except (TimeoutException, NoSuchElementException):
            print("No more pages found")
            break
        finally:
            if connection:
                connection.close()
    
    driver.quit()

def checkDBlastSeen(cursor, connection, script_start_time):

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
        
        asyncio.run(alert_sold(title, offer_price, platform))
        cursor.execute("UPDATE product SET active = 0 WHERE id_product = ?", (id_product, ))
        
    connection.commit()


setupDatabase()

try:
    connection = sqlite3.connect('/data/macbooks.db')
    cursor = connection.cursor()

    cursor.execute("SELECT datetime('now', 'localtime')")
    script_start_time = cursor.fetchone()[0]

    emag_scraper(connection, cursor)
    checkDBlastSeen(cursor, connection, script_start_time)
    
except sqlite3.Error as error:
   print('Error occurred: ', error)
finally:
    if connection:
       connection.close()


if __name__ == "__main__":
    setupDatabase()
    

    while True:
        print("Starting scrape cycle...")
        try:
            connection = sqlite3.connect('//data/macbooks.db')
            cursor = connection.cursor()
            
            cursor.execute("SELECT datetime('now', 'localtime')")
            script_start_time = cursor.fetchone()[0]

            emag_scraper(connection, cursor)
            get_emag_sealed()
            checkDBlastSeen(cursor, connection, script_start_time)
            
        except Exception as e:
            print("Error during scrape:", e)
        finally:
            if connection:
                connection.close()
                
        print("Cycle complete. Sleeping for 2 hours...")
        time.sleep(7200)