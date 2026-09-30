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

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      full_name VARCHAR(100) NOT NULL,
      username VARCHAR(50) NOT NULL UNIQUE,
      email VARCHAR(100) NOT NULL UNIQUE,
      password VARCHAR(255) NOT NULL,
      role ENUM('admin', 'vet', 'staff', 'owner') NOT NULL DEFAULT 'owner',
      phone VARCHAR(20) NULL,
      address TEXT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS pets (
      id INT AUTO_INCREMENT PRIMARY KEY,
      owner_id INT NOT NULL,
      name VARCHAR(50) NOT NULL,
      species ENUM('Dog', 'Cat', 'Bird', 'Rabbit', 'Hamster', 'Reptile', 'Other') NOT NULL,
      breed VARCHAR(50) NULL,
      age INT NULL,
      gender ENUM('Male', 'Female') NULL,
      weight DECIMAL(5,2) NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_pets_owner FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
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
      owner_id INT NOT NULL,
      vet_id INT NULL,
      appointment_date DATE NOT NULL,
      appointment_time TIME NOT NULL,
      reason TEXT NULL,
      status ENUM('pending', 'approved', 'completed', 'cancelled')
        NOT NULL DEFAULT 'pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_appt_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_appt_owner FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_appt_vet FOREIGN KEY (vet_id)
        REFERENCES users (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS clinic_queue (
      id INT AUTO_INCREMENT PRIMARY KEY,
      appointment_id INT NOT NULL UNIQUE,
      pet_id INT NOT NULL,
      owner_id INT NOT NULL,
      vet_id INT NULL,
      queue_number INT NOT NULL,
      queue_date DATE NOT NULL,
      status ENUM('waiting', 'serving', 'done', 'skipped') NOT NULL DEFAULT 'waiting',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_queue_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_owner FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_queue_vet FOREIGN KEY (vet_id)
        REFERENCES users (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS consultations (
      id INT AUTO_INCREMENT PRIMARY KEY,
      appointment_id INT NOT NULL,
      pet_id INT NOT NULL,
      vet_id INT NOT NULL,
      diagnosis TEXT NOT NULL,
      treatment TEXT NULL,
      notes TEXT NULL,
      consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_consult_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_consult_pet FOREIGN KEY (pet_id)
        REFERENCES pets (id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_consult_vet FOREIGN KEY (vet_id)
        REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS prescriptions_treatments (
      id INT AUTO_INCREMENT PRIMARY KEY,
      consultation_id INT NOT NULL,
      inventory_id INT NULL,
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
      owner_id INT NOT NULL,
      appointment_id INT NULL,
      consultation_id INT NULL,
      amount DECIMAL(10,2) NOT NULL,
      status ENUM('unpaid', 'paid', 'cancelled') NOT NULL DEFAULT 'unpaid',
      issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_inv_owner FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE,
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
    print(f"Seeded {seeded} account(s): Admin / Staff (password 123).")


if __name__ == "__main__":
    main()
