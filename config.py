"""BandQil sozlamalari. Maxfiy narsalar .env faylida turadi (kodga yozilmaydi)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env():
    """Oddiy .env o'qigich: KEY=value qatorlarini muhit o'zgaruvchisiga qo'yadi."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

# Ma'lumotlar bazasi fayli (keyin PostgreSQL'ga o'tamiz)
DB_PATH = os.getenv("BANDQIL_DB", str(BASE_DIR / "bandqil.db"))

# Yuklangan rasmlar papkasi. Standart: baza fayli yonidagi "uploads" papka.
# Hostingda BANDQIL_DB ni doimiy disk (volume) ichiga ko'rsating — rasmlar ham shu yerda saqlanadi.
UPLOAD_DIR = os.getenv("BANDQIL_UPLOADS", str(Path(DB_PATH).resolve().parent / "uploads"))

# Admin API uchun maxfiy kalit (.env ichida ADMIN_TOKEN=uzun-tasodifiy-matn)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Adminga Telegram orqali xabar yuborish uchun (ixtiyoriy)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()]

# Bron qoidalari
SLOT_STEP_MIN = 30      # vaqtlar har 30 daqiqada (09:00, 09:30, ...)
MIN_LEAD_MIN = 30       # hozirdan kamida 30 daqiqa keyingi vaqtga bron qilish mumkin
MAX_DAYS_AHEAD = 14     # eng ko'pi bilan 14 kun oldinga
