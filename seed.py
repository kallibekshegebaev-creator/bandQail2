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
salon_d = svc.add_salon("Namuna Komp Klub", "computer_club", d1, "Namuna ko'cha 4", "+998900000004",
                        "09:00", "23:00", paid)["id"]
salon_e = svc.add_salon("Namuna Billiard", "billiard_club", d2, "Namuna ko'cha 5", "+998900000005",
                        "10:00", "23:59", paid)["id"]

BARBER_SERVICES = [("Soch olish", 30, 40000), ("Soch + soqol", 60, 70000)]
BEAUTY_SERVICES = [("Manikyur", 60, 60000), ("Pedikyur", 75, 80000), ("Depilyatsiya", 45, 90000)]
# Klublarda "usta" = stol/kompyuter, "xizmat" = soatlik ijara narxi
HOURLY_SERVICES = [("1 soat", 60, 15000), ("2 soat", 120, 28000), ("3 soat", 180, 40000)]

for salon_id, master_name, kind in [(salon_a, "Usta Bir", "barbershop"),
                                    (salon_b, "Usta Ikki", "barbershop"),
                                    (salon_c, "Usta Uch", "beauty")]:
    master_id = svc.add_master(salon_id, master_name)["id"]
    for name, duration, price in (BARBER_SERVICES if kind == "barbershop" else BEAUTY_SERVICES):
        svc.add_service(master_id, name, duration, price)

for salon_id, resource_name in [(salon_d, "Kompyuter 1"), (salon_d, "Kompyuter 2")]:
    resource_id = svc.add_master(salon_id, resource_name)["id"]
    for name, duration, price in HOURLY_SERVICES:
        svc.add_service(resource_id, name, duration, price)

for salon_id, resource_name in [(salon_e, "Stol 1"), (salon_e, "Stol 2")]:
    resource_id = svc.add_master(salon_id, resource_name)["id"]
    for name, duration, price in HOURLY_SERVICES:
        svc.add_service(resource_id, name, duration, price)

print("Namunaviy ma'lumotlar qo'shildi: 2 tuman, 5 salon "
      "(2 sartaroshxona, 1 go'zallik saloni, 1 kompyuter klubi, 1 billiard klubi), 7 resurs.")
