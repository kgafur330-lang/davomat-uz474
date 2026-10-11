# Face ID Davomat Pro — MVP

Bu paket ko‘p kompyuterdan bitta markaziy serverga ulanadigan davomat tizimining boshlang‘ich versiyasidir. Birinchi talaba avtomatik kiritilgan:
- Student ID: `BMN17112`
- F.I.Sh.: `Qoriyev Abdugafur Rahimjon o‘g‘li`

## 1. Muhim cheklovlar
- Bu MVP: OpenCV Haar + LBPH ishlatiladi. U Apple Face ID bilan bir xil emas va 500+ talaba uchun yakuniy, yuqori xavfsizlikli biometrik tizim deb hisoblanmasligi kerak.
- Hozircha liveness/anti-spoofing (surat yoki video bilan aldashga qarshi) yo‘q. Universitetda haqiqiy foydalanishdan oldin kuchliroq yuz embedding modeli, liveness, HTTPS, zaxira nusxa, audit log va maxfiylik/rozilik jarayonini qo‘shish zarur.
- Barcha kompyuterlar bitta server manziliga ulanadi. Har bir kompyuterda alohida server ochmang, aks holda bazalar alohida bo‘lib qoladi.
- Birinchi administrator paroli `admin / ChangeMe123!`. Birinchi kirishda uni 12+ belgili parolga almashtiring.
- Biometrik suratlarni faqat tegishli rozilik va universitet qoidalariga muvofiq to‘plang. Serverni ochiq internetga himoyasiz chiqarmang.

## 2. Windows’da lokal sinov
1. Python 3.11 (64-bit) o‘rnating: https://www.python.org/downloads/
2. Ushbu papkani kompyuterga oching.
3. Papka ichida Command Prompt oching.
4. Buyruqlar:
   ```bat
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python app.py
   ```
5. Brauzerda `http://127.0.0.1:5000` oching.
6. Admin: `http://127.0.0.1:5000/login`; login `admin`, parol `ChangeMe123!`.
7. Parolni almashtiring, keyin admin panelida talaba suratlarini ro‘yxatdan o‘tkazing.

## 3. Birinchi talaba suratini ro‘yxatga olish
1. Admin panelida BMN17112 allaqachon mavjud.
2. “Yuz suratlarini ro‘yxatga olish” maydoniga `BMN17112` kiriting.
3. Talabaning rozilik bilan olingan kamida 3–5 ta aniq suratini tanlang. Turli yorug‘lik/burchaklardan, lekin bir vaqtda bitta yuz.
4. “Suratlarni saqlash va modelni yangilash” tugmasini bosing.
5. Bosh sahifada kamerani yoqib sinang.

## 4. Bitta serverga bir nechta kompyuter ulash
1. Markaziy Windows kompyuter/serverga loyihani o‘rnating.
2. Serverda `FACEID_SECRET` ni uzun tasodifiy qiymatga o‘rnating.
3. Tarmoq ichida sinash uchun Command Prompt’da:
   ```bat
   set HOST=0.0.0.0
   python app.py
   ```
4. Server IP manzilini aniqlang (`ipconfig`), masalan `192.168.1.20`.
5. Boshqa kompyuterlarda `http://192.168.1.20:5000` ochiladi. Windows Firewall’da faqat ishonchli mahalliy tarmoq uchun portga ruxsat bering.
6. Bu HTTP usuli faqat yopiq LAN sinovi uchun. Internet orqali ishlatishda HTTPS/TLS bilan reverse proxy va himoyalangan serverga joylashtiring. Kamera ruxsatlari HTTPS yoki localhost talab qilishi mumkin.

## 5. Excel
Admin panelidagi “Excel yuklab olish” tugmasi davomat yozuvlarini yagona `.xlsx` faylga eksport qiladi. Excel fayli har safar bazadagi joriy yozuvlardan yaratiladi; uni bir nechta kompyuterda qo‘lda bir vaqtda tahrirlash shart emas.

## 6. Windows EXE sinov build’i
Bu web serverni EXE ichida ishga tushirishning oddiy sinov usuli:
```bat
pip install pyinstaller
pyinstaller --onedir --name FaceIDDavomat --add-data "templates;templates" --add-data "static;static" app.py
```
`dist\FaceIDDavomat` ichidagi build’ni sinab ko‘ring. Ishlab chiqarish uchun bu buyruq yetarli bo‘lmasligi mumkin; OpenCV model fayllari, `faces` papkasi va doimiy `attendance.db` joylashuvi alohida sozlanishi kerak. Server va foydalanuvchi interfeysini ajratish tavsiya etiladi.

## 7. Ishlab chiqarishdan oldin zarur
- HTTPS, kuchli admin autentifikatsiyasi va rol/ruxsatlar
- SQLite o‘rniga PostgreSQL (ko‘p parallel foydalanuvchi uchun)
- liveness/anti-spoofing va yaxshiroq yuz modeli
- biometrik ma’lumotlar uchun rozilik, saqlash muddati va o‘chirish siyosati
- audit log, avtomatik backup/restore testi
- 500+ talaba bilan aniqlik, tezlik va noto‘g‘ri qabul/rad etish sinovlari
- tizimni haqiqiy talabalarda ishlatishdan oldin inson nazorati va alternativ davomat usuli


## Oson ishga tushirish (yangilangan paket)
1. `START_DAVOMAT.bat` faylini ikki marta bosing.
2. Birinchi ishga tushirishda kutubxonalar tekshiriladi/o‘rnatiladi.
3. CMD oynasini yopmang; sayt `http://127.0.0.1:5000` manzilida ochiladi.
4. Admin login: `admin`. Dastlabki parol: `ChangeMe123!`; kirgach darhol almashtiring.

`NameError: name 'json' is not defined` xatosi tuzatildi: `app.py` fayliga `json` importi qo‘shildi.
Eslatma: bu paket hozircha bir kompyuterda sinov uchun mo‘ljallangan. Boshqa kompyuterlardan umumiy foydalanish uchun serverni tarmoqqa xavfsiz joylashtirish va umumiy ma’lumotlar bazasini sozlash kerak.
