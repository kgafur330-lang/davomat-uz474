import os
import time
import sqlite3
import threading
import requests
from flask import Flask

app = Flask(__name__)

# Telegram sozlamalari
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/" if TELEGRAM_TOKEN else ""

# Database manzili
DB_PATH = os.environ.get(
    "FACEID_DB",
    os.path.join(os.environ.get("DATA_DIR", "/data"), "attendance.db")
)


@app.route("/")
def home():
    return "DAVOMAT.UZ474 ishlayapti!"


def telegram_send(chat_id, message):
    try:
        requests.post(
            TELEGRAM_API + "sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=15
        )
    except Exception as e:
        print("Telegram send error:", e)


def telegram_bot_loop():
    offset = 0

    while True:
        try:
            response = requests.get(
                TELEGRAM_API + "getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35
            )
            data = response.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                student_id = message.get("text", "").strip()

                if not chat_id or not student_id:
                    continue

                if student_id == "/start":
                    telegram_send(
                        chat_id,
                        "DAVOMAT.UZ474\nStudent ID raqamingizni yuboring."
                    )
                    continue

                try:
                    with sqlite3.connect(DB_PATH) as connection:
                        connection.row_factory = sqlite3.Row

                        student = connection.execute(
                            """
                            SELECT student_id, full_name
                            FROM students
                            WHERE student_id = ? AND active = 1
                            """,
                            (student_id.upper(),)
                        ).fetchone()

                    if student:
                        telegram_send(
                            chat_id,
                            "Talaba topildi!\n"
                            f"Ism: {student['full_name']}\n"
                            f"ID: {student['student_id']}"
                        )
                    else:
                        telegram_send(
                            chat_id,
                            "Bu ID bazada topilmadi. ID raqamingizni tekshiring."
                        )

                except Exception as e:
                    print("Database error:", e)
                    telegram_send(
                        chat_id,
                        "Bazaga ulanishda xato. Administratorga murojaat qiling."
                    )

        except Exception as e:
            print("Telegram bot error:", e)
            time.sleep(5)


if (
    TELEGRAM_TOKEN
    and os.environ.get("RUN_TELEGRAM_BOT") == "1"
):
    threading.Thread(
        target=telegram_bot_loop,
        daemon=True
    ).start()
