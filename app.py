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
    if role in ("admin", "staff", "vet"):
        # Shared management dashboard (view-only unless admin).
        return url_for("admin_dashboard")
    return url_for("index")  # owner rows are records; no login surface


@app.context_processor
def inject_bell():
    """Header shared data: period filter state + live attention counts (admin side)."""
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    out = {"period": period, "periods": PERIODS}
    ep = (request.endpoint or "")
    if not ep.startswith("admin_"):
        return out
    bell = {"pending": 0, "lowstock": 0, "unpaid": "0.00"}
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM appointments WHERE status='pending'")
                bell["pending"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM inventory WHERE quantity<=5")
                bell["lowstock"] = cur.fetchone()["c"]
                cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM invoices"
                            " WHERE status='unpaid'")
                bell["unpaid"] = cur.fetchone()["t"]
        except pymysql.MySQLError as e:
            print(f"Bell counts failed: {e}")
        finally:
            conn.close()
    total = ((bell["pending"] > 0) + (bell["lowstock"] > 0)
             + (1 if float(bell["unpaid"] or 0) > 0 else 0))
    out.update({"bell": bell, "bell_total": total})
    return out


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
    # Landing curtain may carry booking context (?next=&service=&date=&time=).
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
                            "SELECT id, full_name, password, role, status FROM users"
                            " WHERE username=%s LIMIT 1",
                            (username,),
                        )
                        user = cur.fetchone()
                    try:
                        ok = bool(user) and bcrypt.checkpw(
                            password.encode(), user["password"].encode())
                    except ValueError:
                        ok = False  # corrupt hash in DB: fail closed, never 500
                    if ok and user["status"] != "approved":
                        # Correct password, inactive account: fail closed with reason.
                        print(f"Login blocked: {username} is {user['status']}")
                        return redirect(url_for("index", auth="failed"))
                    if ok:
                        session.clear()
                        session["user_id"] = int(user["id"])
                        session["full_name"] = user["full_name"]
                        session["role"] = user["role"]
                        target = safe_next(nxt, dashboard_for(user["role"]))
                        if not nxt and target == dashboard_for(user["role"]):
                            # Fresh login to home dashboard: play the skeleton once.
                            target += "?welcome=1"
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
                " (pet_id, owner_id, appointment_date, appointment_time, reason,"
                " source, status)"
                " VALUES (%s,%s,%s,%s,%s,'guest','pending')",
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


# ---------------- Admin ----------------

PERIODS = ["All Time", "Today", "This Week"]


def period_cond(col, period):
    """SQL predicate limiting a datetime/date column to the selected period."""
    if period == "Today":
        return f"DATE({col})=CURDATE()"
    if period == "This Week":
        return f"YEARWEEK({col},1)=YEARWEEK(CURDATE(),1)"
    return "1=1"


@app.route("/admin/dashboard")
@role_required("admin", "staff")
def admin_dashboard():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    kpi = {"pending": 0, "queue": 0, "lowstock": 0, "unpaid": "0.00", "consults": 0}
    bell = {"pending": 0, "lowstock": 0, "unpaid": 0}
    charts = None
    now_serving, up_next = None, []
    recent, low_stock, pending_list = [], [], []
    conn = db()
    if conn is None:
        flash("Database connection failed. Check XAMPP MySQL.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                # Snapshot KPIs (always current).
                cur.execute("SELECT COUNT(*) AS c FROM appointments WHERE status='pending'")
                kpi["pending"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM clinic_queue"
                    " WHERE queue_date=CURDATE() AND status IN ('waiting','serving')"
                )
                kpi["queue"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM inventory WHERE quantity<=5")
                kpi["lowstock"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) AS t FROM invoices WHERE status='unpaid'"
                )
                kpi["unpaid"] = cur.fetchone()["t"]
                # Period-driven KPI: consults done in the selected period.
                cur.execute(
                    "SELECT COUNT(*) AS c FROM consultations"
                    f" WHERE {period_cond('consultation_date', period)}"
                )
                kpi["consults"] = cur.fetchone()["c"]
                # Bell mirrors live attention items.
                bell = {"pending": kpi["pending"], "lowstock": kpi["lowstock"],
                        "unpaid": kpi["unpaid"]}
                # ---- Analytics datasets (adaptive buckets, zero-filled) ----
                from datetime import timedelta
                today = date.today()
                if period == "Today":
                    blabels = [f"{h % 12 or 12}{'AM' if h < 12 else 'PM'}" for h in range(24)]
                    cur.execute("SELECT HOUR(created_at) AS b, COUNT(*) AS c FROM appointments"
                                " WHERE DATE(created_at)=CURDATE() GROUP BY b")
                    bmap = {r["b"]: r["c"] for r in cur.fetchall()}
                    bookings = [bmap.get(h, 0) for h in range(24)]
                    cur.execute("SELECT HOUR(issued_date) AS b, COALESCE(SUM(amount),0) AS t"
                                " FROM invoices WHERE status='paid'"
                                " AND DATE(issued_date)=CURDATE() GROUP BY b")
                    rmap = {r["b"]: float(r["t"]) for r in cur.fetchall()}
                    revenue = [rmap.get(h, 0) for h in range(24)]
                elif period == "This Week":
                    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
                    blabels = [d.strftime("%a %d") for d in days]
                    cur.execute("SELECT DATE(created_at) AS b, COUNT(*) AS c FROM appointments"
                                " WHERE created_at>=CURDATE()-INTERVAL 6 DAY GROUP BY b")
                    bmap = {str(r["b"]): r["c"] for r in cur.fetchall()}
                    bookings = [bmap.get(str(d), 0) for d in days]
                    cur.execute("SELECT DATE(issued_date) AS b, COALESCE(SUM(amount),0) AS t"
                                " FROM invoices WHERE status='paid'"
                                " AND issued_date>=CURDATE()-INTERVAL 6 DAY GROUP BY b")
                    rmap = {str(r["b"]): float(r["t"]) for r in cur.fetchall()}
                    revenue = [rmap.get(str(d), 0) for d in days]
                else:
                    months = []
                    y, m = today.year, today.month
                    for _ in range(6):
                        months.append((y, m))
                        m -= 1
                        if m == 0:
                            m, y = 12, y - 1
                    months.reverse()
                    blabels = [date(y, m, 1).strftime("%b '%y") for y, m in months]
                    cur.execute("SELECT DATE_FORMAT(created_at,'%Y-%m') AS b, COUNT(*) AS c"
                                " FROM appointments"
                                " WHERE created_at>=DATE_SUB(CURDATE(), INTERVAL 6 MONTH)"
                                " GROUP BY b")
                    bmap = {r["b"]: r["c"] for r in cur.fetchall()}
                    bookings = [bmap.get(f"{y}-{m:02d}", 0) for y, m in months]
                    cur.execute("SELECT DATE_FORMAT(issued_date,'%Y-%m') AS b,"
                                " COALESCE(SUM(amount),0) AS t FROM invoices"
                                " WHERE status='paid'"
                                " AND issued_date>=DATE_SUB(CURDATE(), INTERVAL 6 MONTH)"
                                " GROUP BY b")
                    rmap = {r["b"]: float(r["t"]) for r in cur.fetchall()}
                    revenue = [rmap.get(f"{y}-{m:02d}", 0) for y, m in months]
                cur.execute(
                    "SELECT status, COUNT(*) AS c FROM clinic_queue"
                    " WHERE queue_date=CURDATE() GROUP BY status"
                )
                qmap = {r["status"]: r["c"] for r in cur.fetchall()}
                queue_load = [qmap.get(s, 0) for s in ("waiting", "serving", "done", "skipped")]
                cur.execute(
                    "SELECT reason, COUNT(*) AS c FROM appointments"
                    f" WHERE {period_cond('created_at', period)}"
                    " GROUP BY reason ORDER BY c DESC LIMIT 5"
                )
                top_rows = cur.fetchall()
                charts = {
                    "labels": blabels, "bookings": bookings, "revenue": revenue,
                    "queue_load": queue_load,
                    "services": [r["reason"] or "Unspecified" for r in top_rows],
                    "service_counts": [r["c"] for r in top_rows],
                }
                # Now-serving strip (same source as the queue board).
                cur.execute(
                    "SELECT q.queue_number, p.name AS pet_name, o.full_name AS owner_name"
                    " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                    " JOIN users o ON o.id=q.owner_id"
                    " WHERE q.queue_date=CURDATE() AND q.status='serving'"
                    " ORDER BY q.queue_number ASC LIMIT 1"
                )
                now_serving = cur.fetchone()
                cur.execute(
                    "SELECT q.queue_number, p.name AS pet_name"
                    " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                    " WHERE q.queue_date=CURDATE() AND q.status='waiting'"
                    " ORDER BY q.queue_number ASC LIMIT 2"
                )
                up_next = cur.fetchall()
                # Period-driven activity: appointments created in the period.
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.status,"
                    " a.created_at, p.name AS pet_name, o.full_name AS owner_name,"
                    " v.full_name AS vet_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " LEFT JOIN users v ON v.id=a.vet_id"
                    f" WHERE {period_cond('a.created_at', period)}"
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
    bell_total = (bell["pending"] > 0) + (bell["lowstock"] > 0) + (1 if float(bell["unpaid"] or 0) > 0 else 0)
    return render_template("admin/dashboard.html", kpi=kpi, bell=bell,
                           bell_total=bell_total, recent=recent, low_stock=low_stock,
                           pending_list=pending_list, charts=charts,
                           now_serving=now_serving, up_next=up_next,
                           period=period, periods=PERIODS)


@app.route("/admin/appointments")
@role_required("admin", "staff")
def admin_appointments():
    status = request.args.get("status", "all").strip()
    if status not in ("pending", "approved", "completed", "cancelled"):
        status = "all"
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    rows = []
    akpi = {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                pcond = period_cond('a.appointment_date', period)
                for key, cond in (("total", "1=1"), ("pending", "a.status='pending'"),
                                  ("approved", "a.status='approved'"),
                                  ("rejected", "a.status='cancelled'")):
                    cur.execute("SELECT COUNT(*) AS c FROM appointments a"
                                f" WHERE {pcond} AND {cond}")
                    akpi[key] = cur.fetchone()["c"]
                sel = ("SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,"
                       " p.name AS pet_name, o.full_name AS owner_name, o.phone,"
                       " v.full_name AS vet_name"
                       " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                       " JOIN users o ON o.id=a.owner_id"
                       " LEFT JOIN users v ON v.id=a.vet_id"
                       f" WHERE {pcond}")
                params = []
                if status != "all":
                    sel += " AND a.status=%s"
                    params.append(status)
                if q:
                    like = f"%{q}%"
                    sel += (" AND (p.name LIKE %s OR o.full_name LIKE %s"
                            " OR o.phone LIKE %s OR a.reason LIKE %s)")
                    params.extend([like] * 4)
                sel += " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 100"
                cur.execute(sel, params)
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Admin appointments failed: {e}")
            flash("Could not load appointments.", "danger")
        finally:
            conn.close()
    return render_template("admin/appointments.html", rows=rows, status=status, q=q,
                           akpi=akpi,
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


# ---------------- Queue (admin manages, vet serves) ----------------

QUEUE_STATUSES = ["waiting", "serving", "done", "skipped"]


def _today_queue(cur, period="All Time", q="", status="all"):
    cond = "" if period == "All Time" else f" AND {period_cond('q.queue_date', period)}"
    params = []
    if status in QUEUE_STATUSES:
        cond += " AND q.status=%s"
        params.append(status)
    if q:
        like = f"%{q}%"
        cond += " AND (p.name LIKE %s OR o.full_name LIKE %s)"
        params.extend([like, like])
    cur.execute(
        "SELECT q.id, q.queue_number, q.status, q.appointment_id, q.queue_date,"
        " p.name AS pet_name, o.full_name AS owner_name, v.full_name AS vet_name"
        " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
        " JOIN users o ON o.id=q.owner_id"
        " LEFT JOIN users v ON v.id=q.vet_id"
        f" WHERE q.queue_date<=CURDATE(){cond} ORDER BY q.queue_date DESC,"
        " q.queue_number ASC",
        params,
    )
    return cur.fetchall()


@app.route("/admin/queue", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_queue():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    qstatus = request.args.get("qstatus", "all").strip()
    if qstatus not in QUEUE_STATUSES:
        qstatus = "all"
    qkpi = {"waiting": 0, "serving": 0, "done": 0, "skipped": 0}
    now_serving, up_next = None, []
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/queue.html", queue=[], eligible=[], qkpi=qkpi,
                               q=q, qstatus=qstatus, now_serving=now_serving,
                               up_next=up_next)
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
            queue = _today_queue(cur, period, q, qstatus)
            for key in ("waiting", "serving", "done", "skipped"):
                cur.execute("SELECT COUNT(*) AS c FROM clinic_queue"
                            f" WHERE status=%s AND {period_cond('queue_date', period)}",
                            (key,))
                qkpi[key] = cur.fetchone()["c"]
            # Now-serving strip: first serving ticket today + next 2 waiting.
            cur.execute(
                "SELECT q.queue_number, p.name AS pet_name, o.full_name AS owner_name"
                " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                " JOIN users o ON o.id=q.owner_id"
                " WHERE q.queue_date=CURDATE() AND q.status='serving'"
                " ORDER BY q.queue_number ASC LIMIT 1"
            )
            now_serving = cur.fetchone()
            cur.execute(
                "SELECT q.queue_number, p.name AS pet_name"
                " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                " WHERE q.queue_date=CURDATE() AND q.status='waiting'"
                " ORDER BY q.queue_number ASC LIMIT 2"
            )
            up_next = cur.fetchall()
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
    return render_template("admin/queue.html", queue=queue, eligible=eligible, qkpi=qkpi,
                           q=q, qstatus=qstatus, now_serving=now_serving,
                           up_next=up_next, statuses=QUEUE_STATUSES)


@app.route("/admin/queue/<int:qid>/status", methods=["POST"])
@role_required("admin", "staff")
def admin_queue_status(qid):
    return _set_queue_status(qid, "admin_queue")


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


# ---------------- Consultations (shared: admin + staff operate) ----------------

@app.route("/admin/consultations")
@role_required("admin", "staff")
def admin_consultations():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    rx = request.args.get("rx", "all").strip()
    if rx not in ("all", "yes", "no"):
        rx = "all"
    rows = []
    eligible = []
    ckpi = {"total": 0, "period": 0, "withrx": 0}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM consultations")
                ckpi["total"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM consultations"
                            f" WHERE {period_cond('consultation_date', period)}")
                ckpi["period"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(DISTINCT consultation_id) AS c"
                            " FROM prescriptions_treatments")
                ckpi["withrx"] = cur.fetchone()["c"]
                sel = ("SELECT c.id, c.diagnosis, c.consultation_date, p.name AS pet_name,"
                       " u.full_name AS vet_name"
                       " FROM consultations c JOIN pets p ON p.id=c.pet_id"
                       " JOIN users u ON u.id=c.vet_id"
                       f" WHERE {period_cond('c.consultation_date', period)}")
                params = []
                if rx == "yes":
                    sel += (" AND EXISTS (SELECT 1 FROM prescriptions_treatments r"
                            " WHERE r.consultation_id=c.id)")
                elif rx == "no":
                    sel += (" AND NOT EXISTS (SELECT 1 FROM prescriptions_treatments r"
                            " WHERE r.consultation_id=c.id)")
                if q:
                    like = f"%{q}%"
                    sel += " AND (c.diagnosis LIKE %s OR p.name LIKE %s)"
                    params.extend([like, like])
                sel += " ORDER BY c.consultation_date DESC LIMIT 50"
                cur.execute(sel, params)
                rows = cur.fetchall()
                cur.execute(
                    "SELECT a.id, a.appointment_date, p.name AS pet_name,"
                    " o.full_name AS owner_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " WHERE a.status='approved'"
                    " ORDER BY a.appointment_date ASC LIMIT 30"
                )
                eligible = cur.fetchall()
                cur.execute(
                    "SELECT a.id, a.appointment_date, p.name AS pet_name,"
                    " o.full_name AS owner_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN users o ON o.id=a.owner_id"
                    " WHERE a.status='approved'"
                    " ORDER BY a.appointment_date ASC LIMIT 30"
                )
                eligible = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Consult list failed: {e}")
        finally:
            conn.close()
    return render_template("admin/consultations.html", rows=rows, ckpi=ckpi, q=q,
                           rx=rx, eligible=eligible)


@app.route("/admin/consultations/new", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_consultation_new():
    vet_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/consultation_form.html", eligible=[])
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
                try:
                    bill_amount = float(request.form.get("bill_amount", "") or 0)
                except ValueError:
                    bill_amount = -1
                if appt_id <= 0 or not diagnosis:
                    flash("Appointment and diagnosis are required.", "danger")
                elif bill_amount < 0:
                    flash("Bill amount must be zero or more.", "danger")
                else:
                    cur.execute(
                        "SELECT pet_id FROM appointments"
                        " WHERE id=%s AND status='approved' LIMIT 1",
                        (appt_id,),
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
                        if bill_amount > 0:
                            cur.execute(
                                "SELECT owner_id FROM appointments WHERE id=%s LIMIT 1",
                                (appt_id,))
                            owner_id = cur.fetchone()["owner_id"]
                            cur.execute(
                                "INSERT INTO invoices (owner_id, appointment_id,"
                                " consultation_id, amount) VALUES (%s,%s,%s,%s)",
                                (owner_id, appt_id, consult_id, bill_amount))
                            flash(f"Consultation logged + bill ₱{bill_amount:.2f} issued.",
                                  "success")
                        else:
                            flash("Consultation logged.", "success")
                        conn.close()
                        return redirect(url_for("admin_consultation_detail",
                                                consult_id=consult_id))
            cur.execute(
                "SELECT a.id, a.appointment_date, p.name AS pet_name, o.full_name AS owner_name"
                " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " JOIN users o ON o.id=a.owner_id"
                " WHERE a.status='approved'"
                " ORDER BY a.appointment_date ASC LIMIT 30"
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
    return render_template("admin/consultation_form.html", eligible=eligible)


@app.route("/admin/consultations/<int:consult_id>", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_consultation_detail(consult_id):
    vet_id = int(session["user_id"])
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_consultations"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.*, p.name AS pet_name FROM consultations c"
                " JOIN pets p ON p.id=c.pet_id WHERE c.id=%s LIMIT 1", (consult_id,)
            )
            consult = cur.fetchone()
            if not consult:
                flash("Consultation not found.", "danger")
                return redirect(url_for("admin_consultations"))
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
        return redirect(url_for("admin_consultations"))
    finally:
        conn.close()
    can_edit = True  # shared surface: admin + staff operate jointly
    return render_template("admin/consultation_detail.html",
                           consult=consult, rxs=rxs, items=items, can_edit=can_edit)


# ---------------- Inventory (admin) ----------------

INV_CATEGORIES = ["Medicine", "Vaccine", "Food", "Equipment", "Hygiene", "Other"]


@app.route("/admin/inventory", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_inventory():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "All").strip()
    if category != "All" and category not in INV_CATEGORIES:
        category = "All"
    ikpi = {"total": 0, "low": 0, "out": 0, "value": "0.00"}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/inventory.html", items=[], categories=INV_CATEGORIES,
                           ikpi={"total": 0, "low": 0, "out": 0, "value": "0.00"},
                           q="", category="All")
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
            cur.execute("SELECT COUNT(*) AS c FROM inventory"
                        f" WHERE {period_cond('created_at', period)}")
            ikpi["total"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM inventory"
                        " WHERE quantity BETWEEN 1 AND 5")
            ikpi["low"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM inventory WHERE quantity<=0")
            ikpi["out"] = cur.fetchone()["c"]
            cur.execute("SELECT COALESCE(SUM(quantity*price),0) AS t FROM inventory")
            ikpi["value"] = cur.fetchone()["t"]
            sel = ("SELECT * FROM inventory"
                   f" WHERE {period_cond('created_at', period)}")
            params = []
            if category != "All":
                sel += " AND category=%s"
                params.append(category)
            if q:
                sel += " AND item_name LIKE %s"
                params.append(f"%{q}%")
            sel += " ORDER BY item_name ASC LIMIT 100"
            cur.execute(sel, params)
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
    return render_template("admin/inventory.html", items=items, ikpi=ikpi, q=q,
                           category=category, categories=INV_CATEGORIES)


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
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    vstatus = request.args.get("vstatus", "all").strip()
    if vstatus not in ("all", "unpaid", "paid", "cancelled"):
        vstatus = "all"
    vkpi = {"unpaid_n": 0, "unpaid": "0.00", "paid": 0, "cancelled": 0}
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
            pcond = period_cond('i.issued_date', period)
            cur.execute("SELECT COUNT(*) AS c FROM invoices i"
                        f" WHERE i.status='unpaid' AND {pcond}")
            vkpi["unpaid_n"] = cur.fetchone()["c"]
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM invoices i"
                        f" WHERE i.status='unpaid' AND {pcond}")
            vkpi["unpaid"] = cur.fetchone()["t"]
            for key, st in (("paid", "paid"), ("cancelled", "cancelled")):
                cur.execute("SELECT COUNT(*) AS c FROM invoices i"
                            f" WHERE i.status=%s AND {pcond}", (st,))
                vkpi[key] = cur.fetchone()["c"]
            sel = ("SELECT i.*, o.full_name AS owner_name FROM invoices i"
                   " JOIN users o ON o.id=i.owner_id"
                   f" WHERE {pcond}")
            params = []
            if vstatus != "all":
                sel += " AND i.status=%s"
                params.append(vstatus)
            if q:
                sel += " AND o.full_name LIKE %s"
                params.append(f"%{q}%")
            sel += " ORDER BY i.issued_date DESC LIMIT 50"
            cur.execute(sel, params)
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
                           vkpi=vkpi, q=q, vstatus=vstatus, statuses=INV_STATUSES)


@app.route("/admin/invoices/<int:inv_id>/receipt")
@role_required("admin", "staff")
def admin_invoice_receipt(inv_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_invoices"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.*, o.full_name AS owner_name, o.phone,"
                " p.name AS pet_name, a.appointment_date, a.reason"
                " FROM invoices i JOIN users o ON o.id=i.owner_id"
                " LEFT JOIN pets p ON p.id=(SELECT pet_id FROM appointments"
                " WHERE id=i.appointment_id LIMIT 1)"
                " LEFT JOIN appointments a ON a.id=i.appointment_id"
                " WHERE i.id=%s LIMIT 1", (inv_id,))
            inv = cur.fetchone()
            if not inv:
                flash("Invoice not found.", "danger")
                return redirect(url_for("admin_invoices"))
    except pymysql.MySQLError as e:
        print(f"Receipt failed: {e}")
        flash("Could not load receipt.", "danger")
        return redirect(url_for("admin_invoices"))
    finally:
        conn.close()
    return render_template("admin/receipt.html", inv=inv)


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


# ---------------- Users (admin creates all accounts) ----------------

USER_ROLES = ["admin", "vet", "staff", "owner"]


@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    ukpi = {"total": 0, "admins": 0, "staff": 0, "vets": 0, "pending": 0}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/users.html", users=[], roles=USER_ROLES,
                           ukpi={"total": 0, "admins": 0, "staff": 0, "vets": 0,
                                 "pending": 0},
                           q="", astatus="all")
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
                        "INSERT INTO users (full_name, username, email, password, role,"
                        " status) VALUES (%s,%s,%s,%s,%s,'pending')",
                        (full_name, username, email, hashed, role))
                    flash(f"User {username} ({role}) created as pending.", "success")
                    conn.close()
                    return redirect(url_for("admin_users"))
                for e in errors:
                    flash(e, "danger")
            astatus = request.args.get("astatus", "all").strip()
            if astatus not in ("all", "pending", "approved", "rejected"):
                astatus = "all"
            sel = ("SELECT id, full_name, username, email, role, status, created_at"
                   " FROM users"
                   f" WHERE {period_cond('created_at', period)}")
            params = []
            if astatus != "all":
                sel += " AND status=%s"
                params.append(astatus)
            if q:
                sel += " AND (username LIKE %s OR full_name LIKE %s)"
                params.extend([f"%{q}%"] * 2)
            sel += " ORDER BY role, username ASC"
            cur.execute(sel, params or None)
            users = cur.fetchall()
            pcond = period_cond('created_at', period)
            cur.execute("SELECT COUNT(*) AS c FROM users"
                        f" WHERE {pcond}")
            ukpi["total"] = cur.fetchone()["c"]
            for key, role in (("admins", "admin"), ("staff", "staff"),
                              ("vets", "vet"), ("pending", None)):
                if role is None:
                    cur.execute("SELECT COUNT(*) AS c FROM users"
                                f" WHERE status='pending' AND {pcond}")
                else:
                    cur.execute("SELECT COUNT(*) AS c FROM users"
                                f" WHERE role=%s AND {pcond}", (role,))
                ukpi[key] = cur.fetchone()["c"]
    except pymysql.MySQLError as e:
        print(f"Admin users failed: {e}")
        flash("Could not load users.", "danger")
        users = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/users.html", users=users, ukpi=ukpi, q=q,
                           astatus=astatus, roles=USER_ROLES)


@app.route("/admin/users/<int:user_id>/status", methods=["POST"])
@role_required("admin")
def admin_user_status(user_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in ("approved", "rejected"):
        flash("Invalid status.", "danger")
    elif user_id == int(session["user_id"]):
        flash("You cannot change your own status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE users SET status=%s WHERE id=%s",
                                (new_status, user_id))
                flash(f"Account → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"User status failed: {e}")
                flash("Could not update account.", "danger")
            finally:
                conn.close()
    return redirect(url_for("admin_users"))


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


# ---------------- Client records (no owner logins; staff-operated) ----------------

@app.route("/admin/clients")
@role_required("admin", "staff")
def admin_clients():
    q = request.args.get("q", "").strip()
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    ckpi = {"total": 0, "active": 0, "new": 0}
    rows = []
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                pcond = period_cond('u.created_at', period)
                cur.execute("SELECT COUNT(*) AS c FROM users u"
                            f" WHERE u.role='owner' AND {pcond}")
                ckpi["total"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(DISTINCT a.owner_id) AS c FROM appointments a"
                            " JOIN users u ON u.id=a.owner_id"
                            f" WHERE u.role='owner' AND {period_cond('a.created_at', period)}")
                ckpi["active"] = cur.fetchone()["c"]
                ckpi["new"] = ckpi["total"]
                base = ("SELECT u.id, u.full_name, u.phone,"
                        " (SELECT COUNT(*) FROM pets p WHERE p.owner_id=u.id) AS pets,"
                        " (SELECT COUNT(*) FROM appointments a WHERE a.owner_id=u.id) AS visits"
                        f" FROM users u WHERE u.role='owner'"
                        f" AND {pcond}")
                if q:
                    like = f"%{q}%"
                    cur.execute(base + " AND (u.full_name LIKE %s OR u.phone LIKE %s)"
                                " ORDER BY u.full_name ASC LIMIT 50", (like, like))
                else:
                    cur.execute(base + " ORDER BY u.full_name ASC LIMIT 50")
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Clients failed: {e}")
            flash("Could not load clients.", "danger")
        finally:
            conn.close()
    return render_template("admin/clients.html", rows=rows, q=q, ckpi=ckpi)


@app.route("/admin/clients/<int:owner_id>", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_client_detail(owner_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_clients"))
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                name = request.form.get("full_name", "").strip()
                phone = "".join(c for c in request.form.get("phone", "") if c.isdigit())
                if not name or len(phone) < 7:
                    flash("Name and a valid phone are required.", "danger")
                else:
                    cur.execute("UPDATE users SET full_name=%s, phone=%s"
                                " WHERE id=%s AND role='owner'", (name, phone, owner_id))
                    flash("Client record updated.", "success")
                    conn.close()
                    return redirect(url_for("admin_client_detail", owner_id=owner_id))
            cur.execute("SELECT id, full_name, phone, created_at FROM users"
                        " WHERE id=%s AND role='owner' LIMIT 1", (owner_id,))
            owner = cur.fetchone()
            if not owner:
                flash("Client not found.", "danger")
                conn.close()
                return redirect(url_for("admin_clients"))
            cur.execute("SELECT * FROM pets WHERE owner_id=%s ORDER BY name ASC",
                        (owner_id,))
            pets = cur.fetchall()
            cur.execute(
                "SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,"
                " p.name AS pet_name FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " WHERE a.owner_id=%s ORDER BY a.appointment_date DESC LIMIT 20",
                (owner_id,))
            visits = cur.fetchall()
            cur.execute("SELECT id, amount, status, issued_date FROM invoices"
                        " WHERE owner_id=%s ORDER BY issued_date DESC LIMIT 20", (owner_id,))
            bills = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Client detail failed: {e}")
        flash("Could not load client.", "danger")
        return redirect(url_for("admin_clients"))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/client_detail.html", owner=owner, pets=pets,
                           visits=visits, bills=bills)


@app.route("/admin/pets")
@role_required("admin", "staff")
def admin_pets():
    species = request.args.get("species", "All").strip()
    if species not in SPECIES_CHOICES:
        species = "All"
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    pkpi = {"total": 0, "dogs": 0, "cats": 0, "others": 0}
    rows = []
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                pcond = period_cond('p.created_at', period)
                cur.execute("SELECT COUNT(*) AS c FROM pets p"
                            f" WHERE {pcond}")
                pkpi["total"] = cur.fetchone()["c"]
                for key, sp in (("dogs", "Dog"), ("cats", "Cat")):
                    cur.execute("SELECT COUNT(*) AS c FROM pets p"
                                f" WHERE p.species=%s AND {pcond}", (sp,))
                    pkpi[key] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM pets p"
                            f" WHERE p.species NOT IN ('Dog','Cat') AND {pcond}")
                pkpi["others"] = cur.fetchone()["c"]
                base = ("SELECT p.*, o.full_name AS owner_name, o.phone"
                        " FROM pets p JOIN users o ON o.id=p.owner_id"
                        f" WHERE {pcond}")
                params = []
                if species != "All":
                    base += " AND p.species=%s"
                    params.append(species)
                if q:
                    like = f"%{q}%"
                    base += " AND (p.name LIKE %s OR o.full_name LIKE %s)"
                    params.extend([like, like])
                base += " ORDER BY p.name ASC LIMIT 100"
                cur.execute(base, params)
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Pets failed: {e}")
            flash("Could not load pets.", "danger")
        finally:
            conn.close()
    return render_template("admin/pets.html", rows=rows, species=species, q=q,
                           pkpi=pkpi, species_choices=["All"] + SPECIES_CHOICES)


@app.route("/admin/pets/<int:pet_id>/edit", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_pet_edit(pet_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_pets"))
    try:
        with conn.cursor() as cur:
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
                if not name or species not in SPECIES_CHOICES or \
                        (gender is not None and gender not in GENDER_CHOICES):
                    flash("Check name, species, and gender.", "danger")
                else:
                    cur.execute(
                        "UPDATE pets SET name=%s, species=%s, breed=%s, age=%s,"
                        " gender=%s, weight=%s WHERE id=%s",
                        (name, species, breed, age, gender, weight, pet_id))
                    flash("Pet record updated.", "success")
                    conn.close()
                    return redirect(url_for("admin_pets", species=species))
            cur.execute("SELECT p.*, o.full_name AS owner_name FROM pets p"
                        " JOIN users o ON o.id=p.owner_id WHERE p.id=%s LIMIT 1",
                        (pet_id,))
            pet = cur.fetchone()
            if not pet:
                flash("Pet not found.", "danger")
                conn.close()
                return redirect(url_for("admin_pets"))
    except pymysql.MySQLError as e:
        print(f"Pet edit failed: {e}")
        flash("Could not update pet.", "danger")
        return redirect(url_for("admin_pets"))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/pet_form.html", pet=pet,
                           species_choices=SPECIES_CHOICES,
                           gender_choices=GENDER_CHOICES)


@app.route("/admin/walk-in", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_walkin():
    """Front-desk walk-in: name + phone + pet + service in one form.
    Creates owner (phone dedupe) + pet + an APPROVED visit today, optionally queued.
    GET also serves the walk-in history (source='walkin')."""
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    wstatus = request.args.get("wstatus", "all").strip()
    if wstatus not in ("approved", "completed", "cancelled"):
        wstatus = "all"
    wkpi = {"total": 0, "today": 0}
    rows = []
    if request.method == "POST":
        name = request.form.get("guest_name", "").strip()
        phone = "".join(c for c in request.form.get("phone", "") if c.isdigit())
        pet_name = request.form.get("pet_name", "").strip()
        species = request.form.get("species", "").strip()
        service = request.form.get("service", "").strip()
        appt_time = request.form.get("appointment_time", "").strip() or "09:00"
        to_queue = request.form.get("to_queue") == "1"
        errors = []
        if not name:
            errors.append("Client name is required.")
        if len(phone) < 7:
            errors.append("A valid phone number is required.")
        if not pet_name:
            errors.append("Pet name is required.")
        if species not in SPECIES_CHOICES:
            errors.append("Please select a valid species.")
        if service not in GUEST_SERVICES:
            errors.append("Please select a valid service.")
        if not appt_time:
            errors.append("Time is required.")
        for e in errors:
            flash(e, "danger")
        if not errors:
            conn = db()
            if conn is None:
                flash("Database connection failed.", "danger")
            else:
                try:
                    import secrets
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM users WHERE phone=%s AND role='owner'"
                                    " LIMIT 1", (phone,))
                        row = cur.fetchone()
                        if row:
                            owner_id = row["id"]
                        else:
                            username = f"guest{phone}"[:40]
                            cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1",
                                        (username,))
                            if cur.fetchone():
                                username = f"{username}{secrets.randbelow(9000) + 1000}"[:50]
                            temp_pw = bcrypt.hashpw(secrets.token_urlsafe(16).encode(),
                                                    bcrypt.gensalt()).decode()
                            cur.execute(
                                "INSERT INTO users (full_name, username, email, password,"
                                " role, phone) VALUES (%s,%s,%s,%s,'owner',%s)",
                                (name, username, f"{username}@guest.local", temp_pw, phone))
                            owner_id = cur.lastrowid
                        cur.execute("INSERT INTO pets (owner_id, name, species)"
                                    " VALUES (%s,%s,%s)", (owner_id, pet_name, species))
                        pet_id = cur.lastrowid
                        cur.execute(
                            "INSERT INTO appointments (pet_id, owner_id, appointment_date,"
                            " appointment_time, reason, source, status)"
                            " VALUES (%s,%s,CURDATE(),%s,%s,'walkin','approved')",
                            (pet_id, owner_id, appt_time, service))
                        appt_id = cur.lastrowid
                        if to_queue:
                            cur.execute("SELECT COALESCE(MAX(queue_number),0)+1 AS nxt"
                                        " FROM clinic_queue WHERE queue_date=CURDATE()")
                            nxt = cur.fetchone()["nxt"]
                            cur.execute(
                                "INSERT INTO clinic_queue (appointment_id, pet_id, owner_id,"
                                " queue_number, queue_date) VALUES (%s,%s,%s,%s,CURDATE())",
                                (appt_id, pet_id, owner_id, nxt))
                            flash(f"Walk-in registered as queue #{nxt}.", "success")
                        else:
                            flash(f"Walk-in registered (visit #{appt_id}, approved).",
                                  "success")
                        conn.close()
                        return redirect(url_for("admin_walkin"))
                except pymysql.MySQLError as e:
                    print(f"Walk-in failed: {e}")
                    flash("Walk-in failed. Please try again.", "danger")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM appointments WHERE source='walkin'")
                wkpi["total"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM appointments"
                            " WHERE source='walkin' AND appointment_date=CURDATE()")
                wkpi["today"] = cur.fetchone()["c"]
                sel = ("SELECT a.id, a.appointment_date, a.appointment_time, a.reason,"
                       " a.status, p.name AS pet_name, o.full_name AS owner_name, o.phone,"
                       " (SELECT q.queue_number FROM clinic_queue q"
                       " WHERE q.appointment_id=a.id LIMIT 1) AS queue_no"
                       " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                       " JOIN users o ON o.id=a.owner_id"
                       f" WHERE a.source='walkin' AND {period_cond('a.appointment_date', period)}")
                params = []
                if wstatus != "all":
                    sel += " AND a.status=%s"
                    params.append(wstatus)
                if q:
                    like = f"%{q}%"
                    sel += (" AND (o.full_name LIKE %s OR o.phone LIKE %s"
                            " OR p.name LIKE %s)")
                    params.extend([like] * 3)
                sel += " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 100"
                cur.execute(sel, params)
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Walk-in history failed: {e}")
            flash("Could not load walk-in history.", "danger")
        finally:
            conn.close()
    return render_template("admin/walkin.html", today=date.today().isoformat(),
                           species_choices=SPECIES_CHOICES, services=GUEST_SERVICES,
                           rows=rows, wkpi=wkpi, q=q, wstatus=wstatus)


if __name__ == "__main__":
    import os

    # PORT env override: another course project (IM 103) already uses :5000,
    # so run this app with e.g. $env:PORT=5001; python app.py
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
