"""Ma'lumotlar bazasi: ulanish va jadvallar."""
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS districts (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Salon: sartaroshxona yoki go'zallik saloni
CREATE TABLE IF NOT EXISTS salons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('barbershop', 'beauty')),
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
