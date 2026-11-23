"""Sinov uchun namunaviy ma'lumotlar. Ishga tushirish: python seed.py
(Faqat baza bo'sh bo'lsa ishlaydi. Haqiqiy salonlarni keyin admin orqali qo'shasiz.)"""
from datetime import timedelta

import services as svc
from db import init_db

init_db()

if svc.list_districts():
    print("Bazada ma'lumot bor, seed o'tkazib yuborildi.")
    raise SystemExit

paid = (svc.now() + timedelta(days=365)).strftime("%Y-%m-%d")

d1 = svc.add_district("1-tuman (namuna)")["id"]
d2 = svc.add_district("2-tuman (namuna)")["id"]

salon_a = svc.add_salon("Namuna Barber A", "barbershop", d1, "Namuna ko'cha 1", "+998900000001",
                        "09:00", "20:00", paid)["id"]
salon_b = svc.add_salon("Namuna Barber B", "barbershop", d1, "Namuna ko'cha 2", "+998900000002",
                        "10:00", "21:00", paid)["id"]
salon_c = svc.add_salon("Namuna Go'zallik", "beauty", d2, "Namuna ko'cha 3", "+998900000003",
                        "09:00", "19:00", paid)["id"]

BARBER_SERVICES = [("Soch olish", 30, 40000), ("Soch + soqol", 60, 70000)]
BEAUTY_SERVICES = [("Manikyur", 60, 60000), ("Pedikyur", 75, 80000), ("Depilyatsiya", 45, 90000)]

for salon_id, master_name, kind in [(salon_a, "Usta Bir", "barbershop"),
                                    (salon_b, "Usta Ikki", "barbershop"),
                                    (salon_c, "Usta Uch", "beauty")]:
    master_id = svc.add_master(salon_id, master_name)["id"]
    for name, duration, price in (BARBER_SERVICES if kind == "barbershop" else BEAUTY_SERVICES):
        svc.add_service(master_id, name, duration, price)

print("Namunaviy ma'lumotlar qo'shildi: 2 tuman, 3 salon (2 sartaroshxona, 1 go'zallik saloni), 3 usta.")
