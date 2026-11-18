"""database/setup_db.py - Portable Pet Clinic database setup (XAMPP MySQL).

New-device flow:
    1. Start MySQL in the XAMPP Control Panel.
    2. pip install -r requirements.txt
    3. python database/setup_db.py
    4. $env:PORT=5001; python app.py

Safe to re-run: uses IF NOT EXISTS and seeds only when the users table is empty.
The `if __name__ == "__main__":` guard means importing this module
(e.g. `import database.setup_db`) NEVER touches the database.
"""
import sys

import bcrypt
import pymysql

DB_HOST = "localhost"
DB_NAME = "petclinic"
DB_USER = "root"
DB_PASS = ""  # XAMPP default

# Seed accounts: (full_name, username, email, plain_password, role, phone)
SEEDS = [
    ("System Admin", "Admin", "admin@clinic.com", "123", "admin", "09170000001"),
    ("Clinic Staff", "Staff", "staff@clinic.com", "123", "staff", "09170000002"),
]

# Fixed service menu: (name, fee, duration, inclusions, sort_order).
# Fees are mid-range 2026 Philippine clinic rates (consult 300-800, vaccines
# 200-950, grooming 400-1100 by size, boarding 150-900/night, emergency fees
# 500-2500). Editable later in Admin -> Services.
SERVICE_SEEDS = [
    ("General Checkup", 500.00, "30 min",
     "Physical examination, weight and temperature check, health assessment,"
     " care advice.", 1),
    ("Vaccination", 600.00, "20 min",
     "Vaccine dose, quick health check before the shot, vaccination record.", 2),
    ("Grooming", 500.00, "60 min",
     "Bath, blow-dry, haircut or trim, nail trim, ear cleaning.", 3),
    ("Boarding", 450.00, "Per night",
     "Cage or room, food and water, litter for cats, daily cleaning and care.", 4),
    ("Surgery Consult", 800.00, "30 min",
     "Pre-surgery assessment, anesthesia plan, procedure and cost estimate.", 5),
    ("Emergency", 1000.00, "30 min",
     "Immediate triage and first aid, priority attention; treatment billed"
     " separately.", 6),
]

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      full_name VARCHAR(100) NOT NULL,
      username VARCHAR(50) NOT NULL UNIQUE,
      email VARCHAR(100) NOT NULL UNIQUE,
      password VARCHAR(255) NOT NULL,
      role ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
      status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'approved',
      phone VARCHAR(20) NULL,
      address TEXT NULL,
      avatar VARCHAR(255) NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS clients (
      id INT AUTO_INCREMENT PRIMARY KEY,
      full_name VARCHAR(50) NOT NULL,
      phone VARCHAR(20) NOT NULL UNIQUE,
      address TEXT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS vets (
      id INT AUTO_INCREMENT PRIMARY KEY,
      full_name VARCHAR(100) NOT NULL,
      specialty VARCHAR(100) NULL,
      phone VARCHAR(20) NULL,
      email VARCHAR(100) NULL,
      license_no VARCHAR(50) NULL,
      bio TEXT NULL,
      photo VARCHAR(255) NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS services (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(80) NOT NULL UNIQUE,
      fee DECIMAL(10,2) NOT NULL DEFAULT 0,
      duration VARCHAR(40) NULL,
      inclusions TEXT NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      sort_order INT NOT NULL DEFAULT 0,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS pets (
      id INT AUTO_INCREMENT PRIMARY KEY,
      client_id INT NOT NULL,
      name VARCHAR(50) NOT NULL,
      species ENUM('Dog', 'Cat', 'Bird', 'Rabbit', 'Hamster', 'Reptile', 'Other') NOT NULL,
      breed VARCHAR(50) NULL,
      age INT NULL,
      gender ENUM('Male', 'Female') NULL,
      weight DECIMAL(5,2) NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_pets_client FOREIGN KEY (client_id)
        REFERENCES clients (id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS inventory (
      id INT AUTO_INCREMENT PRIMARY KEY,
      item_name VARCHAR(100) NOT NULL,
      category ENUM('Medicine', 'Vaccine', 'Food', 'Equipment', 'Hygiene', 'Other')
        NOT NULL DEFAULT 'Medicine',
      quantity INT NOT NULL DEFAULT 0,
      price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
      expiry_date DATE NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS appointments (
      id INT AUTO_INCREMENT PRIMARY KEY,
      pet_id INT NOT NULL,
      client_id INT NOT NULL,
      vet_id INT NULL,
      appointment_date DATE NOT NULL,
      appointment_time TIME NOT NULL,
      reason TEXT NULL,
      source ENUM('guest', 'walkin') NOT NULL DEFAULT 'guest',
      status ENUM('pending', 'approved', 'completed', 'cancelled')
        NOT NULL DEFAULT 'pending',
      auto_queue TINYINT(1) NOT NULL DEFAULT 1,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_appt_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_appt_client FOREIGN KEY (client_id)
        REFERENCES clients (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_appt_vet FOREIGN KEY (vet_id)
        REFERENCES vets (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS clinic_queue (
      id INT AUTO_INCREMENT PRIMARY KEY,
      appointment_id INT NOT NULL UNIQUE,
      pet_id INT NOT NULL,
      client_id INT NOT NULL,
      vet_id INT NULL,
      queue_number INT NOT NULL,
      queue_date DATE NOT NULL,
      status ENUM('waiting', 'serving', 'done', 'skipped') NOT NULL DEFAULT 'waiting',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE KEY uq_queue_day_number (queue_date, queue_number),
      CONSTRAINT fk_queue_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_client FOREIGN KEY (client_id)
        REFERENCES clients (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_vet FOREIGN KEY (vet_id)
        REFERENCES vets (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS consultations (
      id INT AUTO_INCREMENT PRIMARY KEY,
      appointment_id INT NOT NULL,
      pet_id INT NOT NULL,
      vet_id INT NOT NULL,
      service_id INT NULL,
      diagnosis TEXT NOT NULL,
      treatment TEXT NULL,
      notes TEXT NULL,
      consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_consult_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_consult_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_consult_vet FOREIGN KEY (vet_id)
        REFERENCES vets (id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS prescriptions_treatments (
      id INT AUTO_INCREMENT PRIMARY KEY,
      consultation_id INT NOT NULL,
      inventory_id INT NULL,
      medicine_name VARCHAR(120) NULL,
      dosage VARCHAR(100) NULL,
      quantity_used INT NOT NULL DEFAULT 1,
      instructions TEXT NULL,
      CONSTRAINT fk_rx_consult FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_rx_inventory FOREIGN KEY (inventory_id)
        REFERENCES inventory (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS invoices (
      id INT AUTO_INCREMENT PRIMARY KEY,
      client_id INT NOT NULL,
      appointment_id INT NULL,
      consultation_id INT NULL,
      amount DECIMAL(10,2) NOT NULL,
      status ENUM('unpaid', 'paid', 'cancelled') NOT NULL DEFAULT 'unpaid',
      issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_inv_client FOREIGN KEY (client_id)
        REFERENCES clients (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_inv_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments (id) ON DELETE SET NULL ON UPDATE CASCADE,
      CONSTRAINT fk_inv_consult FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


def run_setup(db_name=DB_NAME):
    """Create database, tables and seed accounts. Returns (tables, seeded)."""
    server = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                             charset="utf8mb4", autocommit=True)
    try:
        with server.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}`"
                " CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    finally:
        server.close()

    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                           database=db_name, charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            for stmt in SCHEMA:
                cur.execute(stmt)
            # Lightweight upgrade for DBs created before the source column existed.
            cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS"
                        " WHERE TABLE_SCHEMA=%s AND TABLE_NAME='appointments'"
                        " AND COLUMN_NAME='source'", (db_name,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE appointments ADD COLUMN source"
                            " ENUM('guest','walkin') NOT NULL DEFAULT 'guest'"
                            " AFTER reason")
                print("Migrated: appointments.source column added.")
            # Accounts predate the approval flow: everyone active stays approved.
            cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS"
                        " WHERE TABLE_SCHEMA=%s AND TABLE_NAME='users'"
                        " AND COLUMN_NAME='status'", (db_name,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE users ADD COLUMN status"
                            " ENUM('pending','approved','rejected') NOT NULL"
                            " DEFAULT 'approved' AFTER role")
                print("Migrated: users.status column added (all existing approved).")
            # Queue tickets must be unique per day (guards concurrent adds).
            cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS"
                        " WHERE TABLE_SCHEMA=%s AND TABLE_NAME='clinic_queue'"
                        " AND INDEX_NAME='uq_queue_day_number'", (db_name,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE clinic_queue ADD UNIQUE KEY"
                            " uq_queue_day_number (queue_date, queue_number)")
                print("Migrated: unique queue number per day.")
            # Settings/upload columns (avatars, vet profiles, free-text medicine).
            upgrades = [
                ("users", "avatar", "ALTER TABLE users ADD COLUMN avatar"
                 " VARCHAR(255) NULL AFTER address"),
                ("vets", "photo", "ALTER TABLE vets ADD COLUMN photo"
                 " VARCHAR(255) NULL AFTER phone"),
                ("vets", "email", "ALTER TABLE vets ADD COLUMN email"
                 " VARCHAR(100) NULL AFTER phone"),
                ("vets", "license_no", "ALTER TABLE vets ADD COLUMN license_no"
                 " VARCHAR(50) NULL AFTER email"),
                ("vets", "bio", "ALTER TABLE vets ADD COLUMN bio"
                 " TEXT NULL AFTER license_no"),
                ("prescriptions_treatments", "medicine_name",
                 "ALTER TABLE prescriptions_treatments ADD COLUMN medicine_name"
                 " VARCHAR(120) NULL AFTER inventory_id"),
                ("appointments", "auto_queue",
                 "ALTER TABLE appointments ADD COLUMN auto_queue"
                 " TINYINT(1) NOT NULL DEFAULT 1 AFTER status"),
                ("consultations", "service_id",
                 "ALTER TABLE consultations ADD COLUMN service_id INT NULL"
                 " AFTER vet_id"),
            ]
            for table, column, ddl in upgrades:
                cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS"
                            " WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s"
                            " AND COLUMN_NAME=%s", (db_name, table, column))
                if cur.fetchone()[0] == 0:
                    cur.execute(ddl)
                    print(f"Migrated: {table}.{column} column added.")
            cur.execute("SELECT COUNT(*) FROM users")
            seeded = 0
            if cur.fetchone()[0] == 0:
                for full_name, username, email, plain, role, phone in SEEDS:
                    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
                    cur.execute(
                        "INSERT INTO users (full_name, username, email, password, role, phone)"
                        " VALUES (%s,%s,%s,%s,%s,%s)",
                        (full_name, username, email, hashed, role, phone))
                    seeded += 1
            cur.execute("SELECT COUNT(*) FROM vets")
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO vets (full_name, specialty) VALUES"
                    " ('Duty Veterinarian', 'General')")
                seeded += 1
            cur.execute("SELECT COUNT(*) FROM services")
            if cur.fetchone()[0] == 0:
                for name, fee, duration, inclusions, order in SERVICE_SEEDS:
                    cur.execute(
                        "INSERT INTO services (name, fee, duration, inclusions,"
                        " sort_order) VALUES (%s,%s,%s,%s,%s)",
                        (name, fee, duration, inclusions, order))
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return tables, seeded


def main():
    try:
        db_name = sys.argv[1] if len(sys.argv) > 1 else DB_NAME
        tables, seeded = run_setup(db_name)
    except pymysql.MySQLError as e:
        print(f"Setup failed: {e}\nIs XAMPP MySQL running?")
        raise SystemExit(1)
    print(f"Database `{db_name}` ready: {len(tables)} tables ({', '.join(sorted(tables))}).")
    print(f"Seeded {seeded} account(s): Admin / Staff (password 123)"
          f" + Duty Veterinarian.")


if __name__ == "__main__":
    main()
