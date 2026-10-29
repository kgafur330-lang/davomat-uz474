import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}/"

@app.route("/")
def home():
    return "DAVOMAT.UZ474 ishlayapti!"

def bot():
    offset = 0
    while True:
        try:
            updates = requests.get(
                API + "getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35
            ).json()

            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message", {})
                chat = m.get("chat", {}).get("id")
                text = m.get("text", "").strip()

                if not chat:
                    continue

                if text == "/start":
                    answer = (
                        "DAVOMAT.UZ474 botiga xush kelibsiz!\n\n"
                        "Student ID raqamingizni yuboring."
                    )
                elif text == "/help":
                    answer = "Botni boshlash uchun /start bosing."
                else:
                    answer = (
                        f"ID qabul qilindi: {text}\n\n"
                        "ID bazadan tekshirish funksiyasi "
                        "hali ulanmagan."
                    )

                requests.post(
                    API + "sendMessage",
                    data={"chat_id": chat, "text": answer},
                    timeout=15
                )
        except Exception as e:
            print("Bot xatosi:", e)
            time.sleep(5)

if TOKEN and os.getenv("RUN_TELEGRAM_BOT") == "1":
    threading.Thread(target=bot, daemon=True).start()
