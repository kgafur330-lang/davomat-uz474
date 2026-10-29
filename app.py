import os, io, csv, sqlite3, secrets, json
from datetime import datetime
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
        count = con.execute("SELECT COUNT(*) n FROM admins").fetchone()["n"]
        if not count:
            # Hosting should define INITIAL_ADMIN_PASSWORD as a secret environment variable.
            initial_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "ChangeMe123!")
            initial_username = os.environ.get("INITIAL_ADMIN_USERNAME", "admin")
            con.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",
                        (initial_username, generate_password_hash(initial_password)))

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
        raise ValueError("Rasmni o‘qib bo‘lmadi.")
    return img

def face_crop(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80,80))
    if len(faces) != 1:
        raise ValueError("Rasmda aynan bitta yuz ko‘rinishi kerak. Yuzni markazga olib, yorug‘likni yaxshilang.")
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
