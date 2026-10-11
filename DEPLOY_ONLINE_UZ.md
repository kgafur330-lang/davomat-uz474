# DAVOMAT.UZ474 — internetga joylashtirish

## Muhim
- `render.yaml` Render Blueprint orqali pullik `starter` web service va 1 GB doimiy disk so'raydi. Bu kerak, chunki yuz suratlari, model va SQLite davomat bazasi restart/deploydan keyin saqlanishi kerak.
- Bepul Render instansiyasida mahalliy fayllar yo'qolishi mumkin; haqiqiy davomat uchun bepul tarifni ishlatmang.
- Bu dastur yuz suratlarini va davomat ma'lumotlarini qayta ishlaydi. Faqat vakolatli foydalanuvchilarni kiriting, rozilik va universitet qoidalarini tekshiring, muntazam zaxira nusxa oling.

## Joylashtirish
1. GitHub'da `davomat-uz474` nomli **Private** repository yarating.
2. Ushbu papkaning ichidagi fayllarni repository'ga yuklang. `attendance.db`, `data/`, `faces/`, `.env` va haqiqiy yuz suratlarini GitHub'ga yuklamang.
3. Render hisobiga kiring: https://dashboard.render.com/
4. `New` → `Blueprint` ni tanlang va GitHub repository'ni ulang.
5. `INITIAL_ADMIN_PASSWORD` so'ralganda kuchli, yangi parol kiriting. Uni chatda yoki kod ichida yozmang.
6. Blueprint'da `Apply` / deploy qiling. Deploy tugagach Render `.onrender.com` manzil beradi.
7. `https://SIZNING-SAYTINGIZ.onrender.com/health` ochib `{"status":"ok"...}` chiqishini tekshiring.
8. Saytga `admin` va siz kiritgan boshlang'ich parol bilan kiring, keyin admin parolini sayt ichida almashtiring.

## Cheklov
GitHub va Render akkauntlariga kirish/ulash foydalanuvchi tomonidan tasdiqlanishi kerak. Bu fayllar deployment'ni tayyorlaydi, lekin hisobga kirmasdan yoki billingni tasdiqlamasdan saytni o'z-o'zidan internetga chiqara olmaydi.
