"""database/migrate_clients_vets.py - One-shot migration: owners/vets out of users.

  users  -> logins only (admin/staff)
  owners -> new clients table (pets/appointments/queue/invoices retargeted)
  vets   -> new vets directory (consult/appt/queue vet_id retargeted;
            legacy consultation vet_ids [staff/admin user ids] -> Duty Vet)

Run once:  python database/migrate_clients_vets.py
Idempotent: exits quietly if already migrated.
"""
import sys

import pymysql

DB_HOST = "localhost"
DB_NAME = "petclinic"
DB_USER = "root"
DB_PASS = ""  # XAMPP default

# (table, fk-target column, position clause, fk name, fk sql)
OWNER_TABLES = [
    ("pets", "AFTER id",
     "fk_pets_client",
     "FOREIGN KEY (client_id) REFERENCES clients (id)"
     " ON DELETE CASCADE ON UPDATE CASCADE"),
    ("appointments", "AFTER pet_id",
     "fk_appt_client",
     "FOREIGN KEY (client_id) REFERENCES clients (id)"
     " ON DELETE CASCADE ON UPDATE CASCADE"),
    ("clinic_queue", "AFTER pet_id",
     "fk_queue_client",
     "FOREIGN KEY (client_id) REFERENCES clients (id)"
     " ON DELETE CASCADE ON UPDATE CASCADE"),
    ("invoices", "AFTER id",
     "fk_inv_client",
     "FOREIGN KEY (client_id) REFERENCES clients (id)"
     " ON DELETE CASCADE ON UPDATE CASCADE"),
]

VET_FKS = [
    ("appointments", "fk_appt_vet",
     "FOREIGN KEY (vet_id) REFERENCES vets (id)"
     " ON DELETE SET NULL ON UPDATE CASCADE"),
    ("clinic_queue", "fk_queue_vet",
     "FOREIGN KEY (vet_id) REFERENCES vets (id)"
     " ON DELETE SET NULL ON UPDATE CASCADE"),
    ("consultations", "fk_consult_vet",
     "FOREIGN KEY (vet_id) REFERENCES vets (id)"
     " ON DELETE CASCADE ON UPDATE CASCADE"),
]


def col_exists(cur, db, table, column):
    cur.execute("SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS"
                " WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                (db, table, column))
    return cur.fetchone()["c"] > 0


def fks_on(cur, db, table, column):
    """Constraint names on table.column that reference the users table."""
    cur.execute(
        "SELECT CONSTRAINT_NAME AS n FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE"
        " WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s"
        " AND REFERENCED_TABLE_NAME='users'", (db, table, column))
    return [r["n"] for r in cur.fetchall()]


def main():
    db_name = sys.argv[1] if len(sys.argv) > 1 else DB_NAME
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                           database=db_name, charset="utf8mb4", autocommit=True,
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            if not col_exists(cur, db_name, "pets", "owner_id"):
                cur.execute("SELECT COUNT(*) AS c FROM users"
                            " WHERE role IN ('owner','vet')")
                if cur.fetchone()["c"] == 0:
                    print("Already migrated: no owner columns, no owner/vet users.")
                    return
            # Fresh-DB guard: setup_db.py schema already applied (no owner cols).
            if not col_exists(cur, db_name, "pets", "owner_id"):
                print("No owner columns to migrate; role cleanup only.")
            else:
                # ---- 1. Ensure clients + vets tables ----
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS clients (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      full_name VARCHAR(100) NOT NULL,
                      phone VARCHAR(20) NOT NULL UNIQUE,
                      address TEXT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS vets (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      full_name VARCHAR(100) NOT NULL,
                      specialty VARCHAR(100) NULL,
                      phone VARCHAR(20) NULL,
                      is_active TINYINT(1) NOT NULL DEFAULT 1,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
                cur.execute("SELECT id FROM vets WHERE full_name='Duty Veterinarian'"
                            " LIMIT 1")
                row = cur.fetchone()
                if row:
                    duty_vet = row["id"]
                else:
                    cur.execute("INSERT INTO vets (full_name, specialty) VALUES"
                                " ('Duty Veterinarian', 'General')")
                    duty_vet = cur.lastrowid
                print(f"Duty Vet id={duty_vet}")

                # ---- 2. Owners -> clients ----
                cur.execute("SELECT id, full_name, phone, address FROM users"
                            " WHERE role='owner'")
                owners = cur.fetchall()
                idmap = {}
                for o in owners:
                    cur.execute("SELECT id FROM clients WHERE phone=%s LIMIT 1",
                                (o["phone"],))
                    hit = cur.fetchone()
                    if hit:
                        idmap[o["id"]] = hit["id"]
                    else:
                        cur.execute("INSERT INTO clients (full_name, phone, address)"
                                    " VALUES (%s,%s,%s)",
                                    (o["full_name"], o["phone"], o["address"]))
                        idmap[o["id"]] = cur.lastrowid
                print(f"Owners -> clients: {len(idmap)} mapped")

                # ---- 3. Retarget owner_id -> client_id ----
                for table, pos, fk_name, fk_sql in OWNER_TABLES:
                    for fk in fks_on(cur, db_name, table, "owner_id"):
                        cur.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {fk}")
                    if not col_exists(cur, db_name, table, "client_id"):
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN client_id INT"
                                    f" NOT NULL {pos}")
                    for old_id, new_id in idmap.items():
                        cur.execute(f"UPDATE {table} SET client_id=%s"
                                    f" WHERE owner_id=%s", (new_id, old_id))
                    cur.execute(f"ALTER TABLE {table} DROP COLUMN owner_id")
                    cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {fk_name}"
                                f" {fk_sql}")
                    print(f"{table}: owner_id -> client_id done")

                # ---- 4. Retarget vet FKs to vets ----
                for table, fk_name, fk_sql in VET_FKS:
                    for fk in fks_on(cur, db_name, table, "vet_id"):
                        cur.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {fk}")
                    if table == "consultations":
                        cur.execute(f"UPDATE {table} SET vet_id=%s", (duty_vet,))
                        print(f"{table}: legacy vet_ids -> Duty Vet")
                    else:
                        cur.execute(f"UPDATE {table} SET vet_id=%s"
                                    f" WHERE vet_id IS NOT NULL", (duty_vet,))
                    cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {fk_name}"
                                f" {fk_sql}")
                    print(f"{table}: vet_id -> vets done")

            # ---- 5. Users cleanup ----
            cur.execute("SELECT id, username FROM users WHERE role='vet'")
            strays = cur.fetchall()
            for s in strays:
                cur.execute("UPDATE users SET role='staff' WHERE id=%s", (s["id"],))
                print(f"WARNING: vet user '{s['username']}' converted to staff"
                      f" (review access).")
            cur.execute("DELETE FROM users WHERE role='owner'")
            print(f"Deleted owner login rows.")
            cur.execute("ALTER TABLE users MODIFY COLUMN role"
                        " ENUM('admin','staff') NOT NULL DEFAULT 'staff'")
            print("users.role is now ENUM('admin','staff').")

            # ---- 6. Verify ----
            for t in ("users", "clients", "vets", "pets", "appointments",
                      "clinic_queue", "consultations", "invoices"):
                cur.execute(f"SELECT COUNT(*) AS c FROM {t}")
                print(f"  {t}: {cur.fetchone()['c']} rows")
    finally:
        conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
