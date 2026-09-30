"""app.py - Pet Clinic Management System (Flask + MySQL via XAMPP)."""
from datetime import date
from functools import wraps

import bcrypt
import pymysql
from flask import Flask, flash, redirect, render_template, request, session, url_for

import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


def db():
    try:
        return config.get_connection()
    except pymysql.MySQLError as e:
        print(f"DB connection failed: {e}")
        return None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("index", auth="open"))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("index", auth="open"))
            if session.get("role") not in roles:
                flash("Access denied for your role.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def dashboard_for(role):
    if role in ("admin", "staff"):
        return url_for("admin_dashboard")  # shared dashboard: staff sees all, admin acts
    if role in ("vet",):
        return url_for("vet_dashboard")
    return url_for("client_dashboard")


def safe_next(value, default):
    """Allow only relative in-app redirects (no open-redirect)."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return default


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(dashboard_for(session.get("role", "owner")))
    vets = []
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT full_name FROM users WHERE role='vet'"
                            " ORDER BY full_name ASC")
                vets = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Landing vets failed: {e}")
        finally:
            conn.close()
    # auth: '' | 'open' (curtain auto-open) | 'failed' (curtain + error popup)
    auth = request.args.get("auth", "")
    if auth not in ("open", "failed"):
        auth = ""
    return render_template("landing.html", vets=vets, today=date.today().isoformat(),
                           auth=auth, pre_next=request.args.get("next", ""),
                           pre_service=request.args.get("service", ""),
                           pre_date=request.args.get("date", ""),
                           pre_time=request.args.get("time", ""))


# ---------------- Auth ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """No standalone page: GET bounces to the landing curtain; POST processes logins."""
    passthrough = {k: request.args.get(k, "") or request.form.get(k, "")
                   for k in ("next", "service", "date", "time")}
    if request.method == "GET":
        return redirect(url_for("index", auth="open", **{k: v for k, v in
                                                         passthrough.items() if v}))
    if "user_id" in session:
        return redirect(dashboard_for(session.get("role", "owner")))
    # Booking-bar passthrough from the landing page (?next=/client/book-appointment&service=&date=&time=)
    # Accepts query args (booking-bar GET, /login page) AND hidden form fields (curtain POST).
    nxt = passthrough["next"]
    pre_service = passthrough["service"]
    pre_date = passthrough["date"]
    pre_time = passthrough["time"]
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return redirect(url_for("index", auth="failed"))
        else:
            conn = db()
            if conn is None:
                flash("Database connection failed. Check XAMPP MySQL.", "danger")
            else:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, full_name, password, role FROM users WHERE username=%s LIMIT 1",
                            (username,),
                        )
                        user = cur.fetchone()
                    try:
                        ok = bool(user) and bcrypt.checkpw(
                            password.encode(), user["password"].encode())
                    except ValueError:
                        ok = False  # corrupt hash in DB: fail closed, never 500
                    if ok:
                        session.clear()
                        session["user_id"] = int(user["id"])
                        session["full_name"] = user["full_name"]
                        session["role"] = user["role"]
                        target = safe_next(nxt, dashboard_for(user["role"]))
                        if nxt == url_for("book_appointment"):
                            from urllib.parse import urlencode
                            qs = urlencode({k: v for k, v in
                                            (("service", pre_service), ("date", pre_date),
                                             ("time", pre_time)) if v})
                            if qs:
                                target = f"{target}?{qs}"
                        return redirect(target)
                    # Failure: back to landing, curtain auto-opens with error popup.
                    return redirect(url_for("index", auth="failed", **{k: v for k, v in
                        (("next", nxt), ("service", pre_service),
                         ("date", pre_date), ("time", pre_time)) if v}))
                except pymysql.MySQLError as e:
                    print(f"Login failed: {e}")
                    return redirect(url_for("index", auth="failed"))
                finally:
                    conn.close()


@app.route("/register", methods=["GET", "POST"])
def register():
    """Public signup is disabled: accounts are created by Admin only."""
    flash("Public registration is closed. Accounts are issued by the clinic Admin.", "danger")
    return redirect(url_for("index"))



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------- Public guest booking (no account needed) ----------------

GUEST_SERVICES = ["General Checkup", "Vaccination", "Grooming",
                  "Boarding", "Surgery Consult", "Emergency"]


@app.route("/book-guest", methods=["POST"])
def book_guest():
    name = request.form.get("guest_name", "").strip()
    phone = "".join(c for c in request.form.get("phone", "") if c.isdigit())
    pet_name = request.form.get("pet_name", "").strip()
    species = request.form.get("species", "").strip()
    service = request.form.get("service", "").strip()
    appt_date = request.form.get("appointment_date", "").strip()
    appt_time = request.form.get("appointment_time", "").strip()

    errors = []
    if not name:
        errors.append("Your name is required.")
    if len(phone) < 7:
        errors.append("A valid phone number is required.")
    if not pet_name:
        errors.append("Pet name is required.")
    if species not in SPECIES_CHOICES:
        errors.append("Please select a valid species.")
    if service not in GUEST_SERVICES:
        errors.append("Please select a valid service.")
    if not appt_date:
        errors.append("Date is required.")
    elif appt_date < date.today().isoformat():
        errors.append("Date cannot be in the past.")
    if not appt_time:
        errors.append("Time is required.")
    for e in errors:
        flash(e, "danger")
    if errors:
        return redirect(url_for("index") + "#booking-wrap")

    conn = db()
    if conn is None:
        flash("Booking failed: database unavailable. Please call the clinic.", "danger")
        return redirect(url_for("index") + "#booking-wrap")
    try:
        import secrets
        with conn.cursor() as cur:
            # Reuse owner record by phone; otherwise auto-create one.
            cur.execute("SELECT id FROM users WHERE phone=%s AND role='owner' LIMIT 1",
                        (phone,))
            row = cur.fetchone()
            if row:
                owner_id = row["id"]
                if row.get("full_name") != name:
                    cur.execute("UPDATE users SET full_name=%s WHERE id=%s",
                                (name, owner_id))
            else:
                base = f"guest{phone}"[:40]
                username = base
                cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1", (username,))
                if cur.fetchone():
                    username = f"{base}{secrets.randbelow(9000) + 1000}"[:50]
                temp_pw = bcrypt.hashpw(secrets.token_urlsafe(16).encode(),
                                        bcrypt.gensalt()).decode()
                cur.execute(
                    "INSERT INTO users (full_name, username, email, password, role, phone)"
                    " VALUES (%s,%s,%s,%s,'owner',%s)",
                    (name, username, f"{username}@guest.local", temp_pw, phone))
                owner_id = cur.lastrowid
            cur.execute(
                "INSERT INTO pets (owner_id, name, species) VALUES (%s,%s,%s)",
                (owner_id, pet_name, species))
            pet_id = cur.lastrowid
            cur.execute(
                "INSERT INTO appointments"
                " (pet_id, owner_id, appointment_date, appointment_time, reason, status)"
                " VALUES (%s,%s,%s,%s,%s,'pending')",
                (pet_id, owner_id, appt_date, appt_time, service))
            ref = cur.lastrowid
        flash(f"Booking received! Reference #{ref} — {service} for {pet_name}"
              f" on {appt_date} at {appt_time}. We'll confirm by phone shortly.",
              "success")
    except pymysql.MySQLError as e:
        print(f"Guest booking failed: {e}")
        flash("Booking failed. Please try again or call the clinic.", "danger")
    finally:
        conn.close()
    return redirect(url_for("index") + "#booking-wrap")


# ---------------- Client ----------------

SPECIES_CHOICES = ["Dog", "Cat", "Bird", "Rabbit", "Hamster", "Reptile", "Other"]
GENDER_CHOICES = ["Male", "Female"]


@app.route("/client/dashboard")
@role_required("owner")
def client_dashboard():
    owner_id = int(session["user_id"])
    stats = {"pets": 0, "upcoming": 0, "pending_bills": 0}
    upcoming = []
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM pets WHERE owner_id=%s", (owner_id,))
                stats["pets"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM appointments"
                    " WHERE owner_id=%s AND status IN ('pending','approved')"
                    " AND appointment_date >= CURDATE()",
                    (owner_id,),
                )
                stats["upcoming"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM invoices WHERE owner_id=%s AND status='unpaid'",
                    (owner_id,),
                )
                stats["pending_bills"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.status,"
                    " p.name AS pet_name, u.full_name AS vet_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " LEFT JOIN users u ON u.id=a.vet_id"
                    " WHERE a.owner_id=%s AND a.appointment_date >= CURDATE()"
                    " ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 5",
                    (owner_id,),
                )
                upcoming = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Client dashboard failed: {e}")
        finally:
            conn.close()
    return render_template("client/dashboard.html", stats=stats, upcoming=upcoming)


@app.route("/client/my-pets", methods=["GET", "POST"])
@role_required("owner")
def my_pets():
    owner_id = int(session["user_id"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        species = request.form.get("species", "").strip()
        breed = request.form.get("breed", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        try:
            age = int(request.form.get("age", "") or 0) or None
        except ValueError:
            age = None
        try:
            weight = float(request.form.get("weight", "") or 0) or None
        except ValueError:
            weight = None

        errors = []
        if not name:
            errors.append("Pet name is required.")
        if species not in SPECIES_CHOICES:
            errors.append("Please select a valid species.")
        if gender is not None and gender not in GENDER_CHOICES:
            errors.append("Please select a valid gender.")

        if not errors:
            conn = db()
            if conn is None:
                errors.append("Database connection failed.")
            else:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pets (owner_id, name, species, breed, age, gender, weight)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (owner_id, name, species, breed, age, gender, weight),
                        )
                    flash(f"{name} registered!", "success")
                    return redirect(url_for("my_pets"))
                except pymysql.MySQLError as e:
                    print(f"Add pet failed: {e}")
                    errors.append("Could not register pet. Please try again.")
                finally:
                    conn.close()
        for e in errors:
            flash(e, "danger")

    pets = []
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM pets WHERE owner_id=%s ORDER BY name ASC", (owner_id,)
                )
                pets = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"List pets failed: {e}")
        finally:
            conn.close()
    return render_template(
        "client/my_pets.html", pets=pets,
        species_choices=SPECIES_CHOICES, gender_choices=GENDER_CHOICES,
    )


@app.route("/client/pets/<int:pet_id>/delete", methods=["POST"])
@role_required("owner")
def delete_pet(pet_id):
    owner_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM pets WHERE id=%s AND owner_id=%s", (pet_id, owner_id)
                )
                if cur.rowcount:
                    flash("Pet removed.", "success")
                else:
                    flash("Pet not found.", "danger")
        except pymysql.MySQLError as e:
            print(f"Delete pet failed: {e}")
            flash("Could not remove pet (it may have appointments).", "danger")
        finally:
            conn.close()
    return redirect(url_for("my_pets"))


@app.route("/client/book-appointment", methods=["GET", "POST"])
@role_required("owner")
def book_appointment():
    owner_id = int(session["user_id"])
    pets, vets = [], []
    conn = db()
    if conn is None:
        flash("Database connection failed. Check XAMPP MySQL.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, species, breed FROM pets WHERE owner_id=%s ORDER BY name ASC",
                    (owner_id,),
                )
                pets = cur.fetchall()
                cur.execute("SELECT id, full_name FROM users WHERE role='vet' ORDER BY full_name ASC")
                vets = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Fetch failed: {e}")
            flash("Could not load pets/veterinarians.", "danger")
        finally:
            conn.close()

    if request.method == "POST":
        try:
            pet_id = int(request.form.get("pet_id", 0))
        except ValueError:
            pet_id = 0
        vet_raw = request.form.get("vet_id", "")
        vet_id = int(vet_raw) if vet_raw.isdigit() else None
        appt_date = request.form.get("appointment_date", "").strip()
        appt_time = request.form.get("appointment_time", "").strip()
        reason = request.form.get("reason", "").strip()

        errors = []
        if pet_id <= 0:
            errors.append("Please select your pet.")
        if not appt_date:
            errors.append("Appointment date is required.")
        if not appt_time:
            errors.append("Appointment time is required.")
        if not reason:
            errors.append("Reason for visit is required.")
        if appt_date and appt_date < date.today().isoformat():
            errors.append("Appointment date cannot be in the past.")

        if not errors:
            conn = db()
            if conn is None:
                errors.append("Database connection failed.")
            else:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id FROM pets WHERE id=%s AND owner_id=%s LIMIT 1",
                            (pet_id, owner_id),
                        )
                        if not cur.fetchone():
                            errors.append("Invalid pet selected.")
                        if vet_id is not None:
                            cur.execute(
                                "SELECT id FROM users WHERE id=%s AND role='vet' LIMIT 1",
                                (vet_id,),
                            )
                            if not cur.fetchone():
                                errors.append("Invalid veterinarian selected.")
                                vet_id = None
                        if not errors:
                            cur.execute(
                                "INSERT INTO appointments"
                                " (pet_id, owner_id, vet_id, appointment_date, appointment_time, reason, status)"
                                " VALUES (%s, %s, %s, %s, %s, %s, 'pending')",
                                (pet_id, owner_id, vet_id, appt_date, appt_time, reason),
                            )
                            flash("Appointment booked! Status: pending.", "success")
                            return redirect(url_for("book_appointment"))
                except pymysql.MySQLError as e:
                    print(f"Booking failed: {e}")
                    errors.append("Booking failed. Please try again.")
                finally:
                    conn.close()
        for e in errors:
            flash(e, "danger")

    return render_template(
        "client/book_appointment.html",
        pets=pets,
        vets=vets,
        today=date.today().isoformat(),
        # Prefill from landing booking bar (?service=&date=&time=); POSTed form wins on re-render
        pre_service=request.form.get("reason", request.args.get("service", "")),
        pre_date=request.form.get("appointment_date", request.args.get("date", "")),
        pre_time=request.form.get("appointment_time", request.args.get("time", "")),
    )


# ---------------- Admin ----------------

@app.route("/admin/dashboard")
@role_required("admin", "staff")
def admin_dashboard():
    stats = {"owners": 0, "vets": 0, "pets": 0, "pending": 0, "serving": 0, "unpaid": "0.00"}
    recent, low_stock, pending_list = [], [], []
    conn = db()
    if conn is None:
        flash("Database connection failed. Check XAMPP MySQL.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='owner'")
                stats["owners"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE role IN ('vet','staff')")
                stats["vets"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM pets")
                stats["pets"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM appointments WHERE status='pending'")
                stats["pending"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM clinic_queue"
                    " WHERE status='serving' AND queue_date=CURDATE()"
                )
                stats["serving"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) AS t FROM invoices WHERE status='unpaid'"
                )
                stats["unpaid"] = cur.fetchone()["t"]
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.status,"
                    " p.name AS pet_name, o.full_name AS owner_name, v.full_name AS vet_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " LEFT JOIN users v ON v.id=a.vet_id"
                    " ORDER BY a.created_at DESC LIMIT 8"
                )
                recent = cur.fetchall()
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.reason,"
                    " p.name AS pet_name, o.full_name AS owner_name, o.phone"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " WHERE a.status='pending'"
                    " ORDER BY a.created_at ASC LIMIT 10"
                )
                pending_list = cur.fetchall()
                cur.execute(
                    "SELECT item_name, quantity FROM inventory"
                    " ORDER BY quantity ASC LIMIT 5"
                )
                low_stock = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Admin dashboard failed: {e}")
            flash("Could not load dashboard data.", "danger")
        finally:
            conn.close()
    return render_template("admin/dashboard.html", stats=stats, recent=recent,
                           low_stock=low_stock, pending_list=pending_list)


@app.route("/admin/appointments")
@role_required("admin", "staff")
def admin_appointments():
    status = request.args.get("status", "all").strip()
    if status not in ("pending", "approved", "completed", "cancelled"):
        status = "all"
    rows = []
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                q = ("SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,"
                     " p.name AS pet_name, o.full_name AS owner_name, o.phone,"
                     " v.full_name AS vet_name"
                     " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                     " JOIN users o ON o.id=a.owner_id"
                     " LEFT JOIN users v ON v.id=a.vet_id")
                if status == "all":
                    q += " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 100"
                    cur.execute(q)
                else:
                    q += (" WHERE a.status=%s"
                          " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 100")
                    cur.execute(q, (status,))
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Admin appointments failed: {e}")
            flash("Could not load appointments.", "danger")
        finally:
            conn.close()
    return render_template("admin/appointments.html", rows=rows, status=status,
                           statuses=["all", "pending", "approved", "completed", "cancelled"])


@app.route("/admin/appointments/<int:appt_id>/status", methods=["POST"])
@role_required("admin")
def admin_appointment_status(appt_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in ("pending", "approved", "completed", "cancelled"):
        flash("Invalid status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE appointments SET status=%s WHERE id=%s",
                        (new_status, appt_id),
                    )
                flash(f"Appointment #{appt_id} → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"Status update failed: {e}")
                flash("Could not update status.", "danger")
            finally:
                conn.close()
    ref = request.referrer or ""
    if "/admin/appointments" in ref and "/status" not in ref:
        return redirect(ref)
    return redirect(url_for("admin_dashboard"))


# ---------------- Vet ----------------

@app.route("/vet/dashboard")
@role_required("vet", "staff")
def vet_dashboard():
    vet_id = int(session["user_id"])
    assigned, queue_today, recent_notes = [], [], []
    conn = db()
    if conn is None:
        flash("Database connection failed. Check XAMPP MySQL.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,"
                    " p.name AS pet_name, p.species, o.full_name AS owner_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " WHERE (a.vet_id=%s OR a.vet_id IS NULL)"
                    " AND a.status IN ('pending','approved') AND a.appointment_date >= CURDATE()"
                    " ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 10",
                    (vet_id,),
                )
                assigned = cur.fetchall()
                cur.execute(
                    "SELECT q.queue_number, q.status, p.name AS pet_name, o.full_name AS owner_name"
                    " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                    " JOIN users o ON o.id=q.owner_id"
                    " WHERE q.queue_date=CURDATE() AND q.status IN ('waiting','serving')"
                    " ORDER BY q.queue_number ASC LIMIT 10"
                )
                queue_today = cur.fetchall()
                cur.execute(
                    "SELECT c.diagnosis, c.consultation_date, p.name AS pet_name"
                    " FROM consultations c JOIN pets p ON p.id=c.pet_id"
                    " WHERE c.vet_id=%s ORDER BY c.consultation_date DESC LIMIT 5",
                    (vet_id,),
                )
                recent_notes = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Vet dashboard failed: {e}")
            flash("Could not load dashboard data.", "danger")
        finally:
            conn.close()
    return render_template(
        "vet/dashboard.html", assigned=assigned,
        queue_today=queue_today, recent_notes=recent_notes,
    )


# ---------------- Queue (admin manages, vet serves) ----------------

QUEUE_STATUSES = ["waiting", "serving", "done", "skipped"]


def _today_queue(cur):
    cur.execute(
        "SELECT q.id, q.queue_number, q.status, q.appointment_id,"
        " p.name AS pet_name, o.full_name AS owner_name, v.full_name AS vet_name"
        " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
        " JOIN users o ON o.id=q.owner_id"
        " LEFT JOIN users v ON v.id=q.vet_id"
        " WHERE q.queue_date=CURDATE() ORDER BY q.queue_number ASC"
    )
    return cur.fetchall()


@app.route("/admin/queue", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_queue():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/queue.html", queue=[], eligible=[])
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                if session.get("role") != "admin":
                    flash("Only Admin can add to the queue.", "danger")
                    return redirect(url_for("admin_queue"))
                try:
                    appt_id = int(request.form.get("appointment_id", 0))
                except ValueError:
                    appt_id = 0
                if appt_id > 0:
                    cur.execute(
                        "SELECT pet_id, owner_id, vet_id FROM appointments"
                        " WHERE id=%s AND status='approved' LIMIT 1", (appt_id,)
                    )
                    appt = cur.fetchone()
                    if not appt:
                        flash("Only approved appointments can join the queue.", "danger")
                    else:
                        cur.execute(
                            "SELECT COALESCE(MAX(queue_number),0)+1 AS nxt FROM clinic_queue"
                            " WHERE queue_date=CURDATE()"
                        )
                        nxt = cur.fetchone()["nxt"]
                        try:
                            cur.execute(
                                "INSERT INTO clinic_queue"
                                " (appointment_id, pet_id, owner_id, vet_id, queue_number, queue_date)"
                                " VALUES (%s,%s,%s,%s,%s,CURDATE())",
                                (appt_id, appt["pet_id"], appt["owner_id"], appt["vet_id"], nxt),
                            )
                            flash(f"Added to queue as #{nxt}.", "success")
                        except pymysql.IntegrityError:
                            flash("That appointment is already queued.", "danger")
            queue = _today_queue(cur)
            cur.execute(
                "SELECT a.id, a.appointment_date, p.name AS pet_name"
                " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " LEFT JOIN clinic_queue q ON q.appointment_id=a.id"
                " WHERE a.status='approved' AND q.id IS NULL"
                " ORDER BY a.appointment_date ASC LIMIT 20"
            )
            eligible = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Admin queue failed: {e}")
        flash("Could not load queue.", "danger")
        queue, eligible = [], []
    finally:
        conn.close()
    return render_template("admin/queue.html", queue=queue, eligible=eligible,
                           statuses=QUEUE_STATUSES)


@app.route("/admin/queue/<int:qid>/status", methods=["POST"])
@role_required("admin")
def admin_queue_status(qid):
    return _set_queue_status(qid, "admin_queue")


@app.route("/vet/queue", methods=["GET"])
@role_required("vet", "staff")
def vet_queue():
    conn = db()
    queue = []
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                queue = _today_queue(cur)
        except pymysql.MySQLError as e:
            print(f"Vet queue failed: {e}")
        finally:
            conn.close()
    return render_template("vet/queue.html", queue=queue, statuses=QUEUE_STATUSES)


@app.route("/vet/queue/<int:qid>/status", methods=["POST"])
@role_required("vet", "staff")
def vet_queue_status(qid):
    return _set_queue_status(qid, "vet_queue")


def _set_queue_status(qid, redirect_endpoint):
    new_status = request.form.get("status", "").strip()
    if new_status not in QUEUE_STATUSES:
        flash("Invalid queue status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE clinic_queue SET status=%s WHERE id=%s",
                                (new_status, qid))
                flash(f"Queue entry → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"Queue status failed: {e}")
                flash("Could not update queue.", "danger")
            finally:
                conn.close()
    return redirect(url_for(redirect_endpoint))


# ---------------- Consultations (vet) ----------------

@app.route("/vet/consultations")
@role_required("vet", "staff")
def vet_consultations():
    vet_id = int(session["user_id"])
    rows = []
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT c.id, c.diagnosis, c.consultation_date, p.name AS pet_name"
                    " FROM consultations c JOIN pets p ON p.id=c.pet_id"
                    " WHERE c.vet_id=%s ORDER BY c.consultation_date DESC", (vet_id,)
                )
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Consult list failed: {e}")
        finally:
            conn.close()
    return render_template("vet/consultations.html", rows=rows)


@app.route("/vet/consultations/new", methods=["GET", "POST"])
@role_required("vet", "staff")
def vet_consultation_new():
    vet_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("vet/consultation_form.html", eligible=[])
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                try:
                    appt_id = int(request.form.get("appointment_id", 0))
                except ValueError:
                    appt_id = 0
                diagnosis = request.form.get("diagnosis", "").strip()
                treatment = request.form.get("treatment", "").strip() or None
                notes = request.form.get("notes", "").strip() or None
                if appt_id <= 0 or not diagnosis:
                    flash("Appointment and diagnosis are required.", "danger")
                else:
                    cur.execute(
                        "SELECT pet_id FROM appointments"
                        " WHERE id=%s AND status='approved'"
                        " AND (vet_id=%s OR vet_id IS NULL) LIMIT 1",
                        (appt_id, vet_id),
                    )
                    appt = cur.fetchone()
                    if not appt:
                        flash("Invalid appointment (must be approved).", "danger")
                    else:
                        cur.execute(
                            "INSERT INTO consultations"
                            " (appointment_id, pet_id, vet_id, diagnosis, treatment, notes)"
                            " VALUES (%s,%s,%s,%s,%s,%s)",
                            (appt_id, appt["pet_id"], vet_id, diagnosis, treatment, notes),
                        )
                        consult_id = cur.lastrowid
                        cur.execute(
                            "UPDATE appointments SET status='completed' WHERE id=%s",
                            (appt_id,),
                        )
                        flash("Consultation logged.", "success")
                        conn.close()
                        return redirect(url_for("vet_consultation_detail",
                                                consult_id=consult_id))
            cur.execute(
                "SELECT a.id, a.appointment_date, p.name AS pet_name, o.full_name AS owner_name"
                " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " JOIN users o ON o.id=a.owner_id"
                " WHERE a.status='approved' AND (a.vet_id=%s OR a.vet_id IS NULL)"
                " ORDER BY a.appointment_date ASC LIMIT 30", (vet_id,)
            )
            eligible = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Consult create failed: {e}")
        flash("Could not save consultation.", "danger")
        eligible = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("vet/consultation_form.html", eligible=eligible)


@app.route("/vet/consultations/<int:consult_id>", methods=["GET", "POST"])
@role_required("vet", "staff")
def vet_consultation_detail(consult_id):
    vet_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("vet_consultations"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.*, p.name AS pet_name FROM consultations c"
                " JOIN pets p ON p.id=c.pet_id WHERE c.id=%s LIMIT 1", (consult_id,)
            )
            consult = cur.fetchone()
            if not consult:
                flash("Consultation not found.", "danger")
                return redirect(url_for("vet_consultations"))
            if request.method == "POST":
                inv_raw = request.form.get("inventory_id", "")
                inventory_id = int(inv_raw) if inv_raw.isdigit() else None
                dosage = request.form.get("dosage", "").strip() or None
                try:
                    qty = int(request.form.get("quantity_used", 1))
                except ValueError:
                    qty = 1
                instructions = request.form.get("instructions", "").strip() or None
                if qty < 1:
                    flash("Quantity must be at least 1.", "danger")
                elif inventory_id is not None:
                    cur.execute("SELECT quantity, item_name FROM inventory WHERE id=%s",
                                (inventory_id,))
                    item = cur.fetchone()
                    if not item:
                        flash("Invalid inventory item.", "danger")
                    elif item["quantity"] < qty:
                        flash(f"Not enough stock of {item['item_name']}"
                              f" ({item['quantity']} left).", "danger")
                    else:
                        cur.execute(
                            "INSERT INTO prescriptions_treatments"
                            " (consultation_id, inventory_id, dosage, quantity_used, instructions)"
                            " VALUES (%s,%s,%s,%s,%s)",
                            (consult_id, inventory_id, dosage, qty, instructions),
                        )
                        cur.execute(
                            "UPDATE inventory SET quantity=quantity-%s WHERE id=%s",
                            (qty, inventory_id),
                        )
                        flash("Prescription added; stock deducted.", "success")
                else:
                    cur.execute(
                        "INSERT INTO prescriptions_treatments"
                        " (consultation_id, dosage, quantity_used, instructions)"
                        " VALUES (%s,%s,%s,%s)",
                        (consult_id, dosage, qty, instructions),
                    )
                    flash("Treatment note added.", "success")
            cur.execute(
                "SELECT r.*, i.item_name FROM prescriptions_treatments r"
                " LEFT JOIN inventory i ON i.id=r.inventory_id"
                " WHERE r.consultation_id=%s ORDER BY r.id ASC", (consult_id,)
            )
            rxs = cur.fetchall()
            cur.execute("SELECT id, item_name, quantity FROM inventory"
                        " WHERE quantity > 0 ORDER BY item_name ASC")
            items = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Consult detail failed: {e}")
        flash("Could not load consultation.", "danger")
        return redirect(url_for("vet_consultations"))
    finally:
        conn.close()
    can_edit = (int(consult["vet_id"]) == vet_id)
    return render_template("vet/consultation_detail.html",
                           consult=consult, rxs=rxs, items=items, can_edit=can_edit)


# ---------------- Inventory (admin) ----------------

INV_CATEGORIES = ["Medicine", "Vaccine", "Food", "Equipment", "Hygiene", "Other"]


@app.route("/admin/inventory", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_inventory():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/inventory.html", items=[], categories=INV_CATEGORIES)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                if session.get("role") != "admin":
                    flash("Only Admin can add inventory.", "danger")
                    return redirect(url_for("admin_inventory"))
                name = request.form.get("item_name", "").strip()
                category = request.form.get("category", "Medicine").strip()
                try:
                    qty = int(request.form.get("quantity", 0))
                except ValueError:
                    qty = -1
                try:
                    price = float(request.form.get("price", 0))
                except ValueError:
                    price = -1
                expiry = request.form.get("expiry_date", "").strip() or None
                if not name:
                    flash("Item name is required.", "danger")
                elif category not in INV_CATEGORIES:
                    flash("Invalid category.", "danger")
                elif qty < 0 or price < 0:
                    flash("Quantity and price must be zero or more.", "danger")
                else:
                    cur.execute(
                        "INSERT INTO inventory (item_name, category, quantity, price, expiry_date)"
                        " VALUES (%s,%s,%s,%s,%s)",
                        (name, category, qty, price, expiry),
                    )
                    flash(f"{name} added.", "success")
                    conn.close()
                    return redirect(url_for("admin_inventory"))
            cur.execute("SELECT * FROM inventory ORDER BY item_name ASC")
            items = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Inventory failed: {e}")
        flash("Could not load inventory.", "danger")
        items = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/inventory.html", items=items, categories=INV_CATEGORIES)


@app.route("/admin/inventory/<int:item_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_inventory_edit(item_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_inventory"))
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                name = request.form.get("item_name", "").strip()
                category = request.form.get("category", "Medicine").strip()
                try:
                    qty = int(request.form.get("quantity", 0))
                except ValueError:
                    qty = -1
                try:
                    price = float(request.form.get("price", 0))
                except ValueError:
                    price = -1
                expiry = request.form.get("expiry_date", "").strip() or None
                if not name or category not in INV_CATEGORIES or qty < 0 or price < 0:
                    flash("Check all fields (name, category, qty >= 0, price >= 0).", "danger")
                else:
                    cur.execute(
                        "UPDATE inventory SET item_name=%s, category=%s, quantity=%s,"
                        " price=%s, expiry_date=%s WHERE id=%s",
                        (name, category, qty, price, expiry, item_id),
                    )
                    flash("Item updated.", "success")
                    conn.close()
                    return redirect(url_for("admin_inventory"))
            cur.execute("SELECT * FROM inventory WHERE id=%s LIMIT 1", (item_id,))
            item = cur.fetchone()
            if not item:
                flash("Item not found.", "danger")
                conn.close()
                return redirect(url_for("admin_inventory"))
    except pymysql.MySQLError as e:
        print(f"Inventory edit failed: {e}")
        flash("Could not update item.", "danger")
        return redirect(url_for("admin_inventory"))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/inventory_form.html", item=item,
                           categories=INV_CATEGORIES)


@app.route("/admin/inventory/<int:item_id>/delete", methods=["POST"])
@role_required("admin")
def admin_inventory_delete(item_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM inventory WHERE id=%s", (item_id,))
                flash("Item deleted." if cur.rowcount else "Item not found.",
                      "success" if cur.rowcount else "danger")
        except pymysql.MySQLError as e:
            print(f"Inventory delete failed: {e}")
            flash("Could not delete item.", "danger")
        finally:
            conn.close()
    return redirect(url_for("admin_inventory"))


# ---------------- Invoices (admin bills, client pays) ----------------

INV_STATUSES = ["unpaid", "paid", "cancelled"]


@app.route("/admin/invoices", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_invoices():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/invoices.html", invoices=[], owners=[],
                               statuses=INV_STATUSES)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                if session.get("role") != "admin":
                    flash("Only Admin can issue invoices.", "danger")
                    return redirect(url_for("admin_invoices"))
                try:
                    owner_id = int(request.form.get("owner_id", 0))
                except ValueError:
                    owner_id = 0
                appt_raw = request.form.get("appointment_id", "")
                appt_id = int(appt_raw) if appt_raw.isdigit() else None
                cons_raw = request.form.get("consultation_id", "")
                cons_id = int(cons_raw) if cons_raw.isdigit() else None
                try:
                    amount = float(request.form.get("amount", 0))
                except ValueError:
                    amount = 0
                if owner_id <= 0:
                    flash("Select an owner.", "danger")
                elif amount <= 0:
                    flash("Amount must be more than zero.", "danger")
                else:
                    cur.execute("SELECT id FROM users WHERE id=%s AND role='owner' LIMIT 1",
                                (owner_id,))
                    if not cur.fetchone():
                        flash("Invalid owner.", "danger")
                    else:
                        cur.execute(
                            "INSERT INTO invoices (owner_id, appointment_id, consultation_id, amount)"
                            " VALUES (%s,%s,%s,%s)",
                            (owner_id, appt_id, cons_id, amount),
                        )
                        flash("Invoice issued.", "success")
                        conn.close()
                        return redirect(url_for("admin_invoices"))
            cur.execute(
                "SELECT i.*, o.full_name AS owner_name FROM invoices i"
                " JOIN users o ON o.id=i.owner_id ORDER BY i.issued_date DESC LIMIT 50"
            )
            invoices = cur.fetchall()
            cur.execute("SELECT id, full_name FROM users WHERE role='owner'"
                        " ORDER BY full_name ASC")
            owners = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Invoices failed: {e}")
        flash("Could not load invoices.", "danger")
        invoices, owners = [], []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/invoices.html", invoices=invoices, owners=owners,
                           statuses=INV_STATUSES)


@app.route("/admin/invoices/<int:inv_id>/status", methods=["POST"])
@role_required("admin")
def admin_invoice_status(inv_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in INV_STATUSES:
        flash("Invalid status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE invoices SET status=%s WHERE id=%s",
                                (new_status, inv_id))
                flash(f"Invoice #{inv_id} → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"Invoice status failed: {e}")
                flash("Could not update invoice.", "danger")
            finally:
                conn.close()
    return redirect(url_for("admin_invoices"))


@app.route("/client/my-invoices", methods=["GET", "POST"])
@role_required("owner")
def client_invoices():
    owner_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("client/my_invoices.html", invoices=[])
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                try:
                    inv_id = int(request.form.get("invoice_id", 0))
                except ValueError:
                    inv_id = 0
                cur.execute(
                    "UPDATE invoices SET status='paid'"
                    " WHERE id=%s AND owner_id=%s AND status='unpaid'",
                    (inv_id, owner_id),
                )
                flash("Payment recorded. Thank you!" if cur.rowcount
                      else "Invoice not found or already settled.",
                      "success" if cur.rowcount else "danger")
            cur.execute(
                "SELECT * FROM invoices WHERE owner_id=%s ORDER BY issued_date DESC",
                (owner_id,),
            )
            invoices = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Client invoices failed: {e}")
        flash("Could not load invoices.", "danger")
        invoices = []
    finally:
        conn.close()
    return render_template("client/my_invoices.html", invoices=invoices)


# ---------------- Users (admin creates all accounts) ----------------

USER_ROLES = ["admin", "vet", "staff", "owner"]


@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/users.html", users=[], roles=USER_ROLES)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                full_name = request.form.get("full_name", "").strip()
                username = request.form.get("username", "").strip()
                role = request.form.get("role", "").strip()
                password = request.form.get("password", "")
                email = request.form.get("email", "").strip() or None
                errors = []
                if not full_name:
                    errors.append("Full name is required.")
                if len(username) < 3 or not username.replace("_", "").replace("-", "").isalnum():
                    errors.append("Username needs 3+ letters/numbers ( _ - allowed).")
                if role not in USER_ROLES:
                    errors.append("Invalid role.")
                if len(password) < 3:
                    errors.append("Password is required (3+ chars).")
                if not errors:
                    cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1",
                                (username,))
                    if cur.fetchone():
                        errors.append("Username is taken.")
                if email:
                    cur.execute("SELECT id FROM users WHERE email=%s LIMIT 1", (email,))
                    if cur.fetchone():
                        errors.append("Email is already used.")
                if not errors:
                    if not email:
                        email = f"{username}@clinic.local"
                    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                    cur.execute(
                        "INSERT INTO users (full_name, username, email, password, role)"
                        " VALUES (%s,%s,%s,%s,%s)",
                        (full_name, username, email, hashed, role))
                    flash(f"User {username} ({role}) created.", "success")
                    conn.close()
                    return redirect(url_for("admin_users"))
                for e in errors:
                    flash(e, "danger")
            cur.execute("SELECT id, full_name, username, email, role, created_at FROM users"
                        " ORDER BY role, username ASC")
            users = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Admin users failed: {e}")
        flash("Could not load users.", "danger")
        users = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/users.html", users=users, roles=USER_ROLES)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def admin_user_delete(user_id):
    if user_id == int(session["user_id"]):
        flash("You cannot delete your own account.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT role FROM users WHERE id=%s LIMIT 1", (user_id,))
                    target = cur.fetchone()
                    if not target:
                        flash("User not found.", "danger")
                    elif target["role"] == "admin":
                        cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin'")
                        if cur.fetchone()["c"] <= 1:
                            flash("Cannot delete the last admin.", "danger")
                        else:
                            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
                            flash("User deleted.", "success")
                    else:
                        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
                        flash("User deleted.", "success")
            except pymysql.MySQLError as e:
                print(f"User delete failed: {e}")
                flash("Could not delete user (they may own records).", "danger")
            finally:
                conn.close()
    return redirect(url_for("admin_users"))


if __name__ == "__main__":
    import os

    # PORT env override: another course project (IM 103) already uses :5000,
    # so run this app with e.g. $env:PORT=5001; python app.py
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
