import os
import time
import sqlite3
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB = os.getenv("FACEID_DB", "data/attendance.db")
API = f"https://api.telegram.org/bot{TOKEN}/"

def send(chat_id, text):
    requests.post(API + "sendMessage",
                  data={"chat_id": chat_id, "text": text},
                  timeout=15)

def main():
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

                if not chat or not text:
                    continue

                if text == "/start":
                    send(chat, "DAVOMAT.UZ474\nStudent ID raqamingizni yuboring.")
                    continue

                try:
                    with sqlite3.connect(DB) as con:
                        con.row_factory = sqlite3.Row
                        student = con.execute(
                            "SELECT student_id, full_name FROM students "
                            "WHERE student_id=? AND active=1",
                            (text.upper(),)
                        ).fetchone()

                    if student:
                        send(chat, f"Talaba topildi!\nIsm: {student['full_name']}\nID: {student['student_id']}")
                    else:
                        send(chat, "Bu ID bazada topilmadi. ID raqamingizni tekshiring.")
                except Exception:
                    send(chat, "Bazaga ulanishda xato. Administratorga murojaat qiling.")

        except Exception as e:
            print("Xato:", e)
            time.sleep(5)

if __name__ == "__main__":
    if TOKEN:
        main()
    else:
        print("TELEGRAM_BOT_TOKEN sozlanmagan!")
