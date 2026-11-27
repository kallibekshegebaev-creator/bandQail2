"""Ma'lumotlar bazasi: ulanish va jadvallar."""
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS districts (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Salon: sartaroshxona, go'zallik saloni, kompyuter klubi yoki billiard klubi
CREATE TABLE IF NOT EXISTS salons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('barbershop', 'beauty', 'computer_club', 'billiard_club')),
    district_id INTEGER NOT NULL REFERENCES districts(id),
    address     TEXT NOT NULL,
    phone       TEXT,
    open_time   TEXT NOT NULL DEFAULT '09:00',
    close_time  TEXT NOT NULL DEFAULT '20:00',
    paid_until  TEXT,                       -- abonent to'lovi shu sanagacha (YYYY-MM-DD)
    is_active   INTEGER NOT NULL DEFAULT 1,
    photo_url   TEXT,                       -- salon rasmi (ixtiyoriy)
    lat         REAL,                       -- masofani hisoblash uchun koordinata (ixtiyoriy)
    lng         REAL
);

-- Usta: salon ichida ishlaydi. paid_until bo'sh bo'lsa, salonning abonenti amal qiladi
-- phone/password_hash/auth_token: usta o'z shaxsiy paneliga kirishi uchun (admin beradi)
CREATE TABLE IF NOT EXISTS masters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    salon_id      INTEGER NOT NULL REFERENCES salons(id),
    name          TEXT NOT NULL,
    paid_until    TEXT,                     -- ustaning shaxsiy abonenti (ixtiyoriy)
    is_active     INTEGER NOT NULL DEFAULT 1,
    phone         TEXT,                     -- usta panelga kirish uchun telefon (unikal)
    password_hash TEXT,                     -- "tuz$hash" (hashlib.pbkdf2)
    auth_token    TEXT,                     -- joriy sessiya tokeni (login paytida yangilanadi)
    photo_url     TEXT                      -- usta rasmi (ixtiyoriy)
);

CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id    INTEGER NOT NULL REFERENCES masters(id),
    name         TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min BETWEEN 10 AND 480),
    price        INTEGER NOT NULL CHECK (price >= 0),  -- so'mda
    is_active    INTEGER NOT NULL DEFAULT 1            -- 0: yashirilgan (mijozga ko'rinmaydi)
);

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_no   TEXT UNIQUE,
    master_id    INTEGER NOT NULL REFERENCES masters(id),
    service_id   INTEGER NOT NULL REFERENCES services(id),
    client_name  TEXT NOT NULL,
    client_phone TEXT NOT NULL,
    client_tg_id INTEGER,
    start_at     TEXT NOT NULL,             -- 'YYYY-MM-DD HH:MM'
    end_at       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'booked'
                 CHECK (status IN ('booked', 'done', 'cancelled', 'no_show')),
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_master_start ON bookings(master_id, start_at);

-- Baho: faqat xizmat tugagach, bitta bronga bitta baho
CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
    master_id  INTEGER NOT NULL REFERENCES masters(id),
    salon_id   INTEGER NOT NULL REFERENCES salons(id),
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TEXT NOT NULL
);
"""


def connect():
    """Yangi ulanish. Tranzaksiyalarni o'zimiz boshqaramiz (isolation_level=None)."""
    conn = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
    finally:
        conn.close()


def _migrate(conn):
    """Eski bazalarga (shu fayl yangilanishidan oldin yaratilgan) yangi ustunlarni qo'shadi.
    Ustun allaqachon bo'lsa, xatoni e'tiborsiz qoldiradi."""
    try:
        conn.execute("ALTER TABLE services ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    for col_sql in (
        "ALTER TABLE masters ADD COLUMN phone TEXT",
        "ALTER TABLE masters ADD COLUMN password_hash TEXT",
        "ALTER TABLE masters ADD COLUMN auth_token TEXT",
        "ALTER TABLE masters ADD COLUMN photo_url TEXT",
        "ALTER TABLE salons ADD COLUMN photo_url TEXT",
        "ALTER TABLE salons ADD COLUMN lat REAL",
        "ALTER TABLE salons ADD COLUMN lng REAL",
    ):
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass
    # Bo'sh (NULL) qiymatlar bir-biriga to'qnashmaydi, shuning uchun hali login olmagan
    # ustalar uchun ham xavfsiz — faqat haqiqiy telefon/token takrorlanishini to'sadi.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_masters_phone ON masters(phone)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_masters_token ON masters(auth_token)")
    _migrate_salons_kind_check(conn)


SALONS_DDL = """
    CREATE TABLE salons (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        kind        TEXT NOT NULL CHECK (kind IN ('barbershop', 'beauty', 'computer_club', 'billiard_club')),
        district_id INTEGER NOT NULL REFERENCES districts(id),
        address     TEXT NOT NULL,
        phone       TEXT,
        open_time   TEXT NOT NULL DEFAULT '09:00',
        close_time  TEXT NOT NULL DEFAULT '20:00',
        paid_until  TEXT,
        is_active   INTEGER NOT NULL DEFAULT 1,
        photo_url   TEXT,
        lat         REAL,
        lng         REAL
    )"""


def _migrate_salons_kind_check(conn):
    """Eski bazalarda salons.kind faqat 'barbershop'/'beauty' ni qabul qilardi. Jadvalni yangi
    shart bilan qayta quramiz (ma'lumotlar saqlanadi).

    MUHIM: oldingi versiya jadvalni RENAME qilardi — SQLite bunda ustalar/baholar jadvalidagi
    havolalarni ham "salons_old" ga ko'chirib yuborardi va yangi salon/usta qo'shish
    "Ma'lumot noto'g'ri yoki takrorlangan" xatosi bilan to'xtardi. Endi havolalarga tegmaymiz,
    va shu xatodan buzilgan bazalarni ham o'zi tuzatadi."""
    repaired = False
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='salons'").fetchone()
        if row is not None and row["sql"] and "computer_club" not in row["sql"]:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(salons)")]
            conn.execute("BEGIN")
            conn.execute(SALONS_DDL.replace("TABLE salons", "TABLE salons_new", 1))
            new_cols = [r["name"] for r in conn.execute("PRAGMA table_info(salons_new)")]
            use = ", ".join(c for c in new_cols if c in cols)
            conn.execute(f"INSERT INTO salons_new ({use}) SELECT {use} FROM salons")
            conn.execute("DROP TABLE salons")
            conn.execute("ALTER TABLE salons_new RENAME TO salons")
            conn.execute("COMMIT")

        # Oldingi buggy migratsiyadan qolgan: boshqa jadvallar "salons_old" ga qarab qolgan
        broken = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%salons_old%'").fetchall()
        if broken:
            old_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='salons_old'").fetchone()
            if old_exists:  # yo'qolib qolgan qatorlar bo'lsa, qaytarib olamiz
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(salons)")]
                old_cols = [r["name"] for r in conn.execute("PRAGMA table_info(salons_old)")]
                use = ", ".join(c for c in cols if c in old_cols)
                conn.execute(f"INSERT OR IGNORE INTO salons ({use}) SELECT {use} FROM salons_old")
            ver = conn.execute("PRAGMA schema_version").fetchone()[0]
            conn.execute("PRAGMA writable_schema = ON")
            conn.execute("UPDATE sqlite_master SET sql = REPLACE(REPLACE(sql, '\"salons_old\"', 'salons'), "
                         "'salons_old', 'salons') WHERE type='table' AND name != 'salons_old' AND sql LIKE '%salons_old%'")
            conn.execute(f"PRAGMA schema_version = {ver + 1}")
            conn.execute("PRAGMA writable_schema = OFF")
            repaired = True
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    if repaired:
        # sxema o'zgargani uchun yangi ulanish bilan davom etamiz
        fresh = connect()
        try:
            fresh.execute("PRAGMA foreign_keys = OFF")
            fresh.execute("DROP TABLE IF EXISTS salons_old")
        finally:
            fresh.close()
