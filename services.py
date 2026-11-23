"""BandQil asosiy mantiqi: bo'sh vaqt, bron, reyting, admin amallari."""
import hashlib
import math
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import config
from db import connect

DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%d %H:%M"
KINDS = ("barbershop", "beauty")

# Usta ko'rinadigan bo'lishi uchun: usta va salon faol, va salon yoki ustaning abonenti amalda.
VISIBLE = (
    "m.is_active = 1 AND s.is_active = 1 AND "
    "(COALESCE(s.paid_until, '') >= :today OR COALESCE(m.paid_until, '') >= :today)"
)
# Xizmat ham faol bo'lishi kerak (usta/salon bilan birga tekshiriladigan joylarda)
VISIBLE_SVC = VISIBLE + " AND sv.is_active = 1"


class BookingError(Exception):
    """code: invalid | forbidden | not_found | slot_taken"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------- yordamchilar ----------

def now() -> datetime:
    return datetime.now()


def today_str() -> str:
    return now().strftime(DATE_FMT)


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def immediate(conn):
    """Yozish tranzaksiyasi. BEGIN IMMEDIATE boshqa yozuvchilarni kutdiradi,
    shuning uchun ikki kishi bir vaqtda bir joyni ola olmaydi."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _check_date(date_str):
    try:
        d = datetime.strptime(date_str, DATE_FMT).date()
    except (TypeError, ValueError):
        raise BookingError("invalid", "Sana noto'g'ri. Format: YYYY-MM-DD")
    today = now().date()
    if d < today or d > today + timedelta(days=config.MAX_DAYS_AHEAD):
        raise BookingError(
            "invalid", f"Sana bugundan boshlab {config.MAX_DAYS_AHEAD} kun ichida bo'lishi kerak"
        )
    return d


def _check_hhmm(value, field):
    try:
        datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        raise BookingError("invalid", f"{field} noto'g'ri. Format: HH:MM")


def _services_of(conn, master_id, include_inactive=False):
    sql = "SELECT id, name, duration_min, price, is_active FROM services WHERE master_id = ?"
    if not include_inactive:
        sql += " AND is_active = 1"
    sql += " ORDER BY id"
    rows = conn.execute(sql, (master_id,)).fetchall()
    if not include_inactive:
        return [{k: v for k, v in dict(r).items() if k != "is_active"} for r in rows]
    return [dict(r) for r in rows]


def _free_slots(conn, master_id, open_time, close_time, duration_min, date_str):
    """Ustaning shu kundagi bo'sh boshlanish vaqtlari ro'yxati ('09:00', '09:30', ...)."""
    open_dt = datetime.strptime(f"{date_str} {open_time}", DT_FMT)
    close_dt = datetime.strptime(f"{date_str} {close_time}", DT_FMT)
    rows = conn.execute(
        "SELECT start_at, end_at FROM bookings "
        "WHERE master_id = ? AND substr(start_at, 1, 10) = ? AND status IN ('booked', 'done')",
        (master_id, date_str),
    ).fetchall()
    busy = [
        (datetime.strptime(r["start_at"], DT_FMT), datetime.strptime(r["end_at"], DT_FMT))
        for r in rows
    ]
    earliest = now() + timedelta(minutes=config.MIN_LEAD_MIN)
    step = timedelta(minutes=config.SLOT_STEP_MIN)
    dur = timedelta(minutes=duration_min)

    slots = []
    t = open_dt
    while t + dur <= close_dt:
        overlaps = any(t < b_end and t + dur > b_start for b_start, b_end in busy)
        if t >= earliest and not overlaps:
            slots.append(t.strftime("%H:%M"))
        t += step
    return slots


# ---------- mijoz uchun: ko'rish ----------

def list_districts():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id, name FROM districts ORDER BY name")]


def haversine_km(lat1, lng1, lat2, lng2):
    """Ikki koordinata orasidagi masofa (taxminiy, kilometrda)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(a)))


def _attach_distance(rows, client_lat, client_lng):
    """Har bir qatorga (lat/lng bor bo'lsa) mijozgacha masofani (km) qo'shadi."""
    has_client = client_lat is not None and client_lng is not None
    for r in rows:
        dist = None
        if has_client and r.get("lat") is not None and r.get("lng") is not None:
            dist = round(haversine_km(client_lat, client_lng, r["lat"], r["lng"]), 1)
        r["distance_km"] = dist
    return has_client


def list_salons(district_id=None, kind=None, client_lat=None, client_lng=None):
    if kind is not None and kind not in KINDS:
        raise BookingError("invalid", "kind: barbershop yoki beauty bo'lishi kerak")
    sql = """
        SELECT s.id, s.name, s.kind, s.district_id, s.address, s.phone, s.open_time, s.close_time,
               s.photo_url, s.lat, s.lng,
               (SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.salon_id = s.id) AS rating,
               (SELECT COUNT(*) FROM reviews r WHERE r.salon_id = s.id) AS reviews_count
        FROM salons s
        WHERE s.is_active = 1 AND (
              COALESCE(s.paid_until, '') >= :today
              OR EXISTS (SELECT 1 FROM masters m WHERE m.salon_id = s.id AND m.is_active = 1
                         AND COALESCE(m.paid_until, '') >= :today))
    """
    params = {"today": today_str()}
    if district_id is not None:
        sql += " AND s.district_id = :district_id"
        params["district_id"] = district_id
    if kind is not None:
        sql += " AND s.kind = :kind"
        params["kind"] = kind
    with db() as c:
        rows = [dict(r) for r in c.execute(sql, params)]
    has_client = _attach_distance(rows, client_lat, client_lng)
    if has_client:
        # masofasi ma'lumlar eng yaqindan boshlab, masofasi yo'qlar oxirida (reyting bo'yicha)
        rows.sort(key=lambda r: (r["distance_km"] is None,
                                  r["distance_km"] if r["distance_km"] is not None else 0,
                                  r["rating"] is None, -(r["rating"] or 0), r["name"]))
    else:
        # reytingi yuqorilar birinchi, bahosizlar oxirida
        rows.sort(key=lambda r: (r["rating"] is None, -(r["rating"] or 0), r["name"]))
    return rows


def list_masters(salon_id):
    sql = f"""
        SELECT m.id, m.name, m.salon_id, m.photo_url,
               (SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.master_id = m.id) AS rating,
               (SELECT COUNT(*) FROM reviews r WHERE r.master_id = m.id) AS reviews_count
        FROM masters m JOIN salons s ON s.id = m.salon_id
        WHERE m.salon_id = :salon_id AND {VISIBLE}
        ORDER BY m.name
    """
    with db() as c:
        rows = c.execute(sql, {"salon_id": salon_id, "today": today_str()}).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["services"] = _services_of(c, r["id"])
            result.append(d)
        return result


def list_reviews(master_id, limit=20):
    with db() as c:
        rows = c.execute(
            "SELECT r.rating, r.comment, r.created_at, b.client_name "
            "FROM reviews r JOIN bookings b ON b.id = r.booking_id "
            "WHERE r.master_id = ? ORDER BY r.id DESC LIMIT ?",
            (master_id, limit),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["client_name"] = d["client_name"].split()[0]   # faqat ismi ko'rinadi
        result.append(d)
    return result


def get_free_slots(master_id, service_id, date_str):
    _check_date(date_str)
    sql = f"""
        SELECT m.id, s.open_time, s.close_time, sv.duration_min
        FROM masters m
        JOIN salons s ON s.id = m.salon_id
        JOIN services sv ON sv.master_id = m.id
        WHERE m.id = :master_id AND sv.id = :service_id AND {VISIBLE_SVC}
    """
    with db() as c:
        row = c.execute(
            sql, {"master_id": master_id, "service_id": service_id, "today": today_str()}
        ).fetchone()
        if row is None:
            raise BookingError("not_found", "Usta yoki xizmat topilmadi")
        slots = _free_slots(c, master_id, row["open_time"], row["close_time"],
                            row["duration_min"], date_str)
    return {"date": date_str, "slots": slots}


def nearby_free(district_id, date_str, duration_min=30, kind=None,
                exclude_master_id=None, per_master=6, client_lat=None, client_lng=None):
    """Usta band bo'lsa: shu tumandagi boshqa ustalarning bo'sh vaqtlari va manzillari."""
    _check_date(date_str)
    if kind is not None and kind not in KINDS:
        raise BookingError("invalid", "kind: barbershop yoki beauty bo'lishi kerak")
    sql = f"""
        SELECT m.id AS master_id, m.name AS master_name, m.photo_url AS master_photo_url,
               s.id AS salon_id, s.name AS salon_name, s.kind, s.address, s.phone,
               s.open_time, s.close_time, s.photo_url AS salon_photo_url, s.lat, s.lng,
               (SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.master_id = m.id) AS rating,
               (SELECT COUNT(*) FROM reviews r WHERE r.master_id = m.id) AS reviews_count
        FROM masters m JOIN salons s ON s.id = m.salon_id
        WHERE s.district_id = :district_id AND {VISIBLE}
    """
    params = {"district_id": district_id, "today": today_str()}
    if kind is not None:
        sql += " AND s.kind = :kind"
        params["kind"] = kind
    if exclude_master_id is not None:
        sql += " AND m.id != :exclude"
        params["exclude"] = exclude_master_id

    result = []
    with db() as c:
        for r in c.execute(sql, params).fetchall():
            slots = _free_slots(c, r["master_id"], r["open_time"], r["close_time"],
                                duration_min, date_str)
            if not slots:
                continue
            services = _services_of(c, r["master_id"])
            if not services:          # xizmati yo'q usta bron qila olmaydi
                continue
            item = dict(r)
            del item["open_time"], item["close_time"]
            item["slots"] = slots[:per_master]
            item["services"] = services
            result.append(item)
    _attach_distance(result, client_lat, client_lng)
    # eng erta bo'sh vaqt birinchi, teng bo'lsa reytingi yuqori
    result.sort(key=lambda x: (x["slots"][0], -(x["rating"] or 0)))
    return result


# ---------- bron ----------

def _booking_row(conn, booking_no):
    return conn.execute(
        """
        SELECT b.id, b.booking_no, b.status, b.start_at, b.end_at, b.client_name,
               b.client_phone, b.client_tg_id, b.master_id,
               m.name AS master_name, s.id AS salon_id, s.name AS salon_name, s.address,
               sv.name AS service_name, sv.price
        FROM bookings b
        JOIN masters m ON m.id = b.master_id
        JOIN salons s ON s.id = m.salon_id
        JOIN services sv ON sv.id = b.service_id
        WHERE b.booking_no = ?
        """,
        (booking_no,),
    ).fetchone()


def _public(row):
    d = dict(row)
    d.pop("client_tg_id", None)
    d.pop("id", None)
    return d


def create_booking(master_id, service_id, date_str, time_str,
                   client_name, client_phone, client_tg_id=None):
    client_name = (client_name or "").strip()
    client_phone = (client_phone or "").strip()
    if len(client_name) < 2:
        raise BookingError("invalid", "Ismni kiriting")
    if len(re.sub(r"\D", "", client_phone)) < 9:
        raise BookingError("invalid", "Telefon raqami noto'g'ri")
    _check_date(date_str)
    try:
        start = datetime.strptime(f"{date_str} {time_str}", DT_FMT)
    except (TypeError, ValueError):
        raise BookingError("invalid", "Vaqt noto'g'ri. Format: HH:MM")

    sql = f"""
        SELECT s.open_time, s.close_time, sv.duration_min
        FROM masters m
        JOIN salons s ON s.id = m.salon_id
        JOIN services sv ON sv.master_id = m.id
        WHERE m.id = :master_id AND sv.id = :service_id AND {VISIBLE_SVC}
    """
    with db() as c:
        with immediate(c):
            row = c.execute(
                sql, {"master_id": master_id, "service_id": service_id, "today": today_str()}
            ).fetchone()
            if row is None:
                raise BookingError("not_found", "Usta yoki xizmat topilmadi")

            end = start + timedelta(minutes=row["duration_min"])
            open_dt = datetime.strptime(f"{date_str} {row['open_time']}", DT_FMT)
            close_dt = datetime.strptime(f"{date_str} {row['close_time']}", DT_FMT)
            if start < open_dt or end > close_dt:
                raise BookingError("invalid", "Bu vaqt salonning ish vaqtidan tashqarida")
            minutes_from_open = int((start - open_dt).total_seconds() // 60)
            if minutes_from_open % config.SLOT_STEP_MIN != 0:
                raise BookingError("invalid", "Vaqt noto'g'ri (faqat ro'yxatdagi vaqtlar)")
            if start < now() + timedelta(minutes=config.MIN_LEAD_MIN):
                raise BookingError("invalid", "Bu vaqt o'tib ketgan yoki juda yaqin")

            start_s, end_s = start.strftime(DT_FMT), end.strftime(DT_FMT)
            # Asosiy himoya: shu oraliqqa tegadigan faol bron bormi?
            clash = c.execute(
                "SELECT 1 FROM bookings WHERE master_id = ? AND status IN ('booked', 'done') "
                "AND start_at < ? AND end_at > ? LIMIT 1",
                (master_id, end_s, start_s),
            ).fetchone()
            if clash:
                raise BookingError("slot_taken", "Bu vaqt band qilingan, boshqasini tanlang")

            cur = c.execute(
                "INSERT INTO bookings (master_id, service_id, client_name, client_phone, "
                "client_tg_id, start_at, end_at, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'booked', ?)",
                (master_id, service_id, client_name, client_phone, client_tg_id,
                 start_s, end_s, now().strftime(DT_FMT)),
            )
            booking_no = f"BQ-{cur.lastrowid:05d}"
            c.execute("UPDATE bookings SET booking_no = ? WHERE id = ?",
                      (booking_no, cur.lastrowid))
        return _public(_booking_row(c, booking_no))


def list_client_bookings(client_tg_id):
    """Mijozning o'z bronlari ("Bronlarim"). Ism va telefon qaytarilmaydi."""
    if client_tg_id is None:
        raise BookingError("invalid", "client_tg_id kerak")
    with db() as c:
        rows = c.execute(
            """
            SELECT b.booking_no, b.status, b.start_at, b.end_at, b.master_id,
                   m.name AS master_name, s.id AS salon_id, s.name AS salon_name, s.address,
                   sv.name AS service_name, sv.price,
                   EXISTS (SELECT 1 FROM reviews r WHERE r.booking_id = b.id) AS reviewed
            FROM bookings b
            JOIN masters m ON m.id = b.master_id
            JOIN salons s ON s.id = m.salon_id
            JOIN services sv ON sv.id = b.service_id
            WHERE b.client_tg_id = ?
            ORDER BY b.start_at DESC
            LIMIT 50
            """,
            (client_tg_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["reviewed"] = bool(d["reviewed"])
        result.append(d)
    return result


def cancel_booking(booking_no, client_tg_id):
    """Mijoz o'z bronini bekor qiladi (faqat o'zi yaratgan bo'lsa)."""
    with db() as c:
        with immediate(c):
            row = _booking_row(c, booking_no)
            if row is None:
                raise BookingError("not_found", "Bron topilmadi")
            if row["client_tg_id"] is None or row["client_tg_id"] != client_tg_id:
                raise BookingError("forbidden", "Bu bron sizniki emas")
            if row["status"] != "booked":
                raise BookingError("invalid", "Bu bronni bekor qilib bo'lmaydi")
            if datetime.strptime(row["start_at"], DT_FMT) <= now():
                raise BookingError("invalid", "Vaqti boshlanib bo'lgan bronni bekor qilib bo'lmaydi")
            c.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (row["id"],))
        return _public(_booking_row(c, booking_no))


def set_booking_status(booking_no, status, master_id=None):
    """Usta/admin: done (xizmat bajarildi), no_show (kelmadi) yoki cancelled.
    master_id berilsa (usta paneli), faqat o'ziga tegishli bronlarni o'zgartira oladi."""
    if status not in ("done", "no_show", "cancelled"):
        raise BookingError("invalid", "status: done, no_show yoki cancelled")
    with db() as c:
        with immediate(c):
            row = _booking_row(c, booking_no)
            if row is None:
                raise BookingError("not_found", "Bron topilmadi")
            if master_id is not None and row["master_id"] != master_id:
                raise BookingError("forbidden", "Bu bron sizga tegishli emas")
            if row["status"] != "booked":
                raise BookingError("invalid", "Faqat 'booked' holatdagi bronni o'zgartirish mumkin")
            started = datetime.strptime(row["start_at"], DT_FMT) <= now()
            if status in ("done", "no_show") and not started:
                raise BookingError("invalid", "Bron vaqti hali boshlanmagan")
            c.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, row["id"]))
        return _public(_booking_row(c, booking_no))


# ---------- reyting ----------

def add_review(booking_no, client_tg_id, rating, comment=""):
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise BookingError("invalid", "Baho 1 dan 5 gacha bo'lishi kerak")
    comment = (comment or "").strip()[:500]
    with db() as c:
        with immediate(c):
            row = _booking_row(c, booking_no)
            if row is None:
                raise BookingError("not_found", "Bron topilmadi")
            if row["client_tg_id"] is None or row["client_tg_id"] != client_tg_id:
                raise BookingError("forbidden", "Bu bron sizniki emas")
            if row["status"] != "done":
                raise BookingError("invalid", "Baho faqat xizmat tugagandan keyin beriladi")
            try:
                c.execute(
                    "INSERT INTO reviews (booking_id, master_id, salon_id, rating, comment, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (row["id"], row["master_id"], row["salon_id"], rating, comment,
                     now().strftime(DT_FMT)),
                )
            except sqlite3.IntegrityError:
                raise BookingError("invalid", "Siz bu bronga allaqachon baho bergansiz")
    return {"ok": True}


# ---------- admin ----------

def _insert(conn, sql, params):
    try:
        cur = conn.execute(sql, params)
    except sqlite3.IntegrityError:
        raise BookingError("invalid", "Ma'lumot noto'g'ri yoki takrorlangan (bog'langan yozuv topilmadi?)")
    return cur.lastrowid


def _check_paid_until(value):
    if value is None:
        return
    try:
        datetime.strptime(value, DATE_FMT)
    except (TypeError, ValueError):
        raise BookingError("invalid", "paid_until formati: YYYY-MM-DD")


def add_district(name):
    name = (name or "").strip()
    if not name:
        raise BookingError("invalid", "Tuman nomini kiriting")
    with db() as c:
        return {"id": _insert(c, "INSERT INTO districts (name) VALUES (?)", (name,))}


def _check_latlng(lat, lng):
    if lat is None and lng is None:
        return
    if lat is None or lng is None:
        raise BookingError("invalid", "lat va lng ikkalasi birga berilishi kerak")
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise BookingError("invalid", "Koordinata noto'g'ri")


def add_salon(name, kind, district_id, address, phone=None,
              open_time="09:00", close_time="20:00", paid_until=None,
              photo_url=None, lat=None, lng=None):
    if kind not in KINDS:
        raise BookingError("invalid", "kind: barbershop yoki beauty")
    _check_hhmm(open_time, "open_time")
    _check_hhmm(close_time, "close_time")
    if open_time >= close_time:
        raise BookingError("invalid", "Ochilish vaqti yopilishdan oldin bo'lishi kerak")
    _check_paid_until(paid_until)
    _check_latlng(lat, lng)
    with db() as c:
        new_id = _insert(
            c,
            "INSERT INTO salons (name, kind, district_id, address, phone, open_time, close_time, "
            "paid_until, photo_url, lat, lng) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name.strip(), kind, district_id, address.strip(), phone, open_time, close_time,
             paid_until, photo_url, lat, lng),
        )
    return {"id": new_id}


def set_salon_photo(salon_id, photo_url):
    """Salonning rasm manzilini belgilash yoki o'chirish (photo_url=None bo'lsa, rasm olib tashlanadi)."""
    with db() as c:
        cur = c.execute("UPDATE salons SET photo_url = ? WHERE id = ?", (photo_url, salon_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Salon topilmadi")
    return {"ok": True}


def set_salon_location(salon_id, lat, lng):
    """Salon koordinatasini belgilash yoki o'chirish (lat=lng=None bo'lsa, masofa hisoblanmaydi)."""
    _check_latlng(lat, lng)
    with db() as c:
        cur = c.execute("UPDATE salons SET lat = ?, lng = ? WHERE id = ?", (lat, lng, salon_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Salon topilmadi")
    return {"ok": True}


def add_master(salon_id, name, paid_until=None, photo_url=None):
    _check_paid_until(paid_until)
    with db() as c:
        return {"id": _insert(
            c, "INSERT INTO masters (salon_id, name, paid_until, photo_url) VALUES (?, ?, ?, ?)",
            (salon_id, name.strip(), paid_until, photo_url))}


def set_master_photo(master_id, photo_url):
    """Ustaning rasmini belgilash yoki o'chirish (photo_url=None bo'lsa, rasm olib tashlanadi)."""
    with db() as c:
        cur = c.execute("UPDATE masters SET photo_url = ? WHERE id = ?", (photo_url, master_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Usta topilmadi")
    return {"ok": True}


def add_service(master_id, name, duration_min, price):
    with db() as c:
        return {"id": _insert(
            c, "INSERT INTO services (master_id, name, duration_min, price) VALUES (?, ?, ?, ?)",
            (master_id, name.strip(), duration_min, price))}


def update_service(service_id, name=None, duration_min=None, price=None):
    """Xizmat nomi, davomiyligi yoki narxini tuzatish. Faqat berilgan maydonlar o'zgaradi."""
    fields, params = [], []
    if name is not None:
        name = name.strip()
        if not name:
            raise BookingError("invalid", "Xizmat nomi bo'sh bo'lmasin")
        fields.append("name = ?"); params.append(name)
    if duration_min is not None:
        fields.append("duration_min = ?"); params.append(duration_min)
    if price is not None:
        fields.append("price = ?"); params.append(price)
    if not fields:
        raise BookingError("invalid", "O'zgartiradigan hech narsa berilmadi")
    params.append(service_id)
    with db() as c:
        try:
            cur = c.execute(f"UPDATE services SET {', '.join(fields)} WHERE id = ?", params)
        except sqlite3.IntegrityError:
            raise BookingError("invalid", "Noto'g'ri qiymat (masalan, davomiylik 10-480 oralig'ida bo'lishi kerak)")
        if cur.rowcount == 0:
            raise BookingError("not_found", "Xizmat topilmadi")
    return {"ok": True}


def set_service_active(service_id, is_active):
    """Xizmatni yashirish (mijozga ko'rinmaydi, lekin eski bronlar saqlanadi) yoki qaytarish."""
    with db() as c:
        cur = c.execute("UPDATE services SET is_active = ? WHERE id = ?", (1 if is_active else 0, service_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Xizmat topilmadi")
    return {"ok": True}


def delete_service(service_id):
    """Xizmatni butunlay o'chirish. Agar unga bron qilingan bo'lsa (hozir yoki tarixda),
    o'chirib bo'lmaydi — buning o'rniga set_service_active bilan yashiring."""
    with db() as c:
        used = c.execute("SELECT 1 FROM bookings WHERE service_id = ? LIMIT 1", (service_id,)).fetchone()
        if used:
            raise BookingError("invalid", "Bu xizmatga bronlar mavjud, shuning uchun o'chirib bo'lmaydi. "
                                          "Buning o'rniga yashiring (active=false)")
        cur = c.execute("DELETE FROM services WHERE id = ?", (service_id,))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Xizmat topilmadi")
    return {"ok": True}


# ---------- admin: ro'yxatlar (yashirilgan/to'lanmagan ham ko'rinadi) ----------

def admin_list_salons():
    sql = """
        SELECT s.id, s.name, s.kind, s.district_id, d.name AS district_name, s.address, s.phone,
               s.open_time, s.close_time, s.paid_until, s.is_active, s.photo_url, s.lat, s.lng
        FROM salons s JOIN districts d ON d.id = s.district_id
        ORDER BY d.name, s.name
    """
    with db() as c:
        return [dict(r) for r in c.execute(sql)]


def admin_list_masters(salon_id):
    sql = ("SELECT id, salon_id, name, paid_until, is_active, phone, photo_url, "
           "(password_hash IS NOT NULL) AS has_login "
           "FROM masters WHERE salon_id = ? ORDER BY name")
    with db() as c:
        rows = [dict(r) for r in c.execute(sql, (salon_id,))]
    for r in rows:
        r["has_login"] = bool(r["has_login"])
    return rows


def admin_list_services(master_id):
    with db() as c:
        return _services_of(c, master_id, include_inactive=True)


def set_active(target, target_id, is_active):
    """Salon yoki ustani yashirish/qaytarish. target: 'salon' yoki 'master'."""
    if target not in ("salon", "master"):
        raise BookingError("invalid", "target: salon yoki master")
    table = "salons" if target == "salon" else "masters"
    with db() as c:
        cur = c.execute(f"UPDATE {table} SET is_active = ? WHERE id = ?", (1 if is_active else 0, target_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Topilmadi")
    return {"ok": True}


def set_paid_until(target, target_id, paid_until):
    """Abonent to'lovini uzaytirish. target: 'salon' yoki 'master'."""
    if target not in ("salon", "master"):
        raise BookingError("invalid", "target: salon yoki master")
    _check_paid_until(paid_until)
    table = "salons" if target == "salon" else "masters"
    with db() as c:
        cur = c.execute(f"UPDATE {table} SET paid_until = ? WHERE id = ?", (paid_until, target_id))
        if cur.rowcount == 0:
            raise BookingError("not_found", "Topilmadi")
    return {"ok": True}


def list_day_bookings(date_str, salon_id=None):
    try:
        datetime.strptime(date_str, DATE_FMT)
    except (TypeError, ValueError):
        raise BookingError("invalid", "Sana noto'g'ri. Format: YYYY-MM-DD")
    sql = """
        SELECT b.booking_no, b.status, b.start_at, b.end_at, b.client_name, b.client_phone,
               m.name AS master_name, s.name AS salon_name, sv.name AS service_name, sv.price
        FROM bookings b
        JOIN masters m ON m.id = b.master_id
        JOIN salons s ON s.id = m.salon_id
        JOIN services sv ON sv.id = b.service_id
        WHERE substr(b.start_at, 1, 10) = :day
    """
    params = {"day": date_str}
    if salon_id is not None:
        sql += " AND s.id = :salon_id"
        params["salon_id"] = salon_id
    sql += " ORDER BY b.start_at"
    with db() as c:
        return [dict(r) for r in c.execute(sql, params)]


# ---------- usta paneli (telefon + parol bilan kirish) ----------

def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"{salt}${digest}"


def _verify_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(_hash_password(password, salt), stored)


def _normalize_phone(phone):
    """+998 bo'lsa ham, bo'lmasa ham bir xil solishtiriladigan shaklga keltiradi
    (O'zbekiston mobil raqami: 998 kodisiz 9 ta raqam, masalan 901234567)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("998") and len(digits) == 12:
        digits = digits[3:]
    if len(digits) != 9:
        raise BookingError("invalid", "Telefon raqami noto'g'ri (9 xonali, masalan 901234567)")
    return digits


def set_master_credentials(master_id, phone, password):
    """Admin: ustaga panelga kirish uchun telefon + parol beradi (yoki yangilaydi)."""
    phone = _normalize_phone(phone)
    if len(password or "") < 4:
        raise BookingError("invalid", "Parol kamida 4 ta belgidan iborat bo'lsin")
    pw_hash = _hash_password(password)
    with db() as c:
        try:
            cur = c.execute(
                "UPDATE masters SET phone = ?, password_hash = ?, auth_token = NULL WHERE id = ?",
                (phone, pw_hash, master_id),
            )
        except sqlite3.IntegrityError:
            raise BookingError("invalid", "Bu telefon raqami boshqa ustada band")
        if cur.rowcount == 0:
            raise BookingError("not_found", "Usta topilmadi")
    return {"ok": True}


def usta_login(phone, password):
    """Usta o'z paneliga kiradi. Muvaffaqiyatli bo'lsa, yangi sessiya tokeni beriladi."""
    digits = _normalize_phone(phone)
    with db() as c:
        with immediate(c):
            row = c.execute(
                "SELECT id, password_hash FROM masters WHERE phone = ? AND is_active = 1", (digits,)
            ).fetchone()
            if row is None or not _verify_password(password, row["password_hash"]):
                raise BookingError("forbidden", "Telefon yoki parol noto'g'ri")
            token = secrets.token_hex(24)
            c.execute("UPDATE masters SET auth_token = ? WHERE id = ?", (token, row["id"]))
    return {"token": token}


def usta_logout(master_id):
    with db() as c:
        c.execute("UPDATE masters SET auth_token = NULL WHERE id = ?", (master_id,))
    return {"ok": True}


def usta_by_token(token):
    """Sessiya tokeniga qarab joriy ustani qaytaradi (topilmasa None)."""
    if not token:
        return None
    sql = """
        SELECT m.id, m.name, m.salon_id, s.name AS salon_name, s.kind, s.address
        FROM masters m JOIN salons s ON s.id = m.salon_id
        WHERE m.auth_token = ? AND m.is_active = 1
    """
    with db() as c:
        row = c.execute(sql, (token,)).fetchone()
    return dict(row) if row else None


def list_master_day_bookings(master_id, date_str):
    """Ustaning shu kungi bronlari — o'z paneli uchun (mijoz ismi/telefoni ko'rinadi)."""
    try:
        datetime.strptime(date_str, DATE_FMT)
    except (TypeError, ValueError):
        raise BookingError("invalid", "Sana noto'g'ri. Format: YYYY-MM-DD")
    sql = """
        SELECT b.booking_no, b.status, b.start_at, b.end_at, b.client_name, b.client_phone,
               sv.name AS service_name, sv.price
        FROM bookings b JOIN services sv ON sv.id = b.service_id
        WHERE b.master_id = ? AND substr(b.start_at, 1, 10) = ?
        ORDER BY b.start_at
    """
    with db() as c:
        return [dict(r) for r in c.execute(sql, (master_id, date_str))]


def master_day_stats(master_id, date_str):
    """Usta paneli uchun kunlik qisqacha: savdo, kutilayotgan/kelgan/bekor mijozlar soni."""
    try:
        datetime.strptime(date_str, DATE_FMT)
    except (TypeError, ValueError):
        raise BookingError("invalid", "Sana noto'g'ri. Format: YYYY-MM-DD")
    sql = """
        SELECT b.status, sv.price
        FROM bookings b JOIN services sv ON sv.id = b.service_id
        WHERE b.master_id = ? AND substr(b.start_at, 1, 10) = ?
    """
    with db() as c:
        rows = c.execute(sql, (master_id, date_str)).fetchall()
    revenue = sum(r["price"] for r in rows if r["status"] == "done")
    return {
        "date": date_str,
        "revenue": revenue,
        "pending": sum(1 for r in rows if r["status"] == "booked"),
        "done": sum(1 for r in rows if r["status"] == "done"),
        "missed": sum(1 for r in rows if r["status"] in ("cancelled", "no_show")),
        "total": len(rows),
    }
