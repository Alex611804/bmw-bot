import os, time, json, sqlite3, logging, threading
from flask import Flask
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

TELEGRAM_TOKEN = "8546184456:AAEgIWFMh8BFqr5fwO9V6FMxc316vrXNDkk"
CHAT_ID = "525261793"
CHECK_INTERVAL = 300

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

app = Flask(__name__)

@app.route('/')
def home():
    return "BMW Bot is running!"

conn = sqlite3.connect("seen_cars.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS sent_ads (ad_id TEXT PRIMARY KEY)")
conn.commit()

def is_already_sent(ad_id):
    cursor.execute("SELECT 1 FROM sent_ads WHERE ad_id = ?", (ad_id,))
    return cursor.fetchone() is not None

def mark_as_sent(ad_id):
    cursor.execute("INSERT INTO sent_ads (ad_id) VALUES (?)", (ad_id,))
    conn.commit()

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Telegram error: {e}")

def check_otomoto():
    found = 0
    for page in range(1, 5):
        url = f"https://www.otomoto.pl/osobowe/bmw/seria-7/od-1988-do-2001?page={page}"
        try:
            res = cffi_requests.get(url, impersonate="chrome120", timeout=15)
            if res.status_code != 200:
                break

            soup = BeautifulSoup(res.text, "html.parser")
            tag = soup.find("script", id="__NEXT_DATA__")
            if not tag:
                break

            data = json.loads(tag.string)
            results = data.get("props", {}).get("pageProps", {}).get("urState", {}).get("advertisements", {}).get("edges", [])

            for item in results:
                node = item.get("node", {})
                ad_id = f"oto_{node.get('id')}"

                year = None
                for p in node.get("params", []):
                    if p.get("key") == "year":
                        try:
                            year = int(p.get("value"))
                        except:
                            pass
                        break

                if not year or year < 1988 or year > 2001:
                    continue

                if not is_already_sent(ad_id):
                    title = node.get("title", "BMW Seria 7")
                    clean_url = node.get("url")
                    price = node.get("price", {}).get("displayValue", "")

                    msg = f"🔥 **BMW 7 (E32/E38) Otomoto!**\n\n📌 **{title}**\n💰 **Цена:** {price}\n🗓 **Год:** {year}\n\n🔗 {clean_url}"
                    send_telegram(msg)
                    mark_as_sent(ad_id)
                    found += 1
                    time.sleep(0.4)

        except Exception as e:
            logging.error(f"Otomoto error: {e}")
            break

    if found > 0:
        logging.info(f"Otomoto: отправлено {found} объявлений E32/E38")

def check_olx():
    url = "https://www.olx.pl/motoryzacja/samochody/bmw/7/?search%5Bfilter_float_year%3Afrom%5D=1988&search%5Bfilter_float_year%3Ato%5D=2001"
    try:
        res = cffi_requests.get(url, impersonate="chrome120", timeout=15)
        if res.status_code != 200:
            return

        soup = BeautifulSoup(res.text, "html.parser")
        tag = soup.find("script", id="prerendered-state")
        found = 0

        if tag:
            state = json.loads(tag.string)
            ads = state.get("ad", {}).get("ad", {})
            for ad_key, ad_info in ads.items():
                if isinstance(ad_info, dict):
                    ad_id = f"olx_{ad_info.get('id')}"
                    title = ad_info.get("title", "")
                    
                    year = None
                    for p in ad_info.get("params", []):
                        if p.get("key") == "year":
                            try:
                                year = int(p.get("value"))
                            except:
                                pass

                    if year and (year < 1988 or year > 2001):
                        continue

                    if not is_already_sent(ad_id):
                        full_url = ad_info.get("url")
                        msg = f"🚘 **BMW 7 (E32/E38) OLX!**\n\n📌 **{title}**\n🗓 **Год:** {year or '1988-2001'}\n\n🔗 {full_url}"
                        send_telegram(msg)
                        mark_as_sent(ad_id)
                        found += 1
                        time.sleep(0.4)

        if found > 0:
            logging.info(f"OLX: отправлено {found} объявлений E32/E38")
    except Exception as e:
        logging.error(f"OLX error: {e}")

def bot_loop():
    logging.info("Бот запущен на Render...")
    while True:
        check_otomoto()
        check_olx()
        time.sleep(CHECK_INTERVAL)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
