"""Asosiy mantiq testlari. Ishga tushirish: python test_core.py
Vaqtinchalik baza ishlatiladi, haqiqiy bazangizga tegmaydi."""
import os
import tempfile
import threading
from datetime import timedelta

_tmp = tempfile.mkdtemp()
os.environ["BANDQIL_DB"] = os.path.join(_tmp, "test.db")

import db  # noqa: E402
import services as sv  # noqa: E402

db.init_db()


def expect_error(code, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except sv.BookingError as e:
        assert e.code == code, f"kutilgan kod {code}, keldi {e.code}: {e.message}"
        return
    raise AssertionError(f"{code} xatosi kutilgan edi, lekin xato bo'lmadi")


future = (sv.now() + timedelta(days=365)).strftime("%Y-%m-%d")
tomorrow = (sv.now() + timedelta(days=1)).strftime("%Y-%m-%d")

# ---- tayyorgarlik ----
d1 = sv.add_district("Tuman A")["id"]
d2 = sv.add_district("Tuman B")["id"]
s1 = sv.add_salon("Salon 1", "barbershop", d1, "Manzil 1", open_time="09:00", close_time="18:00", paid_until=future)["id"]
s2 = sv.add_salon("Salon 2", "barbershop", d1, "Manzil 2", open_time="09:00", close_time="18:00", paid_until=future)["id"]
s3 = sv.add_salon("Salon 3", "barbershop", d2, "Manzil 3", paid_until=future)["id"]
s4 = sv.add_salon("Salon 4 (to'lamagan)", "barbershop", d1, "Manzil 4")["id"]
m1 = sv.add_master(s1, "Usta 1")["id"]
m2 = sv.add_master(s2, "Usta 2")["id"]
m3 = sv.add_master(s3, "Usta 3")["id"]
m4 = sv.add_master(s4, "Usta 4")["id"]
sv1 = sv.add_service(m1, "Soch olish", 60, 50000)["id"]
sv2 = sv.add_service(m2, "Soch olish", 30, 40000)["id"]
sv3 = sv.add_service(m3, "Soch olish", 30, 40000)["id"]
sv4 = sv.add_service(m4, "Soch olish", 30, 40000)["id"]

# ---- 1. bo'sh vaqtlar ----
slots = sv.get_free_slots(m1, sv1, tomorrow)["slots"]
assert len(slots) == 17 and slots[0] == "09:00" and slots[-1] == "17:00", slots
print("1. bo'sh vaqtlar to'g'ri hisoblanadi")

# ---- 2. bron qilish va vaqt yo'qolishi ----
b = sv.create_booking(m1, sv1, tomorrow, "10:00", "Ali Valiyev", "+998901234567", client_tg_id=111)
assert b["booking_no"].startswith("BQ-") and b["status"] == "booked"
slots = sv.get_free_slots(m1, sv1, tomorrow)["slots"]
assert "09:00" in slots and "11:00" in slots
assert not {"09:30", "10:00", "10:30"} & set(slots), slots
print("2. bron qilindi:", b["booking_no"], "- band vaqtlar ro'yxatdan chiqdi")

# ---- 3. ikki marta bron himoyasi ----
expect_error("slot_taken", sv.create_booking, m1, sv1, tomorrow, "10:00", "Vali", "+998901112233")
expect_error("slot_taken", sv.create_booking, m1, sv1, tomorrow, "10:30", "Vali", "+998901112233")
print("3. bir xil va ustma-ust vaqtga bron rad etildi")

# ---- 4. bir vaqtda 8 kishi (parallel) ----
results = []
barrier = threading.Barrier(8)


def worker(i):
    barrier.wait()
    try:
        sv.create_booking(m1, sv1, tomorrow, "14:00", f"Mijoz {i}", "+99890123456" + str(i % 10))
        results.append("ok")
    except sv.BookingError as e:
        results.append(e.code)


threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
assert results.count("ok") == 1 and results.count("slot_taken") == 7, results
print("4. 8 kishi bir vaqtda urindi: 1 ta muvaffaqiyatli, 7 tasi rad etildi")

# ---- 5. noto'g'ri ma'lumotlar ----
expect_error("invalid", sv.create_booking, m1, sv1, tomorrow, "18:00", "Ali", "+998901234567")   # ish vaqtidan tashqari
expect_error("invalid", sv.create_booking, m1, sv1, tomorrow, "17:30", "Ali", "+998901234567")   # 60 daqiqa sig'maydi
expect_error("invalid", sv.create_booking, m1, sv1, tomorrow, "09:15", "Ali", "+998901234567")   # katakka tushmaydi
expect_error("invalid", sv.create_booking, m1, sv1, "2020-01-01", "10:00", "Ali", "+998901234567")  # o'tgan sana
expect_error("invalid", sv.create_booking, m1, sv1, tomorrow, "12:00", "Ali", "123")             # telefon noto'g'ri
expect_error("not_found", sv.create_booking, m1, sv2, tomorrow, "12:00", "Ali", "+998901234567")  # xizmat boshqa ustaniki
print("5. noto'g'ri so'rovlar rad etildi")

# ---- 6. yaqin atrofdagi bo'sh joylar ----
near = sv.nearby_free(d1, tomorrow, 30)
ids = {x["master_id"] for x in near}
assert ids == {m1, m2}, ids          # m3 boshqa tumanda, m4 to'lamagan
near = sv.nearby_free(d1, tomorrow, 30, exclude_master_id=m1)
assert [x["master_id"] for x in near] == [m2]
assert near[0]["address"] == "Manzil 2" and near[0]["slots"][0] == "09:00"
print("6. yaqin atrof: faqat shu tuman va to'lagan ustalar chiqadi")

# ---- 7. bekor qilish ----
expect_error("forbidden", sv.cancel_booking, b["booking_no"], 999)
expect_error("forbidden", sv.cancel_booking, b["booking_no"], None)
assert sv.cancel_booking(b["booking_no"], 111)["status"] == "cancelled"
assert "10:00" in sv.get_free_slots(m1, sv1, tomorrow)["slots"]
expect_error("invalid", sv.cancel_booking, b["booking_no"], 111)
print("7. bekor qilish: begona rad etildi, egasi bekor qildi, vaqt bo'shadi")

# ---- 8. reyting ----
b2 = sv.create_booking(m1, sv1, tomorrow, "11:00", "Ali Valiyev", "+998901234567", client_tg_id=111)
expect_error("invalid", sv.set_booking_status, b2["booking_no"], "done")      # hali boshlanmagan
expect_error("invalid", sv.add_review, b2["booking_no"], 111, 5)              # hali tugamagan


def move_to_past(booking_no):
    c = db.connect()
    c.execute("UPDATE bookings SET start_at='2020-01-01 10:00', end_at='2020-01-01 11:00' "
              "WHERE booking_no=?", (booking_no,))
    c.close()


move_to_past(b2["booking_no"])
assert sv.set_booking_status(b2["booking_no"], "done")["status"] == "done"
expect_error("forbidden", sv.add_review, b2["booking_no"], 222, 5)
expect_error("invalid", sv.add_review, b2["booking_no"], 111, 6)
sv.add_review(b2["booking_no"], 111, 5, "Zo'r usta")
expect_error("invalid", sv.add_review, b2["booking_no"], 111, 4)               # ikkinchi marta

b3 = sv.create_booking(m1, sv1, tomorrow, "13:00", "Vali Karimov", "+998907654321", client_tg_id=222)
move_to_past(b3["booking_no"])
sv.set_booking_status(b3["booking_no"], "done")
sv.add_review(b3["booking_no"], 222, 4)

salon = [x for x in sv.list_salons(district_id=d1) if x["id"] == s1][0]
assert salon["rating"] == 4.5 and salon["reviews_count"] == 2, salon
master = sv.list_masters(s1)[0]
assert master["rating"] == 4.5 and master["services"][0]["id"] == sv1
reviews = sv.list_reviews(m1)
assert len(reviews) == 2 and reviews[0]["client_name"] == "Vali"
print("8. reyting: faqat tugagan bronga, bir marta; o'rtacha 4.5")

# ---- 9. abonent to'lovi ----
assert s4 not in [x["id"] for x in sv.list_salons()]
expect_error("not_found", sv.create_booking, m4, sv4, tomorrow, "10:00", "Ali", "+998901234567")
sv.set_paid_until("master", m4, future)
assert s4 in [x["id"] for x in sv.list_salons()]
sv.create_booking(m4, sv4, tomorrow, "10:00", "Ali", "+998901234567")
print("9. abonent to'lamaganlar ko'rinmaydi; to'lagach ko'rinadi va bron olinadi")

# ---- 10. xizmati yo'q usta yaqin atrofda chiqmaydi; "Bronlarim" ----
s5 = sv.add_salon("Salon 5", "barbershop", d1, "Manzil 5", open_time="09:00", close_time="18:00", paid_until=future)["id"]
m5 = sv.add_master(s5, "Usta 5 (xizmatsiz)")["id"]
assert m5 not in [x["master_id"] for x in sv.nearby_free(d1, tomorrow, 30)]

mine = sv.list_client_bookings(111)
assert len(mine) == 2
by_no = {x["booking_no"]: x for x in mine}
assert by_no[b2["booking_no"]]["reviewed"] is True and by_no[b["booking_no"]]["status"] == "cancelled"
assert "client_phone" not in mine[0] and "client_name" not in mine[0]
assert sv.list_client_bookings(424242) == []
expect_error("invalid", sv.list_client_bookings, None)
print("10. xizmatsiz usta yaqin atrofda chiqmaydi; 'Bronlarim' faqat o'ziniki va shaxsiy ma'lumotsiz")

# ---- 11. admin: xizmatni yashirish, tahrirlash, o'chirish ----
m6 = sv.add_master(s1, "Usta 6")["id"]
sv6 = sv.add_service(m6, "Noto'g'ri xizmat", 30, 10000)["id"]

def m6_services():
    return [x for x in sv.list_masters(s1) if x["id"] == m6][0]["services"]

sv.set_service_active(sv6, False)
assert sv6 not in [x["id"] for x in m6_services()]
assert sv6 in [x["id"] for x in sv.admin_list_services(m6)]
expect_error("not_found", sv.get_free_slots, m6, sv6, tomorrow)

sv.set_service_active(sv6, True)
assert sv6 in [x["id"] for x in m6_services()]

sv.update_service(sv6, name="Manikyur", price=55000)
updated = [x for x in sv.admin_list_services(m6) if x["id"] == sv6][0]
assert updated["name"] == "Manikyur" and updated["price"] == 55000 and updated["duration_min"] == 30
expect_error("invalid", sv.update_service, sv6)
expect_error("not_found", sv.update_service, 999999, name="x")

sv.create_booking(m6, sv6, tomorrow, "09:00", "Mijoz", "+998901234567")
expect_error("invalid", sv.delete_service, sv6)   # bron qilingan, o'chirib bo'lmaydi
sv7 = sv.add_service(m6, "Vaqtincha", 30, 1000)["id"]
sv.delete_service(sv7)                             # bronsiz xizmat o'chadi
expect_error("not_found", sv.delete_service, sv7)
print("11. admin: xizmatni yashirish/qaytarish, tahrirlash va o'chirish to'g'ri ishlaydi")

# ---- 12. admin: ro'yxatlar va salon/ustani yashirish ----
salons = sv.admin_list_salons()
assert any(x["id"] == s4 and x["is_active"] == 1 for x in salons)
masters = sv.admin_list_masters(s1)
assert m6 in [x["id"] for x in masters]

sv.set_active("master", m6, False)
assert m6 not in [x["id"] for x in sv.list_masters(s1)]
assert any(x["id"] == m6 and x["is_active"] == 0 for x in sv.admin_list_masters(s1))
sv.set_active("master", m6, True)
assert m6 in [x["id"] for x in sv.list_masters(s1)]
print("12. admin: salon/usta ro'yxatlari va yashirish/qaytarish to'g'ri ishlaydi")

print("\nHAMMA TESTLAR O'TDI")
