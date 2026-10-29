 # Telegram bot — existing student database
import time
import threading
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/" if TELEGRAM_TOKEN else ""

def telegram_send(chat_id, message):
    requests.post(
        TELEGRAM_API + "sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=15
    )

def telegram_bot_loop():
    offset = 0
    while True:
        try:
            data = requests.get(
                TELEGRAM_API + "getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35
            ).json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()

                if not chat_id or not text:
                    continue

                if text.startswith("/start"):
                    answer = "DAVOMAT.UZ474 botiga xush kelibsiz!\nStudent ID raqamingizni yuboring."
                elif text.startswith("/help"):
                    answer = "Student ID raqamingizni yuboring."
                else:
                    with db() as con:
                        student = con.execute(
                            "SELECT student_id, full_name FROM students WHERE student_id=? AND active=1",
                            (text.upper(),)
                        ).fetchone()

                    if student:
                        answer = (
                            f"Talaba topildi!\n"
                            f"F.I.Sh.: {student['full_name']}\n"
                            f"Student ID: {student['student_id']}"
                        )
                    else:
                        answer = "Bu ID faol talabalar bazasida topilmadi."

                telegram_send(chat_id, answer)

        except Exception:
            app.logger.exception("Telegram bot xatosi")
            time.sleep(5)

if (
    os.environ.get("RUN_TELEGRAM_BOT", "0") == "1"
    and TELEGRAM_TOKEN
):
    threading.Thread(
        target=telegram_bot_loop,
        daemon=True
    ).start()
