"""database/demo_seed.py - Clean test rows + inject curated demo data for checking.

Run:  python database/demo_seed.py
Rerunnable: wipes clients/vets/transactional rows first, keeps Admin/Staff.

Demo set:
  vets: Duty Veterinarian (General), Dra. Ana Reyes (Surgery),
        Dr. Mark Villanueva (Dermatology) — all active
  clients: Maria Santos (09171234567), Juan Dela Cruz (09172345678)
  pets: Bantay (Dog, Maria), Mingming (Cat, Maria), Tweety (Bird, Juan)
  appointments: 1x pending guest (Bantay, tomorrow, General Checkup),
                1x approved (Mingming, today, Vaccination),
                1x completed (Tweety, yesterday, Dra. Ana Reyes)
  queue: today's waiting ticket for the approved Mingming visit
  inventory: Amoxicillin 20, Rabies Vaccine 15, Dog Food 8, Syringe 5 (low)
  consults/invoices: 1x completed consult (Tweety, Dra. Ana Reyes)
                     + paid invoice P850
Live demo path left open: approve Bantay -> queue -> consult (pick vet)
-> auto-bill.
"""
from datetime import date, timedelta

import pymysql
import pymysql.cursors

DB_HOST = "localhost"
DB_NAME = "petclinic"
DB_USER = "root"
DB_PASS = ""  # XAMPP default


def get_connection():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        autocommit=True)


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ---- Wipe demo/transactional rows (FK order; Admin/Staff stay) ----
            for tbl in ("prescriptions_treatments", "invoices", "consultations",
                        "clinic_queue", "appointments", "pets", "clients",
                        "vets", "inventory"):
                cur.execute(f"DELETE FROM {tbl}")

            # ---- Vets directory ----
            cur.execute("INSERT INTO vets (full_name, specialty) VALUES"
                        " ('Duty Veterinarian', 'General')")
            duty = cur.lastrowid
            cur.execute("INSERT INTO vets (full_name, specialty, phone) VALUES"
                        " ('Ana Reyes', 'Surgery', '09171112222')")
            ana = cur.lastrowid
            cur.execute("INSERT INTO vets (full_name, specialty, phone) VALUES"
                        " ('Mark Villanueva', 'Dermatology', '09173334444')")
            cur.lastrowid  # mark; directory example

            # ---- Clients ----
            cur.execute("INSERT INTO clients (full_name, phone, address) VALUES"
                        " ('Maria Santos', '09171234567', '123 Mabini St.')")
            maria = cur.lastrowid
            cur.execute("INSERT INTO clients (full_name, phone) VALUES"
                        " ('Juan Dela Cruz', '09172345678')")
            juan = cur.lastrowid

            # ---- Pets ----
            cur.execute(
                "INSERT INTO pets (client_id, name, species, breed, age, gender)"
                " VALUES (%s,'Bantay','Dog','Aspin',3,'Male')", (maria,))
            bantay = cur.lastrowid
            cur.execute(
                "INSERT INTO pets (client_id, name, species, breed, age, gender)"
                " VALUES (%s,'Mingming','Cat','Puspin',2,'Female')", (maria,))
            mingming = cur.lastrowid
            cur.execute(
                "INSERT INTO pets (client_id, name, species, breed, age, gender)"
                " VALUES (%s,'Tweety','Bird','Parakeet',1,'Male')", (juan,))
            tweety = cur.lastrowid

            tomorrow = date.today() + timedelta(days=1)
            yesterday = date.today() - timedelta(days=1)

            # ---- Appointments ----
            cur.execute(
                "INSERT INTO appointments (pet_id, client_id, appointment_date,"
                " appointment_time, reason, source, status)"
                " VALUES (%s,%s,%s,'10:00','General Checkup','guest','pending')",
                (bantay, maria, tomorrow))
            pending_id = cur.lastrowid
            cur.execute(
                "INSERT INTO appointments (pet_id, client_id, appointment_date,"
                " appointment_time, reason, source, status)"
                " VALUES (%s,%s,CURDATE(),'09:30','Vaccination','walkin','approved')",
                (mingming, maria))
            approved_id = cur.lastrowid
            cur.execute(
                "INSERT INTO appointments (pet_id, client_id, vet_id,"
                " appointment_date,"
                " appointment_time, reason, source, status)"
                " VALUES (%s,%s,%s,%s,'11:00','General Checkup','walkin','completed')",
                (tweety, juan, ana, yesterday))
            done_id = cur.lastrowid

            # ---- Queue: today's waiting ticket for the approved visit ----
            cur.execute(
                "INSERT INTO clinic_queue (appointment_id, pet_id, client_id,"
                " queue_number, queue_date) VALUES (%s,%s,%s,1,CURDATE())",
                (approved_id, mingming, maria))

            # ---- Inventory ----
            for name, cat, qty, price in (
                    ("Amoxicillin 250mg", "Medicine", 20, 45.00),
                    ("Rabies Vaccine", "Vaccine", 15, 350.00),
                    ("Premium Dog Food 1kg", "Food", 8, 520.00),
                    ("Syringe 5ml", "Equipment", 5, 12.00)):
                cur.execute(
                    "INSERT INTO inventory (item_name, category, quantity, price)"
                    " VALUES (%s,%s,%s,%s)", (name, cat, qty, price))

            # ---- History example: consult + paid invoice for Tweety ----
            cur.execute(
                "INSERT INTO consultations (appointment_id, pet_id, vet_id,"
                " diagnosis, treatment) VALUES (%s,%s,%s,"
                " 'Healthy, mild ear mites observed', 'Ear cleaning + vitamins')",
                (done_id, tweety, ana))
            consult_id = cur.lastrowid
            cur.execute(
                "INSERT INTO invoices (client_id, appointment_id,"
                " consultation_id, amount, status)"
                " VALUES (%s,%s,%s,850.00,'paid')",
                (juan, done_id, consult_id))
            _ = duty
    finally:
        conn.close()
    print(f"Demo seed ready: 3 vets; clients Maria/Juan; pending appt"
          f" #{pending_id} (live approve path); queue ticket #1 today;"
          f" history consult (Dra. Ana Reyes) + paid P850 invoice.")


if __name__ == "__main__":
    main()
