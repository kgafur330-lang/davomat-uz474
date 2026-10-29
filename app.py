# ===== DAVOMAT.UZ474 TELEGRAM BOT =====
import os
import threading
import requests
import time

def start_telegram_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN topilmadi")
        return

    api = f"https://api.telegram.org/bot{token}"
    offset = 0

    while True:
        try:
            updates = requests.get(
                api + "/getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35
            ).json()

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip()

                if not chat_id:
                    continue

                if text == "/start":
                    answer = (
                        "DAVOMAT.UZ474 botiga xush kelibsiz!\n\n"
                        "Student ID raqamingizni yuboring."
                    )
                elif text == "/help":
                    answer = "/start — botni boshlash\n"
                else:
                    answer = (
                        "ID qabul qilindi: " + text +
                        "\n\nTalaba ma’lumotlarini tekshirish "
                        "uchun universitet bazasi bilan ulanish kerak."
                    )

                requests.post(
                    api + "/sendMessage",
                    data={"chat_id": chat_id, "text": answer},
                    timeout=15
                )

        except Exception as e:
            print("Telegram bot xatosi:", e)
            time.sleep(5)

if os.getenv("RUN_TELEGRAM_BOT") == "1":
    threading.Thread(target=start_telegram_bot, daemon=True).start()
# ===== BOT KODI TUGADI =====
