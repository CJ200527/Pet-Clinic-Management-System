"""config.py - MySQL (XAMPP) connection settings for Pet Clinic (Flask)."""
import pymysql
import pymysql.cursors

DB_HOST = "localhost"
DB_NAME = "petclinic"
DB_USER = "root"
DB_PASS = ""  # XAMPP default: empty password

# Change this to a random value in production
SECRET_KEY = "petclinic-dev-secret-key"


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
