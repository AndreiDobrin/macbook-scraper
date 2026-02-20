from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from telegram.request import HTTPXRequest
import sqlite3
import re
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException



with open("telegram_token.txt", "r") as f:
    telegram_token = f.readline()[:-1]
    chat_token = f.readline()

import asyncio
import telegram

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
    # Normalize title: remove extra spaces to make regex easier
    clean_title = " ".join(title.split())
    
    specs = {
        "type": "N/A",
        "size": "N/A",
        "cpu": "N/A",
        "cpu_cores": "N/A",
        "gpu_cores": "N/A",
        "ram": "N/A",
        "storage": "N/A",
        "color": "N/A",
        "nano_texture": 0,
        "sealed": 1
    }

    # 0. EXTRACT SEALED STATUS
    if "RESIGILAT" in clean_title:
        specs["sealed"] = 0

    # 1. EXTRACT TYPE (Air vs Pro)
    if "MacBook Air" in clean_title:
        specs["type"] = "MacBook Air"
    elif "MacBook Pro" in clean_title:
        specs["type"] = "MacBook Pro"

    # 2. EXTRACT SCREEN SIZE 
    # Looks for number followed by " or -inch. 
    # Handles: 13", 15.3", 13-inch, 14.2"
    size_match = re.search(r'(\d+(\.\d+)?)(?="| -inch|-inch)', clean_title)
    if size_match:
        specs["size"] = float(size_match.group(1))

    # 3. EXTRACT CPU
    # Looks for "cu procesor" followed by the chip name until the next comma or keyword
    # Matches: "Apple M2", "Apple M3 Pro", "Apple M1 Max"
    cpu_match = re.search(r'cu procesor (Apple M\w+(?: Pro| Max| Ultra)?)', clean_title, re.IGNORECASE)
    if cpu_match:
        specs["cpu"] = cpu_match.group(1)

    # 4. EXTRACT CORES (CPU & GPU)
    # Looks for digits before "nuclee CPU" or "nuclee GPU"
    cpu_cores_match = re.search(r'(\d+)\s*nuclee CPU', clean_title)
    if cpu_cores_match:
        specs["cpu_cores"] = int(cpu_cores_match.group(1))

    gpu_cores_match = re.search(r'(\d+)\s*nuclee GPU', clean_title)
    if gpu_cores_match:
        specs["gpu_cores"] = int(gpu_cores_match.group(1))

    # 5. EXTRACT RAM
    # Looks for digits followed by GB.
    # To avoid confusion with storage, we assume RAM is the FIRST "GB" occurrence 
    # OR we look for "GB" that is explicitly NOT followed by "SSD" if possible, 
    # but eMAG titles are messy. 
    # Strategy: Find all "X GB" patterns. RAM is usually the smaller one (8, 16, 24, 32, etc) compared to storage (256, 512).
    # OR: RAM is usually listed before storage.
    
    # Let's find all size patterns (GB or TB)
    # matches tuples like [('24', 'GB'), ('1', 'TB')]
    memory_matches = re.findall(r'(\d+)\s*(GB|TB)', clean_title)
    
    found_ram = False
    found_storage = False

    for amount, unit in memory_matches:
        amount = int(amount)
        
        # Logic: If it's TB, it's definitely storage
        if unit == "TB":
            # Convert TB to GB for standardization, or keep as string "1TB"
            # Let's keep the user's format preference
            specs["storage"] = amount * 1024
            found_storage = True
            
        # If it's GB
        elif unit == "GB":
            # Heuristic: RAM is usually <= 128GB. Storage is usually >= 256GB.
            # Edge case: 128GB Storage exists on old models, but rare on M-series.
            # Edge case: 96GB RAM exists.
            
            # If we haven't found RAM yet, and this looks like a RAM amount, take it.
            if not found_ram and amount in [8, 16, 18, 24, 32, 36, 48, 64, 96, 128]:
                 # Check if the word "SSD" follows immediately. If so, it's storage.
                 # (We need a stricter check for this)
                 if f"{amount} {unit} SSD" in clean_title or f"{amount}{unit} SSD" in clean_title:
                     specs["storage"] = amount
                     found_storage = True
                 else:
                     specs["ram"] = amount
                     found_ram = True
            
            # If we already have RAM, or this is a large number (256, 512), it's storage
            elif amount >= 256:
                specs["storage"] = amount
                found_storage = True
                
            # If we have RAM, and we find another small number (e.g. 8GB RAM, 128GB SSD), update storage
            elif found_ram and not found_storage:
                 specs["storage"] = amount
                 found_storage = True

    # 6. EXTRACT COLOR
    # Searching by comma position is dangerous. It's better to search for known colors.
    known_colors = [
        "Silver", "Space Grey", "Space Gray", "Midnight", 
        "Starlight", "Space Black", "Sky Blue", "Gold", "Rose Gold"
    ]
    
    for color in known_colors:
        if color.lower() in clean_title.lower():
            specs["color"] = color
            break
            
    # Fallback for color: If not found, try the comma logic (between storage and keyboard)
    if specs["color"] == "N/A":
        try:
            # Attempt to grab text between the last spec (Storage) and "Tastatura" or end
            # This is a bit advanced, skipping for now as the list above covers 99% of Macs.
            pass
        except:
            pass

    # 7. NANO TEXTURE
    # Check for "Textura Nano" or "Nano-texture"
    if "Textura Nano" in clean_title or "Nano-texture" in clean_title:
        specs["nano_texture"] = 1
    else:
        specs["nano_texture"] = 0

    return specs


def emag_scraper(connection, cursor, link="https://www.emag.ro/laptopuri/brand/apple/resigilate/c?ref=lst_leftbar_6407_resealed"):
    # ======================= EMAG ===============================
    driver = webdriver.Chrome()
    driver.get(link)
    wait = WebDriverWait(driver, timeout=30)
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "card-standard")))

        product_cards = driver.find_elements(By.CLASS_NAME, "card-standard")

        for product in product_cards:
            product_title = product.find_element(By.CLASS_NAME, "card-v2-title").text
            product_offerprice = product.find_element(By.CLASS_NAME, "product-new-price").text
            specs = extract_macbook_specs(product_title)
            # 1. Use Regex to find the number pattern (digits, dots, commas)
            match = re.search(r'[\d\.,]+', product_offerprice)
            if match:
                raw_price = match.group(0)  # "11.699,99"

                # 2. Convert to a standard float for SQLite
                # Remove the thousands dot (11.699 -> 11699)
                # Replace the decimal comma (11699,99 -> 11699.99)
                product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
            product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
            if "PRP" not in product_fullprice:
                match = re.search(r'[\d\.,]+', product_fullprice)
                if match:
                    raw_price = match.group(0)
                    product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                    if specs["sealed"] == 1:
                        sale = 1
            else:
                product_fullprice = product_offerprice
            product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
            product_description = ""
            print(product_title)
            print(product_fullprice)
            print(product_offerprice)
            print(product_link)
            print("=========================")

            query = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ?"
            cursor.execute(query, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))

            results = cursor.fetchall()
            if len(results) == 0:
                    query = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (specs['type'], product_title, specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))
                    query = "INSERT INTO product (id_model, link, offer_price, full_price, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (cursor.lastrowid, product_link, product_offerprice, product_fullprice, 'EMAG', 1, 0, product_description))
                    connection.commit()
                    print("Produs inserat in MODEL si PRODUCT")
                    asyncio.run(alert_new(product_title, product_offerprice, product_link, 'EMAG'))
            else:
                query = "SELECT * FROM product WHERE id_model = ? AND offer_price = ?"
                cursor.execute(query, (results[0][0], product_offerprice, ))
                connection.commit()
                if cursor.fetchone() is None:
                    query = ("INSERT INTO product (id_model, link, offer_price, full_price, platform, active, sealed, description)"
                             " VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
                    cursor.execute(query, (results[0][0], product_link, product_offerprice, product_fullprice, 'EMAG', 1, 0, product_description))
                    connection.commit()
                    print("Produs inserat in PRODUCT")
                    asyncio.run(alert_new(product_title, product_offerprice, product_link, 'EMAG'))
                else:
                    print("Produsul deja exista")
                    query = ("UPDATE product "
                             "SET last_seen = datetime('now', 'localtime') "
                             "WHERE id_model = ? AND offer_price = ?")
                    cursor.execute(query, (results[0][0], product_offerprice, ))
                    connection.commit()
    except Exception as e:
        print("Error: Timeout waiting for EMAG product cards.")
        print(e) 
    finally:
        driver.quit()


    #checkDatabase(driver, cursor, "EMAG", connection, Macbooks)

def get_emag_sealed():
    link = "https://www.emag.ro/laptopuri/brand/apple/filter/emag-genius-f9538,livrate-de-emag-v30/c?ref=lst_leftbar_9538_30"

    driver = webdriver.Chrome()
    driver.get(link)
    wait = WebDriverWait(driver, timeout=30)

    page_number = 1
    while True:
        
        try:
            connection = sqlite3.connect('macbooks.db')
            cursor = connection.cursor()

            wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "card-standard")))
            product_cards = driver.find_elements(By.CLASS_NAME, "card-standard")

            for product in product_cards:
                sale = 0
                active = 1
                product_title = product.find_element(By.CLASS_NAME, "card-v2-title").text
                specs = extract_macbook_specs(product_title)
                product_offerprice = product.find_element(By.CLASS_NAME, "product-new-price").text
                # 1. Use Regex to find the number pattern (digits, dots, commas)
                match = re.search(r'[\d\.,]+', product_offerprice)
                if match:
                    raw_price = match.group(0)  # "11.699,99"
                    # 2. Convert to a standard float for SQLite
                    # Remove the thousands dot (11.699 -> 11699)
                    # Replace the decimal comma (11699,99 -> 11699.99)
                    product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
                product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
                if "PRP" not in product_fullprice:
                    match = re.search(r'[\d\.,]+', product_fullprice)
                    if match:
                        raw_price = match.group(0)
                        product_fullprice = float(raw_price.replace('.', '').replace(',','.'))
                        if specs["sealed"] == 1:
                            sale = 1
                else:
                    product_fullprice = product_offerprice
                
                try:
                    if product.find_element(By.CLASS_NAME, "text-availability-out_of_stock"):
                        print(product.find_element(By.CLASS_NAME, "text-availability-out_of_stock").text)
                        active = 0
                except NoSuchElementException:
                    pass

                product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
                product_description = ""
                print(product_title)
                print(product_fullprice)
                print(product_offerprice)
                print("sale:", sale)
                print("sealed:", specs["sealed"])
                print(product_link)

                print("=========================\n")

                query = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ?"
                cursor.execute(query, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))
                result = cursor.fetchone()

                if result is None:
                    query = "INSERT INTO MODEL (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (specs["type"], product_title, specs["size"], specs["cpu"], specs["cpu_cores"], specs["gpu_cores"], specs["ram"], specs["storage"], specs["color"], specs["nano_texture"], ))
                    query = "INSERT INTO PRODUCT (id_model, link, full_price, offer_price, platform, active, sealed, sale) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (cursor.lastrowid, product_link, product_fullprice, product_offerprice, "EMAG", active, 1, sale))
                    connection.commit()
                else:
                    query = "SELECT full_price, sale, offer_price, active from product where id_model = ? and platform = ?"
                    cursor.execute(query, (result[0], "EMAG"))
                    product_result = cursor.fetchone()
                    if product_result[0] != product_fullprice or product_result[1] != sale or product_result[2] != product_offerprice or product_result[3] != active:
                        query = "UPDATE product " \
                                "SET full_price = ?, sale = ?, offer_price = ?, active = ? " \
                                "WHERE id_model = ? and sealed = 1"
                        cursor.execute(query, (product_fullprice, sale, product_offerprice, active, result[0]))
                        connection.commit()
                    else:
                        print("Data is up-to-date")

            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.js-change-page[aria-label='Next']")))
            next_page_btn = driver.find_element(By.CSS_SELECTOR, "a.js-change-page[aria-label='Next']")
            driver.execute_script("arguments[0].scrollIntoView();", next_page_btn)
            driver.execute_script("window.scrollBy(0, -150);")
            next_page_btn.click()
            page_number += 1
            #time.sleep(10)
            WebDriverWait(driver, 10).until(EC.staleness_of(product_cards[0]))
        except (TimeoutException, NoSuchElementException):
            print("No more pages found")
            driver.quit()
            connection.close()
            break
        finally:
            connection.close()


total = 0



def checkDBlastSeen (cursor, connection):
    cursor.execute("SELECT p.platform, m.title, p.offer_price, p.last_seen, p.id_model FROM product p JOIN model m ON p.id_model = m.id_model WHERE p.last_seen < ? AND sealed = 0 AND active = 1", (script_start_time, ))
    results = cursor.fetchall()
    for result in results:
        asyncio.run(alert_sold(result[1],result[2], result[0]))
        cursor.execute("UPDATE product SET active = 0 WHERE id_model = ? AND offer_price = ?", (result[4], result[2], ))
    connection.commit()

def setupDatabase():
    connection = sqlite3.connect('macbooks.db')
    cursor = connection.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS model (
        id_model INTEGER PRIMARY KEY,
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
        id_product INTEGER PRIMARY KEY,
        id_model INTEGER NOT NULL,
        link TEXT NOT NULL,
        price NUMERIC,
        last_seen TEXT DEFAULT (datetime('now', 'localtime')),
        platform TEXT,
        active INTEGER check(active = 0 or active = 1),
        sealed INTEGER check(sealed = 0 or sealed = 1),
        sale NUMERIC,
        description TEXT,

        FOREIGN KEY (id_model) REFERENCES model(id_model)
    )
    ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS price_history (
    id_history INTEGER PRIMARY KEY AUTOINCREMENT,
    id_product INTEGER NOT NULL,
    full_price NUMERIC,      -- The base price / PRP at that moment
    offer_price NUMERIC NOT NULL, -- The actual selling price at that moment
    is_sale INTEGER CHECK(is_sale = 0 OR is_sale = 1), -- 1 if there was an active promotion
    recorded_at TEXT DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (id_product) REFERENCES product(id_product)
    )
    ''')

    connection.commit()
    connection.close()

setupDatabase()
try:
    connection = sqlite3.connect('macbooks.db')
    cursor = connection.cursor()

    cursor.execute("SELECT datetime('now', 'localtime')")
    script_start_time = cursor.fetchone()[0]


    emag_scraper(connection, cursor)
    checkDBlastSeen(cursor, connection)
    '''
    # ======================= ALTEX ===============================

    link = "https://altex.ro/resigilate/laptopuri/cpl/filtru/brand-3334/apple/"

    driver = webdriver.Chrome()
    driver.get(link)
    driver.implicitly_wait(999)
    Macbooks = driver.find_elements(By.CLASS_NAME, "Product")
    for db_macbook in Macbooks:
        titlu_mac = db_macbook.find_element(By.CLASS_NAME, "Product-name").text
        fullprice_mac = db_macbook.find_element(By.CSS_SELECTOR, "li.Products-item > div:nth-child(1) > div:nth-child(5) > div:nth-child(1) > div:nth-child(1) > span:nth-child(2)").text
        offerprice_mac = db_macbook.find_element(By.CSS_SELECTOR, "li.Products-item > div:nth-child(1) > div:nth-child(5) > div:nth-child(1) > div:nth-child(2) > span:nth-child(2) > span:nth-child(1)").text
        link_mac = db_macbook.find_element(By.CSS_SELECTOR, "li.Products-item > div:nth-child(1) > a:nth-child(2)").get_attribute("href")
        print(titlu_mac)
        print(f"NOU {fullprice_mac} Lei")
        print(f"de la {offerprice_mac} Lei")
        print(link_mac)
        print("=========================")

        query = f"SELECT titlu FROM macbooks WHERE link = ?"
        cursor.execute(query, (link_mac,))

        result = cursor.fetchone()

        if result is None:
            cursor.execute(f"SELECT pret_oferta FROM macbooks WHERE titlu = ?", (titlu_mac,))
            results = cursor.fetchall()
            ok = 1
            for pret_oferta in results:
                if pret_oferta[0] == offerprice_mac:
                    ok = 0
                    break
            
            if ok == 1:
                asyncio.run(alert_new(titlu_mac, offerprice_mac, link_mac, "ALTEX", fullprice_mac))
                query = f"INSERT INTO macbooks (link, titlu, pret_oferta, platforma, pret_nou) VALUES (?, ?, ?, 'ALTEX', ?)"
                cursor.execute(query, (link_mac, titlu_mac, offerprice_mac, fullprice_mac))
                connection.commit()
                print("Data inserted into table")
            else:
                print("Data already exists in table (checked against price)")
                cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime')) WHERE titlu = ? and pret_oferta = ?", (titlu_mac, offerprice_mac,))
        else:
            print("Data already exists in table")
            cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime')) WHERE titlu = ? and pret_oferta = ?", (titlu_mac, offerprice_mac,))
    #checkDatabase(driver, cursor, "ALTEX", connection, Macbooks)     

    total += len(Macbooks)
    driver.quit()

  

    # ======================= ISTYLE ===============================

    link = "https://istyle.ro/collections/produse-resigilate?filter.p.product_type=Mac+Resigilat&filter.v.price.gte=&filter.v.price.lte=&sort_by=best-selling"
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, timeout=100)
    driver.get(link)
    driver.implicitly_wait(999)
    Macbooks = driver.find_elements(By.CLASS_NAME, "card1")
    mac_links = []
    for db_macbook in Macbooks:
        #titlu_mac = db_macbook.find_element(By.CSS_SELECTOR, ".card1 > div:nth-child(2) > div:nth-child(2) > h3:nth-child(1) > a:nth-child(1)").text
        #offerprice_mac = db_macbook.find_element(By.CLASS_NAME, "price-item").text
        mac_links.append(db_macbook.find_element(By.CLASS_NAME, "full-unstyled-link").get_attribute("href"))

    for link_mac in mac_links:
        driver.get(link_mac)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.apl-section-product-title > h1:nth-child(1)")))
        titlu_mac = driver.find_element(By.CSS_SELECTOR, "div.apl-section-product-title > h1:nth-child(1)").text
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#price-template--16719916499033__main > div:nth-child(2) > div:nth-child(1) > p:nth-child(1) > span:nth-child(1)")))
        offerprice_mac = driver.find_element(By.CSS_SELECTOR, "#price-template--16719916499033__main > div:nth-child(2) > div:nth-child(1) > p:nth-child(1) > span:nth-child(1)").text#get_attribute("data-price")
        print(titlu_mac)
        print(offerprice_mac)
        print(link_mac)
        print("=========================")

        query = f"SELECT titlu FROM macbooks WHERE link = ?"
        cursor.execute(query, (link_mac,))

        result = cursor.fetchone()

        if result is None:
            cursor.execute(f"SELECT pret_oferta FROM macbooks WHERE titlu = ?", (titlu_mac,))
            results = cursor.fetchall()
            ok = 1
            for pret_oferta in results:
                if pret_oferta[0] == offerprice_mac:
                    ok = 0
                    break
            
            if ok == 1:
                asyncio.run(alert_new(titlu_mac, offerprice_mac, link_mac, "ISTYLE"))
                query = f"INSERT INTO macbooks (link, titlu, pret_oferta, platforma) VALUES (?, ?, ?, 'ISTYLE')"
                cursor.execute(query, (link_mac, titlu_mac, offerprice_mac,))
                connection.commit()
                print("Data inserted into table")
            else:
                print("Data already exists in table (checked against price)")
                cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime')) WHERE titlu = ? and pret_oferta = ?", (titlu_mac, offerprice_mac,))
        else:
            print("Data already exists in table")
            cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime')) WHERE titlu = ? and pret_oferta = ?", (titlu_mac, offerprice_mac,))

    total += len(Macbooks)
    driver.quit()

    checkDBlastSeen(cursor, connection)

    print(total)
    cursor.execute("SELECT COUNT(*) FROM MACBOOKS")
    print(cursor.fetchall())
    '''
except sqlite3.Error as error:
   print('Error occurred: ', error)
finally:
    if connection:
       connection.close()

get_emag_sealed()


if connection:
    connection.close()


