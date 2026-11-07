import os, io, csv, sqlite3, secrets, json, urllib.request, urllib.parse
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# Set DAVOMAT_DATA_DIR=/var/data on a persistent hosting disk.
DATA_DIR = os.environ.get("DAVOMAT_DATA_DIR", os.path.join(APP_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.environ.get("FACEID_DB", os.path.join(DATA_DIR, "attendance.db"))
MODEL_PATH = os.path.join(DATA_DIR, "face_model.yml")
LABELS_PATH = os.path.join(DATA_DIR, "face_labels.json")
FACES_DIR = os.path.join(DATA_DIR, "faces")
os.makedirs(FACES_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("FACEID_SECRET", "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET")
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

# Haar cascade is bundled with OpenCV. LBPH recognizer comes from opencv-contrib-python.
CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
FACE_SIZE = (200, 200)
MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "65")) # lower = stricter

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS students(
            student_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL, attendance_time TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'Face ID', status TEXT NOT NULL DEFAULT 'Keldi',
            FOREIGN KEY(student_id) REFERENCES students(student_id),
            UNIQUE(student_id, attendance_date))""")
        con.execute("""CREATE TABLE IF NOT EXISTS admins(
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS lesson_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, course_name TEXT NOT NULL,
            group_name TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL,
            ended_at TEXT, status TEXT NOT NULL DEFAULT 'active')""")
        con.execute("""CREATE TABLE IF NOT EXISTS lesson_attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
            student_id TEXT NOT NULL, attendance_time TEXT NOT NULL,
            UNIQUE(session_id, student_id),
            FOREIGN KEY(session_id) REFERENCES lesson_sessions(id),
            FOREIGN KEY(student_id) REFERENCES students(student_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS telegram_links(
            student_id TEXT PRIMARY KEY, chat_id TEXT UNIQUE NOT NULL,
            linked_at TEXT NOT NULL, FOREIGN KEY(student_id) REFERENCES students(student_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS telegram_link_codes(
            code TEXT PRIMARY KEY, student_id TEXT NOT NULL, expires_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id))""")
        # Two requested administrator accounts. Passwords are stored as hashes.
        admin_accounts = [
            ("admin1", os.environ.get("ADMIN1_PASSWORD", "Qwerty777")),
            ("admin2", os.environ.get("ADMIN2_PASSWORD", "Qwerty474")),
        ]
        for username, password in admin_accounts:
            con.execute(
                "INSERT INTO admins(username,password_hash) VALUES(?,?) "
                "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash",
                (username, generate_password_hash(password))
            )
        # Keep exactly the two requested administrator accounts.
        con.execute("DELETE FROM admins WHERE username NOT IN ('admin1','admin2')")

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def read_image(file_bytes):
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Rasmni oâqib boâlmadi.")
    return img

def face_crop(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80,80))
    if len(faces) != 1:
        raise ValueError("Rasmda aynan bitta yuz koârinishi kerak. Yuzni markazga olib, yorugâlikni yaxshilang.")
    x,y,w,h = faces[0]
    crop = gray[y:y+h, x:x+w]
    crop = cv2.equalizeHist(crop)
    return cv2.resize(crop, FACE_SIZE)

def load_labels():
    if os.path.exists(LABELS_PATH):
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def train_model():
    samples, ids, labels = [], [], {}
    with db() as con:
        students = con.execute("SELECT student_id,full_name FROM students WHERE active=1").fetchall()
    label_num = 0
    for s in students:
        folder = os.path.join(FACES_DIR, s["student_id"])
        if not os.path.isdir(folder): continue
        images = [x for x in os.listdir(folder) if x.lower().endswith((".jpg",".jpeg",".png",".webp"))]
        if not images: continue
        labels[str(label_num)] = {"student_id": s["student_id"], "full_name": s["full_name"]}
        for name in images:
            try:
                with open(os.path.join(folder,name),"rb") as f: crop = face_crop(read_image(f.read()))
                samples.append(crop); ids.append(label_num)
            except Exception:
                continue
        label_num += 1
    if not samples:
        if os.path.exists(MODEL_PATH): os.remove(MODEL_PATH)
        with open(LABELS_PATH,"w",encoding="utf-8") as f: json.dump({},f,ensure_ascii=False)
        return 0
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(samples, np.array(ids, dtype=np.int32))
    recognizer.save(MODEL_PATH)
    with open(LABELS_PATH,"w",encoding="utf-8") as f: json.dump(labels,f,ensure_ascii=False)
    return len(samples)

def record_attendance(student_id):
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    # When a lesson is open, attendance is recorded per lesson, not merely once per day.
    with db() as con:
        active = con.execute("SELECT id,course_name FROM lesson_sessions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
        if active:
            try:
                con.execute("INSERT INTO lesson_attendance(session_id,student_id,attendance_time) VALUES(?,?,?)",
                            (active["id"], student_id, stamp))
            except sqlite3.IntegrityError:
                return False, f"Bu talaba ushbu darsda allaqachon qayd etilgan: {active['course_name']}"
            # Keep the legacy daily summary/export compatible; multiple lessons per day are stored separately above.
            con.execute("INSERT OR IGNORE INTO attendance(student_id,attendance_date,attendance_time,method,status) VALUES(?,?,?,?,?)",
                        (student_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "Face ID", "Keldi"))
            return True, f"Davomat qayd etildi: {active['course_name']} Â· {stamp}"
        try:
            con.execute("INSERT INTO attendance(student_id,attendance_date,attendance_time,method,status) VALUES(?,?,?,?,?)",
                        (student_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "Face ID", "Keldi"))
            return True, f"Kunlik davomat qayd etildi: {stamp}. Eslatma: hozir faol dars ochilmagan."
        except sqlite3.IntegrityError:
            return False, "Bu talaba bugun kunlik davomatdan oâtgan. Fan boâyicha hisob uchun admin darsni ochishi kerak."

def telegram_api(method, payload):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN sozlanmagan")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))

def telegram_send(chat_id, text):
    return telegram_api("sendMessage", {"chat_id": str(chat_id), "text": text})

def telegram_report(student_id):
    with db() as con:
        student = con.execute("SELECT * FROM students WHERE student_id=? AND active=1", (student_id,)).fetchone()
        if not student:
            return "Talaba topilmadi yoki faol emas. Admin bilan bogâlaning."
        total = con.execute("SELECT COUNT(*) n FROM lesson_sessions WHERE status='completed'").fetchone()["n"]
        attended = con.execute("SELECT COUNT(*) n FROM lesson_attendance la JOIN lesson_sessions ls ON ls.id=la.session_id WHERE la.student_id=? AND ls.status='completed'", (student_id,)).fetchone()["n"]
        rows = con.execute("""SELECT ls.course_name, COUNT(*) total,
            SUM(CASE WHEN la.student_id IS NOT NULL THEN 1 ELSE 0 END) attended
            FROM lesson_sessions ls LEFT JOIN lesson_attendance la ON la.session_id=ls.id AND la.student_id=?
            WHERE ls.status='completed' GROUP BY ls.course_name ORDER BY ls.course_name""", (student_id,)).fetchall()
    missed = max(0, total-attended)
    pct = (attended/total*100) if total else 0
    lines = [f"DAVOMAT.UZ474 â shaxsiy hisobot", f"Talaba: {student['full_name']}", f"ID: {student_id}", "",
             f"Yakunlangan darslar: {total}", f"Qatnashgan: {attended}", f"Qoldirgan: {missed}", f"Qatnashish: {pct:.1f}%", ""]
    if rows:
        lines.append("Fanlar boâyicha:")
        for r in rows:
            m = int(r["total"])-int(r["attended"] or 0)
            lines.append(f"â¢ {r['course_name']}: {int(r['attended'] or 0)}/{int(r['total'])} qatnashgan, {m} qoldirgan")
    else:
        lines.append("Hozircha yakunlangan darslar yoâq.")
    lines += ["", "Hisobot faqat admin ochib, yakunlagan darslar asosida hisoblanadi."]
    return "\n".join(lines)

def handle_telegram_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message or not message.get("chat") or not message.get("text"):
        return
    chat_id = str(message["chat"]["id"])
    text = message["text"].strip()
    parts = text.split()
    cmd = parts[0].split("@")[0].lower() if parts else ""
    if cmd in ("/start", "/help"):
        telegram_send(chat_id, "DAVOMAT.UZ474 botiga xush kelibsiz.\nHisobingizni bogâlash: /link KOD\nDavomat hisoboti: /report\nKODni universitet administratori beradi.")
    elif cmd == "/link":
        if len(parts) != 2:
            telegram_send(chat_id, "Foydalanish: /link KOD. KODni admin panelidan oling.")
            return
        code = parts[1].upper()
        now = datetime.now().isoformat(timespec="seconds")
        with db() as con:
            row = con.execute("SELECT student_id,expires_at FROM telegram_link_codes WHERE code=?", (code,)).fetchone()
            if not row or row["expires_at"] < now:
                telegram_send(chat_id, "Kod notoâgâri yoki muddati tugagan. Admin panelidan yangi kod oling.")
                return
            try:
                con.execute("INSERT INTO telegram_links(student_id,chat_id,linked_at) VALUES(?,?,?) ON CONFLICT(student_id) DO UPDATE SET chat_id=excluded.chat_id,linked_at=excluded.linked_at", (row["student_id"], chat_id, now))
                con.execute("DELETE FROM telegram_link_codes WHERE code=?", (code,))
            except sqlite3.IntegrityError:
                telegram_send(chat_id, "Bu Telegram akkaunti boshqa talaba bilan bogâlangan. Admin bilan bogâlaning.")
                return
        telegram_send(chat_id, "Akkaunt muvaffaqiyatli bogâlandi! Hisobot uchun /report yuboring.")
    elif cmd == "/report":
        with db() as con:
            row = con.execute("SELECT student_id FROM telegram_links WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            telegram_send(chat_id, "Avval akkauntingizni bogâlang: /link KOD. KODni admin beradi.")
        else:
            telegram_send(chat_id, telegram_report(row["student_id"]))
    else:
        # Plain Student ID: validate against the shared DB and record attendance.
        student_id = text.strip().upper()
        if len(student_id) > 40 or not student_id.replace("-", "").replace("_", "").isalnum():
            telegram_send(chat_id, "Student ID yuboring yoki /link KOD va /report buyruqlaridan foydalaning.")
            return
        with db() as con:
            student = con.execute(
                "SELECT student_id, full_name FROM students WHERE student_id=? AND active=1",
                (student_id,)
            ).fetchone()
        if not student:
            telegram_send(chat_id, "Bu Student ID bazadan topilmadi. ID raqamingizni tekshiring.")
            return
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with db() as con:
                active = con.execute(
                    "SELECT id, course_name FROM lesson_sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if active:
                    con.execute(
                        "INSERT INTO lesson_attendance(session_id,student_id,attendance_time) VALUES(?,?,?)",
                        (active["id"], student["student_id"], stamp)
                    )
                    con.execute(
                        "INSERT OR IGNORE INTO attendance(student_id,attendance_date,attendance_time,method,status) VALUES(?,?,?,?,?)",
                        (student["student_id"], now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "Telegram", "Keldi")
                    )
                    reply = f"â Davomat qayd etildi!\\nTalaba: {student['full_name']}\\nID: {student['student_id']}\\nDars: {active['course_name']}\\nVaqt: {stamp}"
                else:
                    con.execute(
                        "INSERT INTO attendance(student_id,attendance_date,attendance_time,method,status) VALUES(?,?,?,?,?)",
                        (student["student_id"], now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "Telegram", "Keldi")
                    )
                    reply = f"â Davomat qayd etildi!\\nTalaba: {student['full_name']}\\nID: {student['student_id']}\\nSana-vaqt: {stamp}"
            telegram_send(chat_id, reply)
        except sqlite3.IntegrityError:
            telegram_send(chat_id, f"â¹ï¸ {student['full_name']} â bugungi davomat oldin qayd etilgan.")

@app.route("/")
def index():
    with db() as con:
        total = con.execute("SELECT COUNT(*) n FROM students WHERE active=1").fetchone()["n"]
        today = con.execute("SELECT COUNT(*) n FROM attendance WHERE attendance_date=?", (datetime.now().strftime("%Y-%m-%d"),)).fetchone()["n"]
        latest = con.execute("""SELECT a.student_id,s.full_name,a.attendance_date,a.attendance_time,a.status
            FROM attendance a JOIN students s USING(student_id) ORDER BY a.id DESC LIMIT 12""").fetchall()
    return render_template("index.html", total=total, today=today, latest=latest)

@app.route("/checkin", methods=["POST"])
def checkin():
    if not request.files.get("frame"):
        return jsonify(ok=False, message="Kamera tasviri kelmadi."), 400
    if not os.path.exists(MODEL_PATH):
        return jsonify(ok=False, message="Hozircha yuz namunasi roâyxatga olinmagan. Administrator avval talabani roâyxatdan oâtkazsin."), 400
    try:
        img = read_image(request.files["frame"].read())
        crop = face_crop(img)
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(MODEL_PATH)
        label_num, confidence = recognizer.predict(crop)
        labels = load_labels()
        person = labels.get(str(label_num))
        if person is None or confidence > MATCH_THRESHOLD:
            return jsonify(ok=False, message=f"Yuz mos kelmadi (score {confidence:.1f}). Qayta urinib koâring."), 401
        ok, message = record_attendance(person["student_id"])
        return jsonify(ok=ok, message=message, student_id=person["student_id"], name=person["full_name"], score=round(float(confidence),1))
    except ValueError as e:
        return jsonify(ok=False, message=str(e)), 400
    except Exception as e:
        app.logger.exception("checkin error")
        return jsonify(ok=False, message="Tekshiruvda xatolik. Administratorga murojaat qiling."), 500

@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        return jsonify(ok=False), 403
    update = request.get_json(silent=True) or {}
    try:
        handle_telegram_update(update)
    except Exception:
        app.logger.exception("Telegram webhook error")
    return jsonify(ok=True)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        with db() as con:
            admin = con.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin"] = username
            return redirect(url_for("admin"))
        flash("Login yoki parol xato.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin", methods=["GET","POST"])
@login_required
def admin():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            sid = request.form.get("student_id","").strip().upper()
            name = request.form.get("full_name","").strip()
            if not sid or not name:
                flash("Student ID va ism-familiya kiritilishi shart.", "error")
            else:
                try:
                    with db() as con:
                        con.execute("INSERT INTO students(student_id,full_name,active,created_at) VALUES(?,?,1,?)",
                                    (sid,name,datetime.now().isoformat(timespec="seconds")))
                    flash("Talaba qoâshildi. Endi kamida 3 ta sifatli yuz suratini yuklang.", "success")
                except sqlite3.IntegrityError:
                    flash("Bu Student ID oldin qoâshilgan.", "error")
        elif action == "enroll":
            sid = request.form.get("student_id","").strip().upper()
            with db() as con:
                student = con.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
            if not student:
                flash("Talaba topilmadi.", "error")
            else:
                uploads = request.files.getlist("photos")
                folder = os.path.join(FACES_DIR,sid)
                os.makedirs(folder,exist_ok=True)
                saved=0
                for i,up in enumerate(uploads):
                    if not up or not up.filename: continue
                    try:
                        crop = face_crop(read_image(up.read()))
                        out = os.path.join(folder, f"enroll_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{i}.png")
                        cv2.imwrite(out,crop); saved+=1
                    except Exception as e:
                        flash(f"{up.filename}: {e}", "error")
                if saved:
                    count=train_model()
                    flash(f"{saved} ta surat qabul qilindi. Model qayta oâqitildi ({count} ta surat).", "success")
        elif action == "retrain":
            count=train_model()
            flash(f"Model qayta oâqitildi. Foydalanilgan suratlar: {count}.", "success")
        elif action == "start_lesson":
            course = request.form.get("course_name", "").strip()[:120]
            group = request.form.get("group_name", "").strip()[:80]
            if not course:
                flash("Fan/dars nomini kiriting.", "error")
            else:
                with db() as con:
                    active = con.execute("SELECT id FROM lesson_sessions WHERE status='active' LIMIT 1").fetchone()
                    if active:
                        flash("Avval ochiq darsni yakunlang.", "error")
                    else:
                        con.execute("INSERT INTO lesson_sessions(course_name,group_name,started_at,status) VALUES(?,?,?,'active')",
                                    (course, group, datetime.now().isoformat(timespec="seconds")))
                        flash(f"Dars boshlandi: {course}. Endi kamera orqali kelganlar shu darsga yoziladi.", "success")
        elif action == "end_lesson":
            with db() as con:
                active = con.execute("SELECT id,course_name FROM lesson_sessions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
                if active:
                    con.execute("UPDATE lesson_sessions SET status='completed',ended_at=? WHERE id=?",
                                (datetime.now().isoformat(timespec="seconds"), active["id"]))
                    flash(f"Dars yakunlandi: {active['course_name']}. Endi bot hisobotiga kiradi.", "success")
                else:
                    flash("Yakunlash uchun ochiq dars yoâq.", "error")
        elif action == "telegram_code":
            sid = request.form.get("student_id", "").strip().upper()
            with db() as con:
                student = con.execute("SELECT student_id,full_name FROM students WHERE student_id=? AND active=1", (sid,)).fetchone()
                if not student:
                    flash("Talaba ID topilmadi.", "error")
                else:
                    code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
                    expires = (datetime.now()+timedelta(minutes=30)).isoformat(timespec="seconds")
                    con.execute("DELETE FROM telegram_link_codes WHERE student_id=?", (sid,))
                    con.execute("INSERT INTO telegram_link_codes(code,student_id,expires_at) VALUES(?,?,?)", (code,sid,expires))
                    flash(f"{student['full_name']} uchun bir martalik kod: {code} (30 daqiqa amal qiladi). Talaba botga /link {code} yuborsin.", "success")
        elif action == "telegram_setup":
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
            base_url = os.environ.get("APP_PUBLIC_URL", "").strip().rstrip("/")
            if not token or not secret or not base_url.startswith("https://"):
                flash("Telegram sozlamalari yetishmaydi: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET va HTTPS APP_PUBLIC_URL kerak.", "error")
            else:
                try:
                    result = telegram_api("setWebhook", {"url": base_url+url_for("telegram_webhook"), "secret_token": secret})
                    flash("Telegram webhook sozlandi." if result.get("ok") else "Telegram webhook sozlanmadi: API xabari tekshirilsin.", "success" if result.get("ok") else "error")
                except Exception:
                    app.logger.exception("Telegram webhook setup failed")
                    flash("Telegram webhookni sozlab boâlmadi. Token va Render environment sozlamalarini tekshiring.", "error")
        elif action == "password":
            old=request.form.get("old_password",""); new=request.form.get("new_password","")
            with db() as con:
                adminrow=con.execute("SELECT * FROM admins WHERE username=?",(session["admin"],)).fetchone()
                if adminrow and check_password_hash(adminrow["password_hash"],old) and len(new)>=12:
                    con.execute("UPDATE admins SET password_hash=? WHERE username=?",(generate_password_hash(new),session["admin"]))
                    flash("Parol yangilandi.","success")
                else: flash("Eski parol xato yoki yangi parol kamida 12 belgidan iborat boâlishi kerak.","error")
        return redirect(url_for("admin"))
    with db() as con:
        students=con.execute("SELECT s.*, (SELECT COUNT(*) FROM attendance a WHERE a.student_id=s.student_id) attendance_count FROM students s ORDER BY s.full_name").fetchall()
        active_lesson=con.execute("SELECT * FROM lesson_sessions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
        lesson_history=con.execute("SELECT ls.*, (SELECT COUNT(*) FROM lesson_attendance la WHERE la.session_id=ls.id) present_count FROM lesson_sessions ls ORDER BY ls.id DESC LIMIT 10").fetchall()
    return render_template("admin.html", students=students, active_lesson=active_lesson, lesson_history=lesson_history, telegram_configured=bool(os.environ.get("TELEGRAM_BOT_TOKEN")))

@app.route("/export.xlsx")
@login_required
def export_xlsx():
    start=request.args.get("start","").strip(); end=request.args.get("end","").strip()
    query="""SELECT a.student_id,s.full_name,a.attendance_date,a.attendance_time,a.method,a.status
             FROM attendance a JOIN students s USING(student_id) WHERE 1=1"""
    args=[]
    if start: query+=" AND a.attendance_date>=?"; args.append(start)
    if end: query+=" AND a.attendance_date<=?"; args.append(end)
    query+=" ORDER BY a.attendance_date DESC,a.attendance_time DESC"
    with db() as con: rows=con.execute(query,args).fetchall()
    wb=Workbook(); ws=wb.active; ws.title="Davomat"
    ws.append(["Student ID","Talaba F.I.Sh.","Sana","Vaqt","Usul","Holat"])
    for r in rows: ws.append([r["student_id"],r["full_name"],r["attendance_date"],r["attendance_time"],r["method"],r["status"]])
    for c in ws[1]:
        c.font=Font(bold=True,color="FFFFFF"); c.fill=PatternFill("solid",fgColor="1746A2"); c.alignment=Alignment(horizontal="center")
    for i,w in enumerate([18,38,16,14,16,16],1): ws.column_dimensions[get_column_letter(i)].width=w
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    output=io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, as_attachment=True, download_name="FaceID_Davomat.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/health")
def health():
    return jsonify(status="ok", database=os.path.basename(DB_PATH))

# Initialize on import too, so production WSGI servers (Gunicorn) are ready.
init_db()

if __name__ == "__main__":
    print("DAVOMAT.UZ474: http://127.0.0.1:5000")
    print("Admin accounts: admin1 and admin2 (see README_UZ.md)")
    app.run(host=os.environ.get("HOST","127.0.0.1"), port=int(os.environ.get("PORT","5000")), debug=False)
