"""BandQil serveri (FastAPI). Ishga tushirish: uvicorn main:app --reload
Brauzerda http://127.0.0.1:8000/docs ochilsa, hamma so'rovlarni qo'lda sinab ko'rish mumkin."""
import logging
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import services as svc
from db import init_db
from notify import notify_admins
from tg_auth import verify_init_data

logging.basicConfig(level=logging.INFO)
init_db()

STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOAD_PATH = Path(config.UPLOAD_DIR)
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="BandQil API", version="0.1")

STATUS_BY_CODE = {"invalid": 400, "forbidden": 403, "not_found": 404, "slot_taken": 409}


def telegram_client_id(x_telegram_init_data: str = Header(default="")) -> Optional[int]:
    """Telegram Mini App ichida ochilgan bo'lsa, brauzer yuborgan 'initData'ni serverda
    tekshirib, haqiqiy Telegram ID'ni qaytaradi. Soxta (spoof qilingan) ID qabul qilinmaydi.
    Oddiy brauzerda (Telegram tashqarisida) ochilgan bo'lsa, None qaytadi — bu holatda
    so'rovdagi client_tg_id (mijoz qurilmasida saqlangan vaqtinchalik ID) ishlatiladi,
    chunki u yerda haqiqiy Telegram autentifikatsiyasi umuman yo'q."""
    if not x_telegram_init_data or not config.BOT_TOKEN:
        return None
    user = verify_init_data(x_telegram_init_data, config.BOT_TOKEN)
    if user is None:
        raise HTTPException(status_code=403, detail="Telegram ma'lumoti noto'g'ri yoki eskirgan")
    return int(user["id"])


@app.exception_handler(svc.BookingError)
async def booking_error_handler(request, exc: svc.BookingError):
    return JSONResponse(
        status_code=STATUS_BY_CODE.get(exc.code, 400),
        content={"code": exc.code, "detail": exc.message},
    )


# ---------- so'rov shakllari ----------

class BookingIn(BaseModel):
    master_id: int
    service_id: int
    date: str = Field(description="YYYY-MM-DD")
    time: str = Field(description="HH:MM")
    client_name: str = Field(min_length=2, max_length=60)
    client_phone: str = Field(min_length=9, max_length=20)
    client_tg_id: Optional[int] = None


class CancelIn(BaseModel):
    client_tg_id: int


class ReviewIn(BaseModel):
    booking_no: str
    client_tg_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=500)


class DistrictIn(BaseModel):
    name: str


class DistrictRenameIn(BaseModel):
    name: str


class SalonUpdateIn(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = Field(default=None, description="barbershop, beauty, computer_club yoki billiard_club")
    district_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None


class MasterRenameIn(BaseModel):
    name: str


class SalonIn(BaseModel):
    name: str
    kind: str = Field(description="barbershop, beauty, computer_club yoki billiard_club")
    district_id: int
    address: str
    phone: Optional[str] = None
    open_time: str = "09:00"
    close_time: str = "20:00"
    paid_until: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    photo_url: Optional[str] = Field(default=None, description="Salon rasmining havolasi")
    lat: Optional[float] = Field(default=None, description="Kenglik (masofani hisoblash uchun)")
    lng: Optional[float] = Field(default=None, description="Uzunlik (masofani hisoblash uchun)")


class MasterIn(BaseModel):
    salon_id: int
    name: str
    paid_until: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    photo_url: Optional[str] = Field(default=None, description="Usta rasmining havolasi")


class SalonPhotoIn(BaseModel):
    photo_url: Optional[str] = None


class SalonLocationIn(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class MasterPhotoIn(BaseModel):
    photo_url: Optional[str] = None


class ServiceIn(BaseModel):
    master_id: int
    name: str
    duration_min: int
    price: int


class PaidUntilIn(BaseModel):
    target: str = Field(description="salon yoki master")
    target_id: int
    paid_until: str = Field(description="YYYY-MM-DD")


class ActiveIn(BaseModel):
    target: str = Field(description="salon yoki master")
    target_id: int
    is_active: bool


class ServiceUpdateIn(BaseModel):
    name: Optional[str] = None
    duration_min: Optional[int] = None
    price: Optional[int] = None


class ServiceActiveIn(BaseModel):
    is_active: bool


class StatusIn(BaseModel):
    status: str = Field(description="done, no_show yoki cancelled")


class UstaCredentialsIn(BaseModel):
    phone: str
    password: str = Field(min_length=4, max_length=72)


class UstaLoginIn(BaseModel):
    phone: str
    password: str


# ---------- mijoz uchun ----------

@app.get("/api/health")
def health():
    return {"app": "BandQil", "status": "ok"}


@app.get("/api/districts")
def districts():
    return svc.list_districts()


@app.get("/api/salons")
def salons(district_id: Optional[int] = None, kind: Optional[str] = None,
           lat: Optional[float] = None, lng: Optional[float] = None):
    """lat/lng berilsa (mijoz joylashuvini ruxsat etgan bo'lsa), har bir salon uchun
    distance_km (taxminiy masofa, km) qo'shiladi va ro'yxat eng yaqinidan saralanadi."""
    return svc.list_salons(district_id, kind, lat, lng)


@app.get("/api/salons/{salon_id}/masters")
def salon_masters(salon_id: int):
    return svc.list_masters(salon_id)


@app.get("/api/masters/{master_id}/reviews")
def master_reviews(master_id: int):
    return svc.list_reviews(master_id)


@app.get("/api/masters/{master_id}/slots")
def master_slots(master_id: int, service_id: int, date: str):
    return svc.get_free_slots(master_id, service_id, date)


@app.get("/api/nearby")
def nearby(district_id: int, date: str, duration_min: int = 30, kind: Optional[str] = None,
           exclude_master_id: Optional[int] = None,
           lat: Optional[float] = None, lng: Optional[float] = None):
    """Usta band bo'lsa: shu tumandagi boshqa ustalarning bo'sh vaqtlari va manzillari."""
    return svc.nearby_free(district_id, date, duration_min, kind, exclude_master_id,
                           client_lat=lat, client_lng=lng)


@app.post("/api/bookings")
def create_booking(body: BookingIn, background: BackgroundTasks,
                   tg_id: Optional[int] = Depends(telegram_client_id)):
    client_tg_id = tg_id if tg_id is not None else body.client_tg_id
    booking = svc.create_booking(
        body.master_id, body.service_id, body.date, body.time,
        body.client_name, body.client_phone, client_tg_id,
    )
    background.add_task(
        notify_admins,
        f"Yangi bron {booking['booking_no']}\n"
        f"{booking['salon_name']} / {booking['master_name']}\n"
        f"{booking['service_name']} - {booking['start_at']}\n"
        f"Mijoz: {booking['client_name']} {booking['client_phone']}",
    )
    return booking


@app.get("/api/my-bookings")
def my_bookings(client_tg_id: int, tg_id: Optional[int] = Depends(telegram_client_id)):
    return svc.list_client_bookings(tg_id if tg_id is not None else client_tg_id)


@app.post("/api/bookings/{booking_no}/cancel")
def cancel_booking(booking_no: str, body: CancelIn, tg_id: Optional[int] = Depends(telegram_client_id)):
    return svc.cancel_booking(booking_no, tg_id if tg_id is not None else body.client_tg_id)


@app.post("/api/reviews")
def add_review(body: ReviewIn, tg_id: Optional[int] = Depends(telegram_client_id)):
    client_tg_id = tg_id if tg_id is not None else body.client_tg_id
    return svc.add_review(body.booking_no, client_tg_id, body.rating, body.comment)


# ---------- admin (X-Admin-Token sarlavhasi bilan) ----------

def require_admin(x_admin_token: str = Header(default="")):
    # Hozircha oddiy kalit. Keyingi bosqichda Telegram ID orqali tekshiramiz.
    if not config.ADMIN_TOKEN or not secrets.compare_digest(
        x_admin_token.encode("utf-8"), config.ADMIN_TOKEN.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")


admin = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)], tags=["admin"])


@admin.post("/districts")
def admin_add_district(body: DistrictIn):
    return svc.add_district(body.name)


@admin.patch("/districts/{district_id}")
def admin_rename_district(district_id: int, body: DistrictRenameIn):
    return svc.rename_district(district_id, body.name)


@admin.delete("/districts/{district_id}")
def admin_delete_district(district_id: int):
    """Tumanni o'chirish. Unda salonlar bo'lsa, o'chirib bo'lmaydi."""
    return svc.delete_district(district_id)


MAX_PHOTO_BYTES = 5 * 1024 * 1024


def _image_ext(data: bytes):
    """Fayl turini kengaytmasiga emas, ichidagi haqiqiy belgilarga qarab aniqlaydi."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


@admin.post("/upload-photo")
async def admin_upload_photo(file: UploadFile = File(...)):
    """Kompyuterdan rasm yuklash. Qaytgan 'url' ni salon/usta rasmi sifatida saqlash mumkin."""
    data = await file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Rasm hajmi 5 MB dan oshmasin")
    ext = _image_ext(data)
    if ext is None:
        raise HTTPException(status_code=400, detail="Faqat JPG, PNG, WEBP yoki GIF rasm yuklang")
    UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(12) + ext
    (UPLOAD_PATH / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


@admin.get("/salons")
def admin_get_salons():
    """Hamma salonlar: yashirilgan va to'lamaganlar ham ko'rinadi."""
    return svc.admin_list_salons()


@admin.post("/salons")
def admin_add_salon(body: SalonIn):
    return svc.add_salon(body.name, body.kind, body.district_id, body.address, body.phone,
                         body.open_time, body.close_time, body.paid_until,
                         body.photo_url, body.lat, body.lng)


@admin.patch("/salons/{salon_id}")
def admin_update_salon(salon_id: int, body: SalonUpdateIn):
    """Salon maydonlarini tuzatish (faqat yuborilgan maydonlar o'zgaradi)."""
    return svc.update_salon(salon_id, body.name, body.kind, body.district_id, body.address,
                            body.phone, body.open_time, body.close_time)


@admin.delete("/salons/{salon_id}")
def admin_delete_salon(salon_id: int):
    """Salonni o'chirish. Unda ustalar bo'lsa, o'chirib bo'lmaydi."""
    return svc.delete_salon(salon_id)


@admin.post("/salons/{salon_id}/photo")
def admin_set_salon_photo(salon_id: int, body: SalonPhotoIn):
    return svc.set_salon_photo(salon_id, body.photo_url)


@admin.post("/salons/{salon_id}/location")
def admin_set_salon_location(salon_id: int, body: SalonLocationIn):
    return svc.set_salon_location(salon_id, body.lat, body.lng)


@admin.get("/salons/{salon_id}/masters")
def admin_get_masters(salon_id: int):
    return svc.admin_list_masters(salon_id)


@admin.post("/masters")
def admin_add_master(body: MasterIn):
    return svc.add_master(body.salon_id, body.name, body.paid_until, body.photo_url)


@admin.patch("/masters/{master_id}")
def admin_rename_master(master_id: int, body: MasterRenameIn):
    return svc.rename_master(master_id, body.name)


@admin.delete("/masters/{master_id}")
def admin_delete_master(master_id: int):
    """Ustani o'chirish. Unga bronlar bog'langan bo'lsa, o'chirib bo'lmaydi."""
    return svc.delete_master(master_id)


@admin.post("/masters/{master_id}/photo")
def admin_set_master_photo(master_id: int, body: MasterPhotoIn):
    return svc.set_master_photo(master_id, body.photo_url)


@admin.get("/masters/{master_id}/services")
def admin_get_services(master_id: int):
    """Shu ustaning hamma xizmatlari, yashirilganlari ham (is_active maydoni bilan)."""
    return svc.admin_list_services(master_id)


@admin.post("/services")
def admin_add_service(body: ServiceIn):
    return svc.add_service(body.master_id, body.name, body.duration_min, body.price)


@admin.patch("/services/{service_id}")
def admin_update_service(service_id: int, body: ServiceUpdateIn):
    """Xizmat nomi, davomiyligi yoki narxini tuzatish (faqat yuborilgan maydonlar o'zgaradi)."""
    return svc.update_service(service_id, body.name, body.duration_min, body.price)


@admin.post("/services/{service_id}/active")
def admin_service_active(service_id: int, body: ServiceActiveIn):
    """is_active=false: xizmat mijozga ko'rinmay qoladi, lekin eski bronlar saqlanadi."""
    return svc.set_service_active(service_id, body.is_active)


@admin.delete("/services/{service_id}")
def admin_delete_service(service_id: int):
    """Xizmatni butunlay o'chirish. Unga bron qilingan bo'lsa, o'rniga /active bilan yashiring."""
    return svc.delete_service(service_id)


@admin.post("/paid-until")
def admin_paid_until(body: PaidUntilIn):
    return svc.set_paid_until(body.target, body.target_id, body.paid_until)


@admin.post("/active")
def admin_set_active(body: ActiveIn):
    """Salon yoki ustani yashirish/qaytarish (abonentdan boshqa, qo'lda o'chirib qo'yish uchun)."""
    return svc.set_active(body.target, body.target_id, body.is_active)


@admin.get("/bookings")
def admin_bookings(date: str, salon_id: Optional[int] = None):
    return svc.list_day_bookings(date, salon_id)


@admin.post("/bookings/{booking_no}/status")
def admin_booking_status(booking_no: str, body: StatusIn):
    return svc.set_booking_status(booking_no, body.status)


@admin.post("/masters/{master_id}/credentials")
def admin_set_master_credentials(master_id: int, body: UstaCredentialsIn):
    """Ustaga shaxsiy panelga kirish uchun telefon + parol beriladi (qayta chaqirilsa, yangilanadi)."""
    return svc.set_master_credentials(master_id, body.phone, body.password)


app.include_router(admin)


# ---------- usta paneli (X-Usta-Token sarlavhasi bilan) ----------

def require_usta(x_usta_token: str = Header(default="")) -> dict:
    master = svc.usta_by_token(x_usta_token)
    if master is None:
        raise HTTPException(status_code=403, detail="Kirish talab qilinadi")
    return master


usta = APIRouter(prefix="/api/usta", tags=["usta"])


@usta.post("/login")
def usta_login_route(body: UstaLoginIn):
    return svc.usta_login(body.phone, body.password)


@usta.post("/logout")
def usta_logout_route(master: dict = Depends(require_usta)):
    return svc.usta_logout(master["id"])


@usta.get("/me")
def usta_me(master: dict = Depends(require_usta)):
    return master


@usta.get("/bookings")
def usta_bookings(date: str, master: dict = Depends(require_usta)):
    return svc.list_master_day_bookings(master["id"], date)


@usta.get("/stats")
def usta_stats(date: str, master: dict = Depends(require_usta)):
    return svc.master_day_stats(master["id"], date)


@usta.post("/bookings/{booking_no}/status")
def usta_booking_status(booking_no: str, body: StatusIn, master: dict = Depends(require_usta)):
    return svc.set_booking_status(booking_no, body.status, master_id=master["id"])


app.include_router(usta)

# Mijoz sahifalari (static/ papkasi). Eng oxirida turishi kerak, aks holda /api so'rovlarini to'sib qo'yadi.
app.mount("/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
