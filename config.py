"""config.py - MySQL (XAMPP) connection settings for Pet Clinic (Flask)."""
import os

import pymysql
import pymysql.cursors

DB_HOST = os.environ.get("PETCLINIC_DB_HOST", "localhost")
DB_NAME = os.environ.get("PETCLINIC_DB_NAME", "petclinic")
DB_USER = os.environ.get("PETCLINIC_DB_USER", "root")
DB_PASS = os.environ.get("PETCLINIC_DB_PASS", "")  # XAMPP default: empty password

# Dev fallback only: set PETCLINIC_SECRET_KEY outside this machine.
SECRET_KEY = os.environ.get("PETCLINIC_SECRET_KEY", "petclinic-dev-secret-key")


def get_connection():
    """Return a new pymysql connection (DictCursor). Raises on failure."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
