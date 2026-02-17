from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from telegram.request import HTTPXRequest
import datetime
import sqlite3
import re


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
        "nano_texture": 0
    }

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

'''
def emag_info_extraction(title):


    i = title.find("MacBook ") + len("MacBook ")
    global product_type
    product_type = ""
    while title[i] != " ":
        product_type = product_type + title[i]
        i += 1
    print("product_type:", product_type)

    global product_size
    product_size = title[title.find('"') - 2] + title[title.find('"') - 1] 
    print("product_size:", product_size)

    global product_cpu
    product_cpu = title[title.find('cu procesor ') + len('cu procesor ') : title.find(',', title.find('cu procesor ') + len('cu procesor '))]
    print("product_cpu:", product_cpu)

    global product_cpu_cores
    product_cpu_cores = ""
    if title.find(" nuclee CPU"):
        for i in reversed(title[:title.find(" nuclee CPU")]):
            if i.isdigit() == False:
                break
            product_cpu_cores = i + product_cpu_cores
        print("product_cpu_cores:", product_cpu_cores)
    else:
        product_cpu_cores = "N/A"

    global product_gpu_cores
    product_gpu_cores = ""
    if title.find(" nuclee GPU"):
        for i in reversed(title[:title.find(" nuclee GPU")]):
            if i.isdigit() == False:
                break
            product_gpu_cores = i + product_gpu_cores
        print("product_gpu_cores:", product_gpu_cores)
    else:
        product_gpu_cores = "N/A"


    global product_ram
    product_ram = ""
    for i in reversed(title[:title.find("GB")]):
        if i.isdigit() == False:
            break
        product_ram = i + product_ram

    print("product_ram:", product_ram)
        

    global product_storage
    product_storage = ""
    for i in reversed(title[title.find("GB")+len("GB") : title.find("GB", title.find("GB")+len("GB"))]):
        if i.isdigit() == False:
            break
        product_storage = i + product_storage
    print("product_storage:", product_storage)


    i = title.find("GB SSD, ") + len("GB SSD, ")
    j = title[i:].find(",")
    x = title[title.find(",", title.find("GB")) + 1 :]
    y = title[title.find(",", title.find(",", title.find("GB")) + 1):]
    z = title[title.find(",", title.find(",", title.find("GB")) + 1) + 2 : title.find(",", title.find(",", title.find(",", title.find("GB")) + 1) + 2)]
    global product_color
    product_color = title[title.find(",", title.find(",", title.find("GB")) + 1) + 2 : title.find(",", title.find(",", title.find(",", title.find("GB")) + 1) + 2)]
    print("product_color:", product_color)

    global product_nano_texture
    if title.find("Textura Nano") == 1:
        product_nano_texture = 1
    else:
        product_nano_texture = 0
    print("product_nano_texture:", product_nano_texture)

    # last_seen = (datetime('now','localtime'))
'''

#title = 'RESIGILAT: Laptop Apple MacBook Air 13", cu procesor Apple M4, 10 nuclee CPU si 10 nuclee GPU, 16GB RAM, 512GB, Starlight, Tastatura Internationala, Manual RO'
#title = 'RESIGILAT: Laptop Apple MacBook Air 13", cu procesor Apple M3, 8 nuclee CPU si 8 nuclee GPU, 8GB, 256GB, Silver, INT KB'

#emag_info_extraction(title)

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

            # 1. Use Regex to find the number pattern (digits, dots, commas)
            match = re.search(r'[\d\.,]+', product_offerprice)

            if match:
                raw_price = match.group(0)  # "11.699,99"

                # 2. Convert to a standard float for SQLite
                # Remove the thousands dot (11.699 -> 11699)
                # Replace the decimal comma (11699,99 -> 11699.99)
                product_offerprice = float(raw_price.replace('.', '').replace(',', '.'))
            product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
            product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
            product_description = ""
            print(product_title)
            # print(product_fullprice)
            print(product_offerprice)
            print(product_link)
            print("=========================")

            specs = extract_macbook_specs(product_title)

            query = "SELECT id_model FROM model WHERE type = ? AND size = ? AND cpu = ? AND cpu_cores = ? AND gpu_cores = ? AND ram = ? AND storage = ? AND color = ? AND nano_texture = ?"
            cursor.execute(query, (specs['type'], specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))

            results = cursor.fetchall()
            if len(results) == 0:
                    query = "INSERT INTO model (type, title, size, cpu, cpu_cores, gpu_cores, ram, storage, color, nano_texture) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (specs['type'], product_title, specs['size'], specs['cpu'], specs['cpu_cores'], specs['gpu_cores'], specs['ram'], specs['storage'], specs['color'], specs['nano_texture'], ))
                    query = "INSERT INTO product (id_model, link, price, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (cursor.lastrowid, product_link, product_offerprice, 'EMAG', 1, 0, product_description))
                    connection.commit()
                    print("Produs inserat in MODEL si PRODUCT")
                    asyncio.run(alert_new(product_title, product_offerprice, product_link, 'EMAG'))
            else:
                query = "SELECT * FROM product WHERE id_model = ? AND price = ?"
                cursor.execute(query, (results[0][0], product_offerprice, ))
                connection.commit()
                if cursor.fetchone() is None:
                    query = "INSERT INTO product (id_model, link, price, platform, active, sealed, description) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (results[0][0], product_link, product_offerprice, 'EMAG', 1, 0, product_description))
                    connection.commit()
                    print("Produs inserat in PRODUCT")
                    asyncio.run(alert_new(product_title, product_offerprice, product_link, 'EMAG'))
                else:
                    print("Produsul deja exista")
                    query = "UPDATE product SET last_seen = datetime('now', 'localtime') WHERE id_model = ? AND price = ?"
                    cursor.execute(query, (results[0][0], product_offerprice, ))
                    connection.commit()
    except Exception as e:
        print("Error: Timeout waiting for EMAG product cards.")
        print(e) 
    finally:
        driver.quit()


    #checkDatabase(driver, cursor, "EMAG", connection, Macbooks)

total = 0



def checkDBlastSeen (cursor, connection):
    cursor.execute("SELECT p.platform, m.title, p.price, p.last_seen, p.id_model FROM product p JOIN model m ON p.id_model = m.id_model WHERE p.last_seen < ?", (script_start_time, ))
    results = cursor.fetchall()
    for result in results:
        asyncio.run(alert_sold(result[1],result[2], result[0]))
        cursor.execute("DELETE FROM product WHERE id_model = ? AND price = ?", (result[4], result[2], ))
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
        price NUMERIC NOT NULL,
        last_seen TEXT DEFAULT (datetime('now', 'localtime')),
        platform TEXT,
        active INTEGER check(active = 0 or active = 1),
        sealed INTEGER check(sealed = 0 or sealed = 1),
        sale NUMERIC,
        description TEXT,

        FOREIGN KEY (id_model) REFERENCES model(id_model)
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

if connection:
    connection.close()


