from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from telegram.request import HTTPXRequest
import datetime
import sqlite3

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


def emag_info_extraction(title):

    # title = 'Laptop Apple MacBook Pro 16" cu procesor Apple M4 Pro, 14 nuclee CPU si 20 nuclee GPU, 24GB RAM, 512GB SSD, Space Black, Textura Nano, Tastatura Internationala'

    i = title.find("MacBook ") + len("MacBook ")
    global type
    type = ""
    while title[i] != " ":
        type = type + title[i]
        i += 1
    #print(type)

    global size
    size = title[title.find('"') - 2] + title[title.find('"') - 1] 
    #print(size)

    global procesor
    procesor = title[title.find('cu procesor ') + len('cu procesor ') : title.find(',')]
    #print(procesor)

    global cpu_cores
    cpu_cores = ""
    if title.find(" nuclee CPU"):
        cpu_cores = title[title.find(" nuclee CPU") - 2] + title[title.find(" nuclee CPU") - 1]
    else:
        cpu_cores = "N/A"

    #print(cpu_cores)

    global gpu_cores
    if title.find(" nuclee GPU"):
        gpu_cores = title[title.find(" nuclee GPU") - 2] + title[title.find(" nuclee GPU") - 1]
        print(gpu_cores)
    else:
        gpu_cores = "N/A"


    global ram
    ram = title[title.find("GB RAM") - 2] + title[title.find("GB RAM") - 1]
    #print(ram)

    global storage
    storage = title[title.find("GB RAM, ")+len("GB RAM, ") : title.find("GB SSD")]
    #print(storage)


    i = title.find("GB SSD, ") + len("GB SSD, ")
    j = title[i:].find(",")
    global color
    color = title[i : i+j]
    #print(color)

    global textura_nano
    if title.find("Textura Nano") == 1:
        textura_nano = 1
    else:
        textura_nano = 0
    print(textura_nano)

    # last_seen = (datetime('now','localtime'))


def emag_scraper(wait, connection, link="https://www.emag.ro/laptopuri/brand/apple/resigilate/c?ref=lst_leftbar_6407_resealed"):
    # ======================= EMAG ===============================
    driver = webdriver.Chrome()
    driver.get(link)
    try:
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "card-standard")))

        product_cards = driver.find_elements(By.CLASS_NAME, "card-standard")

        for product in product_cards:
            title = product.find_element(By.CLASS_NAME, "card-v2-title").text
            offerprice = product.find_element(By.CLASS_NAME, "product-new-price").text
            product_fullprice = product.find_element(By.CLASS_NAME, "pricing").text
            product_link = product.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
            print(title)
            # print(product_fullprice)
            print(offerprice)
            print(product_link)
            print("=========================")

            
                    
    except:
        print("Error: Timeout waiting for EMAG product cards.") 
    finally:
        driver.quit()


    #checkDatabase(driver, cursor, "EMAG", connection, Macbooks)

total = 0



def checkDBlastSeen (cursor, connection):
    cursor.execute("SELECT platforma, titlu, pret_oferta, pret_nou, last_seen FROM macbooks WHERE last_seen < ?", (script_start_time, ))
    results = cursor.fetchall()
    for result in results:
        asyncio.run(alert_sold(result[1],result[2], result[0], result[3]))
        cursor.execute("DELETE FROM MACBOOKS WHERE TITLU = ? AND PRET_OFERTA = ? AND PLATFORMA = ?", (result[1], result[2], result[0],))
    connection.commit()

def setupDatabase():
    connection = sqlite3.connect('macbooks.db')
    cursor = connection.cursor()


    cursor.execute('''
    CREATE TABLE IF NOT EXISTS model (
        id_model INTEGER PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT NOT NULL, 
        inch NUMERIC NOT NULL,
        cpu TEXT NOT NULL,
        cpu_cores INTEGER NOT NULL,
        gpu_cores INTEGER NOT NULL,
        ram INTEGER NOT NULL,
        storage INTEGER NOT NULL,
        color TEXT NOT NULL,
        nano_texture INTEGER NOT NULL check(nano_texture = 0 or nano_texture = 1)
    );
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


