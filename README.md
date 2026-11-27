# BandQil v1 — baza va server

Sartaroshxona va go'zallik salonlari uchun onlayn navbat tizimi (1-bosqich: baza + server).

## Ishga tushirish (Windows, VS Code terminal)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python test_core.py
python seed.py
uvicorn main:app --reload
```

1. `.env` faylini ochib, `ADMIN_TOKEN=` ga uzun tasodifiy matn yozing.
2. `python test_core.py` — "HAMMA TESTLAR O'TDI" chiqishi kerak.
3. `python seed.py` — namunaviy 2 tuman, 3 salon, 3 usta qo'shadi.
4. `uvicorn main:app --reload` dan keyin brauzerda http://127.0.0.1:8000/docs ni oching.
   U yerda har bir so'rovni tugma bosib sinab ko'rish mumkin.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `config.py` | Sozlamalar (.env dan o'qiydi) |
| `db.py` | Baza jadvallari |
| `services.py` | Asosiy mantiq: bo'sh vaqt, bron, reyting, admin |
| `main.py` | Server (API manzillari) |
| `notify.py` | Adminga Telegram xabari |
| `seed.py` | Namunaviy ma'lumot |
| `test_core.py` | Mantiq testlari |

## Muhim qoidalar

- **Ikki marta bron yo'q:** tekshiruv va yozish bitta tranzaksiyada (`BEGIN IMMEDIATE`).
- **Abonent:** salon yoki ustaning `paid_until` sanasi o'tib ketsa, u ko'rinmaydi va bron olmaydi.
  To'lovni uzaytirish: `POST /api/admin/paid-until`.
- **Reyting:** faqat `done` holatidagi bronga, bitta bronga bitta baho (1–5).
- **Yaqin atrofda:** `GET /api/nearby?district_id=1&date=2026-11-16&duration_min=30` — shu tumandagi
  bo'sh vaqtlar, manzillar va reytinglar.
- **Admin API:** hamma `/api/admin/...` so'rovlarida `X-Admin-Token: <ADMIN_TOKEN>` sarlavhasi kerak.
  (`/docs` sahifasida Authorize emas, har so'rovda sarlavha qo'shish kerak bo'ladi; keyingi bosqichda
  Telegram ID orqali tekshiruv qo'shamiz.)

## Xizmatlarni o'zingiz boshqarish (admin orqali)

Go'zallik saloni va sartaroshxonaning xizmatlari boshqacha bo'lishi kerak (masalan, ayollar uchun
soch, manikyur, pedikyur, depilyatsiya — "soch + soqol" emas). Buni `/docs` sahifasi orqali o'zingiz
tuzatasiz:

1. Brauzerda `http://127.0.0.1:8000/docs` ni oching.
2. Kerakli so'rovni toping (pastda), **Try it out** bosing, tagida chiqqan **X-Admin-Token**
   maydoniga `.env` dagi `ADMIN_TOKEN` qiymatini yozing, so'ng kerakli ma'lumotni kiritib
   **Execute** bosing.

| Nima qilmoqchisiz | So'rov |
|---|---|
| Ustaning xizmatlarini (yashirilganlari ham) ko'rish, `id` larini bilish uchun | `GET /api/admin/masters/{master_id}/services` |
| Noto'g'ri xizmatni mijozdan yashirish (o'chirmaydi, eski bronlar saqlanadi) | `POST /api/admin/services/{service_id}/active` — `is_active: false` |
| Xizmat nomi/narxi/davomiyligini tuzatish | `PATCH /api/admin/services/{service_id}` — faqat o'zgartirmoqchi bo'lgan maydonni yuboring |
| Yangi xizmat qo'shish (masalan, Manikyur) | `POST /api/admin/services` — `master_id`, `name`, `duration_min`, `price` |
| Xizmatni butunlay o'chirish (unga hali bron qilinmagan bo'lsa) | `DELETE /api/admin/services/{service_id}` |
| Salon/ustaning `id` sini bilish uchun | `GET /api/admin/salons` va `GET /api/admin/salons/{salon_id}/masters` |

Masalan, go'zallik salonidagi ustaning avvalgi "Soch + soqol" xizmatini yashirib, o'rniga
Manikyur/Pedikyur/Depilyatsiya qo'shish uchun: avval shu usta `id`sini `GET /salons/{id}/masters`
dan oling, keyin noto'g'ri xizmatni `.../active` bilan yashiring, so'ng `POST /services` bilan
yangilarini qo'shing. Yangi o'rnatishda (`seed.py`) endi go'zallik saloniga shu uchtasi avtomatik
qo'yiladi — faqat mavjud bazadagi eski yozuvlarni tuzatish kerak.

## Mijoz sahifalari (2-bosqich)

`static/` papkasida: tuman/salon ro'yxati, usta va xizmat, sana/vaqt, bron, "yaqin atrofda bo'sh
joylar" (band vaqtga urinilsa avtomatik chiqadi) va "Bronlarim" (bekor qilish, baho berish).
`uvicorn main:app --reload` ishga tushgach, http://127.0.0.1:8000/ da ochiladi (Telegram'siz,
oddiy brauzerda ham ishlaydi — Telegram ichida ochilganda mijozning Telegram ID'si avtomatik
olinadi, brauzerda esqa shu qurilma uchun vaqtinchalik ID saqlanadi).

## Keyingi bosqichlar

3. Usta paneli (jadval, "tugatish" / "kelmadi") va admin sahifasi (hozircha faqat /docs orqali)
4. Telegram bot: @BotFather'da bot ochish, Mini App tugmasini ulash, admin xabarlarini yoqish
5. Internetga chiqarish (domen, HTTPS)


## Ma'lumotlar yo'qolmasligi uchun (muhim)
Baza (`bandqil.db`) va yuklangan rasmlar (`uploads/`) oddiy fayl. Render/Railway/Heroku kabi
hostinglarda har yangi deploydan keyin papka tozalanadi — salonlar ham shu bilan o'chib ketadi.
Doimiy disk (volume) ulab, `.env`/o'zgaruvchilarga shuni yozing: `BANDQIL_DB=/data/bandqil.db`
(rasmlar avtomatik `/data/uploads` ga tushadi). `bandqil.db` ni GitHub'ga yuklamang (`.gitignore`).
