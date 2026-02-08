from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import datetime
import sqlite3

with open("telegram_token.txt", "r") as f:
    telegram_token = f.readline()[:-1]
    chat_token = f.readline()

import asyncio
import telegram

async def alert_new(titlu, pret_oferta, link, platforma, pret_intreg="Necunoscut"):
    bot = telegram.Bot(telegram_token)
    async with bot:
        await bot.send_message(text=f"Mac nou pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}\n{link}", chat_id = chat_token)

async def alert_sold(titlu, pret_oferta, platforma, pret_intreg="Necunoscut"):
    bot = telegram.Bot(telegram_token)
    async with bot:
        await bot.send_message(text=f"Mac vandut pe {platforma}\n{titlu}\nPret intreg: {pret_intreg}\nPret oferta: {pret_oferta}", chat_id = chat_token)

total = 0

'''def checkDatabase(driver, cursor, platforma, connection, Macbooks):
    
    # definire variabile pentru fiecare platforma pentru cod curat
    # iStyle
    if platforma == "ISTYLE":
        by_object_titlu = By.CSS_SELECTOR
        id_titlu = "div.apl-section-product-title > h1:nth-child(1)"

        by_object_pret = By.CSS_SELECTOR
        id_pret = "#price-template--16719916499033__main > div:nth-child(2) > div:nth-child(1) > p:nth-child(1) > span:nth-child(1)"

    # eMag
    elif platforma == "EMAG":
        by_object_titlu = By.CLASS_NAME
        id_titlu = "card-v2-title"

        by_object_pret = By.CLASS_NAME
        id_pret = "product-new-price"

    # Altex
    elif platforma == "ALTEX":
        by_object_titlu = By.CLASS_NAME
        id_titlu = "Product-name"

        by_object_pret = By.CSS_SELECTOR
        id_pret = "li.Products-item > div:nth-child(1) > div:nth-child(5) > div:nth-child(1) > div:nth-child(2) > span:nth-child(2) > span:nth-child(1)"


    cursor.execute(f"SELECT titlu, pret_oferta, pret_nou FROM macbooks WHERE platforma = ?", (platforma,))
    db_results = cursor.fetchall()
    for db_macbook in db_results:
        ok = 0
        for Macbook in Macbooks:
            if db_macbook[0] == Macbook.find_element(by_object_titlu, id_titlu).text and db_macbook[1] == Macbook.find_element(by_object_pret, id_pret).text:
                print(db_macbook[0])
                print(Macbook.find_element(by_object_titlu, id_titlu).text)
                print("===================================================================")
                ok = 1
                break
        if ok == 0:
            cursor.execute(f"DELETE FROM macbooks WHERE platforma = ? AND titlu = ? AND pret_oferta = ?", (platforma, db_macbook[0], db_macbook[1],))
            connection.commit()
            asyncio.run(alert_sold(db_macbook[0],db_macbook[1], platforma, db_macbook[2]))
'''

def checkDBlastSeen (cursor, connection):
    cursor.execute("SELECT platforma, titlu, pret_oferta, pret_nou, last_seen FROM macbooks WHERE last_seen < datetime('now', '-2 hours')")
    results = cursor.fetchall()
    for result in results:
        asyncio.run(alert_sold(result[1],result[2], result[0], result[3]))
        cursor.execute("DELETE FROM MACBOOKS WHERE TITLU = ? AND PRET_OFERTA = ? AND PLATFORMA = ?", (result[1], result[2], result[0],))
    connection.commit()

def setupDatabase():
    connection = sqlite3.connect('macbooks.db')
    cursor = connection.cursor()


    cursor.execute('''
    CREATE TABLE IF NOT EXISTS macbooks (
        link TEXT PRIMARY KEY,
        titlu TEXT,
        pret_oferta TEXT,
        pret_nou TEXT,
        first_seen TEXT DEFAULT (datetime('now', 'localtime')),
        activ INTEGER DEFAULT 1,
        platforma TEXT,
        last_seen TEXT DEFAULT (datetime('now', 'localtime'))
    )
    ''')

    connection.commit()
    connection.close()

class scraper:
    def __init__ (self, platforma):
        self.platforma = platforma
    



setupDatabase()


try:

    connection = sqlite3.connect('macbooks.db')
    # ======================= EMAG ===============================
    link = "https://www.emag.ro/laptopuri/brand/apple/resigilate/c?ref=lst_leftbar_6407_resealed"
    driver = webdriver.Chrome()
    driver.get(link)
    driver.implicitly_wait(999)
    Macbooks = driver.find_elements(By.CLASS_NAME, "card-standard")
    for db_macbook in Macbooks:
        titlu_mac = db_macbook.find_element(By.CLASS_NAME, "card-v2-title").text
        fullprice_mac = db_macbook.find_element(By.CLASS_NAME, "pricing").text
        offerprice_mac = db_macbook.find_element(By.CLASS_NAME, "product-new-price").text
        link_mac = db_macbook.find_element(By.CLASS_NAME, "card-v2-thumb").get_attribute("href")
        print(titlu_mac)
        print(fullprice_mac)
        print(offerprice_mac)
        print(link_mac)
        print("=========================")
        cursor = connection.cursor()
        query = f"SELECT titlu FROM macbooks WHERE link = '{link_mac}'"
        cursor.execute(query)
        result = cursor.fetchone()
        if result is None:
            cursor.execute(f"SELECT pret_oferta FROM macbooks WHERE titlu = '{titlu_mac}'")
            results = cursor.fetchall()
            ok = 1
            for pret_oferta in results:
                if pret_oferta[0] == offerprice_mac:
                    ok = 0
                    break
                
            if ok == 1:
                asyncio.run(alert_new(titlu_mac, offerprice_mac, link_mac, "EMAG", fullprice_mac))
                query = f"INSERT INTO macbooks (link, titlu, pret_oferta, platforma, pret_nou) VALUES (?, ?, ?, 'EMAG', ?)"
                cursor.execute(query, (link_mac, titlu_mac, offerprice_mac, fullprice_mac,))
                connection.commit()
                print("Data inserted into table")
            else:
                print("Data already exists in table (checked against price)")
                cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")
        else:
            print("Data already exists in table")
            cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")



    #checkDatabase(driver, cursor, "EMAG", connection, Macbooks)        

    print(len(Macbooks))
    total += len(Macbooks)
    driver.quit()

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
                cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")
        else:
            print("Data already exists in table")
            cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")
    #checkDatabase(driver, cursor, "ALTEX", connection, Macbooks)     

    total += len(Macbooks)
    driver.quit()

    

    # ======================= ISTYLE ===============================

    link = "https://istyle.ro/collections/produse-resigilate?filter.p.product_type=Mac&filter.v.price.gte=&filter.v.price.lte=&sort_by=best-selling"
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
                cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")
        else:
            print("Data already exists in table")
            cursor.execute("UPDATE macbooks SET last_seen = (datetime('now','localtime'))")

    total += len(Macbooks)
    driver.quit()

    checkDBlastSeen(cursor, connection)

    print(total)
    cursor.execute("SELECT COUNT(*) FROM MACBOOKS")
    print(cursor.fetchall())
except sqlite3.Error as error:
   print('Error occurred: ', error)
finally:
    if connection:
       connection.close()

if connection:
    connection.close()


