"""app.py - Pet Clinic Management System (Flask + MySQL via XAMPP)."""
import math
import os
import secrets
import time
from contextlib import contextmanager
from datetime import date, datetime, time as clock_time, timedelta
from functools import wraps

import bcrypt
import pymysql
from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)

import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("PETCLINIC_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# Sessions are tied to this process. Restarting app.py changes RUN_ID, so any
# cookie left over from a previous run is treated as logged out.
RUN_ID = secrets.token_hex(8)


def db():
    try:
        return config.get_connection()
    except pymysql.MySQLError as e:
        print(f"DB connection failed: {e}")
        return None


@contextmanager
def tx(conn):
    """Explicit transaction on top of the autocommit connection."""
    conn.begin()
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def verify_admin_password():
    """Re-check the signed-in admin's own password before a privileged write.

    Same idea as CPSC Inventory's destructive-confirm gate: a live session is
    not enough for deletes and approvals — the admin retypes their password.
    Fails closed on blank input, a non-admin session, a DB error, or a corrupt
    hash. Returns True/False only, never the row or the secret.
    """
    password = request.form.get("admin_password", "")
    user_id = session.get("user_id")
    if not password or not user_id or session.get("role") != "admin":
        return False
    conn = db()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE id=%s LIMIT 1",
                        (user_id,))
            row = cur.fetchone()
        try:
            return bool(row) and bcrypt.checkpw(
                password.encode(), row["password"].encode())
        except ValueError:
            return False
    except pymysql.MySQLError as e:
        print(f"Password re-check failed: {e}")
        return False
    finally:
        conn.close()


def list_services(active_only=False):
    """Fixed service menu with fees and inclusions, ordered for display."""
    conn = db()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            sql = ("SELECT id, name, fee, duration, inclusions, is_active"
                   " FROM services")
            if active_only:
                sql += " WHERE is_active=1"
            cur.execute(sql + " ORDER BY sort_order ASC, name ASC")
            return cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Services load failed: {e}")
        return []
    finally:
        conn.close()


def csrf_token():
    if not session.get("_csrf"):
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def session_run_guard():
    """Drop login state that belongs to an earlier server run (stale cookie)."""
    if session.get("user_id") and session.get("_run") != RUN_ID:
        session.clear()


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not sent or not secrets.compare_digest(sent, expected):
            abort(400, description="Invalid or missing CSRF token.")


LOGIN_WINDOW = 300
LOGIN_MAX_FAILS = 5
_login_fails = {}


def _login_key(username):
    return f"{request.remote_addr or '?'}|{username.lower()}"


def _login_locked(key):
    now = time.time()
    stamps = [t for t in _login_fails.get(key, ()) if now - t < LOGIN_WINDOW]
    if stamps:
        _login_fails[key] = stamps
    else:
        _login_fails.pop(key, None)
    return len(stamps) >= LOGIN_MAX_FAILS


def _session_user_ok():
    """True only while the logged-in account still exists and is approved.

    Also re-reads the role so a changed role takes effect on the next request.
    DB outage: keep the session (pages already degrade with their own errors).
    """
    uid = session.get("user_id")
    if not uid:
        return False
    conn = db()
    if conn is None:
        return True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role, status FROM users WHERE id=%s LIMIT 1", (uid,))
            row = cur.fetchone()
    except pymysql.MySQLError:
        return True
    finally:
        conn.close()
    if not row or row["status"] != "approved":
        return False
    if row["role"] != session.get("role"):
        session["role"] = row["role"]
    return True


def _deny_login():
    session.clear()
    return redirect(url_for("index", auth="open"))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _session_user_ok():
            return _deny_login()
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not _session_user_ok():
                return _deny_login()
            if session.get("role") not in roles:
                flash("Access denied for your role.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def dashboard_for(role):
    if role in ("admin", "staff"):
        # Shared management dashboard (view-only unless admin).
        return url_for("admin_dashboard")
    return url_for("index")  # clients are record rows; no login surface


# ---------------- Uploaded photos (avatars + vet portraits) ----------------

UPLOAD_MAX_BYTES = 3 * 1024 * 1024  # 3 MB per image
UPLOAD_EXTS = ("png", "jpg", "jpeg", "webp")


def _upload_dir(kind):
    path = os.path.join(app.static_folder, "uploads", kind)
    os.makedirs(path, exist_ok=True)
    return path


def _image_ext(blob):
    """Detect the real format from the file bytes, never from the name."""
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if blob.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "webp"
    return None


def _store_image(file_storage, kind, prefix):
    """Save one uploaded image. Returns (filename, None) or (None, message)."""
    raw = (file_storage.filename or "").strip()
    if not raw:
        return None, "Choose an image first."
    ext_in = os.path.splitext(raw)[1].lower().lstrip(".")
    blob = file_storage.read()
    if not blob:
        return None, "That file is empty."
    if len(blob) > UPLOAD_MAX_BYTES:
        return None, "Image is too large. Please keep it under 3 MB."
    ext = _image_ext(blob)
    if not ext or ext_in not in UPLOAD_EXTS:
        return None, "Use a PNG, JPG or WEBP image."
    name = f"{prefix}_{secrets.token_hex(8)}.{ext}"
    try:
        with open(os.path.join(_upload_dir(kind), name), "wb") as fh:
            fh.write(blob)
    except OSError as err:
        print(f"[_store_image] {err}")
        return None, "Could not save the image. Please try again."
    return name, None


def _delete_image(kind, filename):
    """Remove one stored image; basename-only so it cannot leave the folder."""
    name = os.path.basename(str(filename or "").strip())
    if not name:
        return
    try:
        target = os.path.join(_upload_dir(kind), name)
        if os.path.isfile(target):
            os.remove(target)
    except OSError as err:
        print(f"[_delete_image] {err}")


def _avatar_url():
    name = os.path.basename((session.get("avatar") or "").strip())
    if not name:
        return None
    return url_for("static", filename=f"uploads/avatars/{name}")


@app.template_global()
def vet_photo_url(name):
    name = os.path.basename(str(name or "").strip())
    if not name:
        return None
    return url_for("static", filename=f"uploads/vets/{name}")


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
    bell = {"pending": 0, "unpaid": "0.00"}
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT (SELECT COUNT(*) FROM appointments"
                    " WHERE status='pending') AS pending,"
                    " (SELECT COALESCE(SUM(amount),0) FROM invoices"
                    " WHERE status='unpaid') AS unpaid"
                )
                row = cur.fetchone()
                bell = {"pending": row["pending"], "unpaid": row["unpaid"]}
        except pymysql.MySQLError as e:
            print(f"Bell counts failed: {e}")
        finally:
            conn.close()
    total = ((bell["pending"] > 0)
             + (1 if float(bell["unpaid"] or 0) > 0 else 0))
    out.update({"bell": bell, "bell_total": total,
                "avatar_url": _avatar_url()})
    return out


def safe_next(value, default):
    """Allow only relative in-app redirects (no open-redirect)."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return default


PER_PAGE = 20


def _page_no():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def paginated(cur, count_sql, params, data_sql, per_page=PER_PAGE):
    """COUNT + LIMIT/OFFSET for one list query; returns rows plus pager state."""
    page = _page_no()
    cur.execute(count_sql, params or None)
    total = cur.fetchone()["c"] or 0
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    cur.execute(data_sql + " LIMIT %s OFFSET %s",
                list(params or []) + [per_page, (page - 1) * per_page])
    return {"rows": cur.fetchall(), "page": page, "pages": pages,
            "total": total, "per_page": per_page,
            "start": (page - 1) * per_page + 1 if total else 0,
            "end": min(total, page * per_page)}


@app.template_global()
def page_url(n):
    """Link back to the same list page with a different ?page value."""
    args = request.args.to_dict(flat=True)
    args["page"] = n
    return url_for(request.endpoint, **(request.view_args or {}), **args)


@app.template_filter("person_name")
def person_name(value):
    """Display a person surname-first: 'Juan Dela Cruz' -> 'Dela Cruz, Juan'."""
    parts = str(value or "").split()
    if len(parts) < 2:
        return " ".join(parts)
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        text = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19], fmt).date()
            except ValueError:
                continue
    return None


def _to_hhmm(value):
    if isinstance(value, timedelta):
        hours, minutes = divmod(int(value.total_seconds()) // 60, 60)
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(value, datetime):
        return f"{value.hour:02d}:{value.minute:02d}"
    if isinstance(value, clock_time):
        return f"{value.hour:02d}:{value.minute:02d}"
    if isinstance(value, str) and ":" in value:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(value.strip(), fmt).time()
                return f"{t.hour:02d}:{t.minute:02d}"
            except ValueError:
                continue
    return ""


def _pretty_day(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"


@app.template_filter("pretty_date")
def pretty_date(value):
    """Render a date as 'August 30, 2026' (datetimes drop their time)."""
    d = _to_date(value)
    return _pretty_day(d) if d else "—"


@app.template_filter("pretty_when")
def pretty_when(value, time_value=None):
    """Render 'August 30, 2026 | 12:00' when a time exists, else the date."""
    d = _to_date(value)
    if d is None:
        return "—"
    hhmm = _to_hhmm(value if time_value is None else time_value)
    return f"{_pretty_day(d)} | {hhmm}" if hhmm else _pretty_day(d)


PH_MOBILE_HINT = ("Philippine mobile numbers must start with '09' and be exactly"
                  " 11 digits (e.g. 09123456789).")


@app.route("/")
def index():
    # Always the public landing page, even with an active session: opening the
    # app never drops straight into the admin dashboard. Signed-in staff get a
    # Dashboard shortcut instead of the Login button.
    vets = []
    services = []
    conn = db()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT full_name, specialty FROM vets WHERE is_active=1"
                            " ORDER BY full_name ASC")
                vets = cur.fetchall()
                cur.execute("SELECT id, name, fee, duration, inclusions"
                            " FROM services WHERE is_active=1"
                            " ORDER BY sort_order ASC, name ASC")
                services = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Landing vets failed: {e}")
        finally:
            conn.close()
    # auth: '' | 'open' (curtain auto-open) | 'failed' (curtain + error popup)
    auth = request.args.get("auth", "")
    if auth not in ("open", "failed"):
        auth = ""
    return render_template("landing.html", vets=vets, services=services,
                           today=date.today().isoformat(),
                           auth=auth, pre_next=request.args.get("next", ""),
                           pre_service=request.args.get("service", ""),
                           pre_date=request.args.get("date", ""),
                           pre_time=request.args.get("time", ""),
                           signed_in=("user_id" in session))


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
        key = _login_key(username)
        if _login_locked(key):
            flash("Too many failed attempts. Please wait a few minutes.", "danger")
            return redirect(url_for("index", auth="failed"))
        if not username or not password:
            _login_fails.setdefault(key, []).append(time.time())
            return redirect(url_for("index", auth="failed"))
        else:
            conn = db()
            if conn is None:
                flash("Database connection failed. Check XAMPP MySQL.", "danger")
            else:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, full_name, password, role, status, avatar"
                            " FROM users WHERE username=%s LIMIT 1",
                            (username,),
                        )
                        user = cur.fetchone()
                    try:
                        ok = bool(user) and bcrypt.checkpw(
                            password.encode(), user["password"].encode())
                    except ValueError:
                        ok = False  # corrupt hash in DB: fail closed, never 500
                    if ok and user["status"] != "approved":
                        # Correct password, inactive account: fail closed.
                        print("Login blocked: inactive account.")
                        _login_fails.setdefault(key, []).append(time.time())
                        return redirect(url_for("index", auth="failed"))
                    if ok:
                        _login_fails.pop(key, None)
                        session.clear()
                        session.permanent = True
                        session["_run"] = RUN_ID
                        session["user_id"] = int(user["id"])
                        session["full_name"] = user["full_name"]
                        session["role"] = user["role"]
                        session["avatar"] = (user.get("avatar") or "").strip() or None
                        target = safe_next(nxt, dashboard_for(user["role"]))
                        if not nxt and target == dashboard_for(user["role"]):
                            # Fresh login to home dashboard: play the skeleton once.
                            target += "?welcome=1"
                        return redirect(target)
                    # Failure: back to landing, curtain auto-opens with error popup.
                    _login_fails.setdefault(key, []).append(time.time())
                    return redirect(url_for("index", auth="failed", **{k: v for k, v in
                        (("next", nxt), ("service", pre_service),
                         ("date", pre_date), ("time", pre_time)) if v}))
                except pymysql.MySQLError as e:
                    print(f"Login failed: {e}")
                    return redirect(url_for("index", auth="failed"))
                finally:
                    conn.close()


@app.route("/logout", methods=["POST"])
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

    valid_services = [s["name"] for s in list_services(active_only=True)]
    if not valid_services:
        valid_services = GUEST_SERVICES
    errors = []
    if not name:
        errors.append("Your name is required.")
    if not phone:
        errors.append("Phone number is required.")
    elif not phone.startswith("09") or len(phone) != 11:
        errors.append("Invalid phone number: " + PH_MOBILE_HINT)
    if not pet_name:
        errors.append("Pet name is required.")
    if species not in SPECIES_CHOICES:
        errors.append("Please select a valid species.")
    if service not in valid_services:
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
        with tx(conn), conn.cursor() as cur:
            # Reuse client record by phone; otherwise auto-create one. A public
            # form never renames an existing client.
            cur.execute("SELECT id FROM clients WHERE phone=%s LIMIT 1", (phone,))
            row = cur.fetchone()
            if row:
                client_id = row["id"]
            else:
                cur.execute(
                    "INSERT INTO clients (full_name, phone) VALUES (%s,%s)",
                    (name, phone))
                client_id = cur.lastrowid
            # Reuse the pet registered for this client; only add a new row once.
            cur.execute(
                "SELECT id FROM pets WHERE client_id=%s AND LOWER(name)=LOWER(%s)"
                " AND species=%s LIMIT 1", (client_id, pet_name, species))
            pet = cur.fetchone()
            if pet:
                pet_id = pet["id"]
            else:
                cur.execute(
                    "INSERT INTO pets (client_id, name, species) VALUES (%s,%s,%s)",
                    (client_id, pet_name, species))
                pet_id = cur.lastrowid
            cur.execute(
                "INSERT INTO appointments"
                " (pet_id, client_id, appointment_date, appointment_time, reason,"
                " source, status)"
                " VALUES (%s,%s,%s,%s,%s,'guest','pending')",
                (pet_id, client_id, appt_date, appt_time, service))
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
    def picked(key):
        value = request.args.get(key, "All Time")
        return value if value in PERIODS else "All Time"

    # Every analytics card carries its own period filter.
    card_periods = {
        "bookings": picked("bk"),
        "queue": picked("qp"),
        "revenue": picked("rev"),
        "services": picked("svc"),
        "recent": picked("rec"),
    }
    kpi = {"pending": 0, "queue": 0, "unpaid": "0.00", "consults": 0}
    bell = {"pending": 0, "unpaid": 0}
    charts = None
    now_serving, up_next = None, []
    recent, pending_list = [], []
    conn = db()
    if conn is None:
        flash("Database connection failed. Check XAMPP MySQL.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                # Promote approved same-day appointments whose time has come.
                _auto_queue_due(conn, cur)
                # Snapshot KPIs (always current).
                cur.execute("SELECT COUNT(*) AS c FROM appointments WHERE status='pending'")
                kpi["pending"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM clinic_queue"
                    " WHERE queue_date=CURDATE() AND status IN ('waiting','serving')"
                )
                kpi["queue"] = cur.fetchone()["c"]
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) AS t FROM invoices WHERE status='unpaid'"
                )
                kpi["unpaid"] = cur.fetchone()["t"]
                # Snapshot KPI: consults done today.
                cur.execute(
                    "SELECT COUNT(*) AS c FROM consultations"
                    " WHERE DATE(consultation_date)=CURDATE()"
                )
                kpi["consults"] = cur.fetchone()["c"]
                # Bell mirrors live attention items.
                bell = {"pending": kpi["pending"], "unpaid": kpi["unpaid"]}
                # ---- Analytics datasets (adaptive buckets, zero-filled) ----
                def time_series(col, table, period, agg, extra=""):
                    """(labels, values) in hourly/daily/monthly buckets."""
                    today = date.today()
                    if period == "Today":
                        cur.execute(
                            f"SELECT HOUR({col}) AS b, {agg} AS v FROM {table}"
                            f" WHERE DATE({col})=CURDATE(){extra} GROUP BY b")
                        found = {int(r["b"]): r["v"] for r in cur.fetchall()}
                        labels = [f"{h % 12 or 12}{'AM' if h < 12 else 'PM'}"
                                  for h in range(24)]
                        return labels, [float(found.get(h, 0)) for h in range(24)]
                    if period == "This Week":
                        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
                        cur.execute(
                            f"SELECT DATE({col}) AS b, {agg} AS v FROM {table}"
                            f" WHERE {col}>=CURDATE()-INTERVAL 6 DAY{extra} GROUP BY b")
                        found = {str(r["b"]): r["v"] for r in cur.fetchall()}
                        return ([d.strftime("%a %d") for d in days],
                                [float(found.get(str(d), 0)) for d in days])
                    months = []
                    y, m = today.year, today.month
                    for _ in range(6):
                        months.append((y, m))
                        m -= 1
                        if m == 0:
                            m, y = 12, y - 1
                    months.reverse()
                    cur.execute(
                        f"SELECT DATE_FORMAT({col},'%Y-%m') AS b, {agg} AS v"
                        f" FROM {table}"
                        f" WHERE {col}>=DATE_SUB(CURDATE(), INTERVAL 6 MONTH)"
                        f"{extra} GROUP BY b")
                    found = {r["b"]: r["v"] for r in cur.fetchall()}
                    return ([date(y, m, 1).strftime("%b '%y") for y, m in months],
                            [float(found.get(f"{y}-{m:02d}", 0)) for y, m in months])

                b_labels, bookings = time_series(
                    "created_at", "appointments", card_periods["bookings"], "COUNT(*)")
                r_labels, revenue = time_series(
                    "issued_date", "invoices", card_periods["revenue"],
                    "COALESCE(SUM(amount),0)", " AND status='paid'")
                qwhere = period_cond("queue_date", card_periods["queue"])
                cur.execute(
                    "SELECT status, COUNT(*) AS c FROM clinic_queue"
                    + ("" if qwhere == "1=1" else f" WHERE {qwhere}")
                    + " GROUP BY status"
                )
                qmap = {r["status"]: r["c"] for r in cur.fetchall()}
                queue_load = [qmap.get(s, 0) for s in ("waiting", "serving", "done", "skipped")]
                cur.execute(
                    "SELECT reason, COUNT(*) AS c FROM appointments"
                    f" WHERE {period_cond('created_at', card_periods['services'])}"
                    " GROUP BY reason ORDER BY c DESC LIMIT 5"
                )
                top_rows = cur.fetchall()
                charts = {
                    "bookings": {"labels": b_labels, "values": bookings},
                    "revenue": {"labels": r_labels, "values": revenue},
                    "queue": {"labels": ["Waiting", "Serving", "Done", "Skipped"],
                              "values": queue_load},
                    "services": {
                        "labels": [r["reason"] or "Unspecified" for r in top_rows],
                        "values": [r["c"] for r in top_rows]},
                }
                # Now-serving strip (same source as the queue board).
                cur.execute(
                    "SELECT q.queue_number, p.name AS pet_name, o.full_name AS owner_name"
                    " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                    " JOIN clients o ON o.id=q.client_id"
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
                    " JOIN clients o ON o.id=a.client_id"
                    " LEFT JOIN vets v ON v.id=a.vet_id"
                    f" WHERE {period_cond('a.created_at', card_periods['recent'])}"
                    " ORDER BY a.created_at DESC LIMIT 8"
                )
                recent = cur.fetchall()
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.appointment_time, a.reason,"
                    " p.name AS pet_name, o.full_name AS owner_name, o.phone"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN clients o ON o.id=a.client_id"
                    " WHERE a.status='pending'"
                    " ORDER BY a.created_at ASC LIMIT 10"
                )
                pending_list = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Admin dashboard failed: {e}")
            flash("Could not load dashboard data.", "danger")
        finally:
            conn.close()
    bell_total = (bell["pending"] > 0) + (1 if float(bell["unpaid"] or 0) > 0 else 0)
    return render_template("admin/dashboard.html", kpi=kpi, bell=bell,
                           bell_total=bell_total, recent=recent,
                           pending_list=pending_list, charts=charts,
                           now_serving=now_serving, up_next=up_next,
                           card_periods=card_periods, periods=PERIODS)


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
    pg = None
    clients, pets, vets = [], [], []
    akpi = {"total": 0, "pending": 0, "approved": 0, "completed": 0,
            "cancelled": 0}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                pcond = period_cond('a.appointment_date', period)
                for key, cond in (("total", "1=1"), ("pending", "a.status='pending'"),
                                  ("approved", "a.status='approved'"),
                                  ("completed", "a.status='completed'"),
                                  ("cancelled", "a.status='cancelled'")):
                    cur.execute("SELECT COUNT(*) AS c FROM appointments a"
                                f" WHERE {pcond} AND {cond}")
                    akpi[key] = cur.fetchone()["c"]
                base = (" FROM appointments a JOIN pets p ON p.id=a.pet_id"
                        " JOIN clients o ON o.id=a.client_id"
                        " LEFT JOIN vets v ON v.id=a.vet_id")
                where = f" WHERE {pcond}"
                params = []
                if status != "all":
                    where += " AND a.status=%s"
                    params.append(status)
                if q:
                    like = f"%{q}%"
                    where += (" AND (p.name LIKE %s OR o.full_name LIKE %s"
                              " OR o.phone LIKE %s OR a.reason LIKE %s)")
                    params.extend([like] * 4)
                pg = paginated(
                    cur, "SELECT COUNT(*) AS c" + base + where, params,
                    "SELECT a.id, a.appointment_date, a.appointment_time,"
                    " a.reason, a.status, p.name AS pet_name,"
                    " o.full_name AS owner_name, o.phone, v.full_name AS vet_name"
                    + base + where +
                    " ORDER BY a.appointment_date DESC, a.appointment_time DESC")
                rows = pg["rows"]
                cur.execute("SELECT id, full_name, phone FROM clients"
                            " ORDER BY full_name ASC")
                clients = cur.fetchall()
                cur.execute("SELECT id, client_id, name FROM pets"
                            " ORDER BY name ASC")
                pets = cur.fetchall()
                cur.execute("SELECT id, full_name FROM vets WHERE is_active=1"
                            " ORDER BY full_name ASC")
                vets = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Admin appointments failed: {e}")
            flash("Could not load appointments.", "danger")
        finally:
            conn.close()
    return render_template("admin/appointments.html", rows=rows, status=status, q=q,
                           akpi=akpi, pager=pg, clients=clients, pets=pets,
                           vets=vets, services=list_services(active_only=True),
                           default_services=GUEST_SERVICES,
                           species_choices=SPECIES_CHOICES,
                           statuses=["all", "pending", "approved", "completed", "cancelled"])


@app.route("/admin/appointments/new", methods=["POST"])
@role_required("admin", "staff")
def admin_appointment_new():
    """Staff-entered booking: used for walk-in clients and phone bookings."""
    client_raw = request.form.get("client_id", "").strip()
    owner_name = request.form.get("owner_name", "").strip()
    phone = "".join(c for c in request.form.get("phone", "") if c.isdigit())
    pet_raw = request.form.get("pet_id", "").strip()
    pet_name = request.form.get("pet_name", "").strip()
    species = request.form.get("species", "Dog")
    service = request.form.get("service", "").strip()
    appt_date = request.form.get("appointment_date", "").strip()
    appt_time = request.form.get("appointment_time", "").strip()
    vet_raw = request.form.get("vet_id", "").strip()
    notes = request.form.get("notes", "").strip() or None
    queue_now = request.form.get("add_to_queue") == "1"

    if species not in SPECIES_CHOICES:
        species = "Other"
    valid_services = [s["name"] for s in list_services(active_only=True)]
    if not valid_services:
        valid_services = GUEST_SERVICES
    if service not in valid_services:
        service = valid_services[0]

    errors = []
    try:
        when = date.fromisoformat(appt_date)
        if when < date.today():
            errors.append("The appointment date cannot be in the past.")
    except ValueError:
        errors.append("Choose a valid appointment date.")
    try:
        datetime.strptime(appt_time, "%H:%M")
    except ValueError:
        errors.append("Choose a valid appointment time.")
    if not client_raw.isdigit():
        if not owner_name:
            errors.append("Owner name is required.")
        if not phone:
            errors.append("Owner phone number is required.")
        elif not phone.startswith("09") or len(phone) != 11:
            errors.append("Invalid phone number: " + PH_MOBILE_HINT)
    if not pet_raw.isdigit() and not pet_name:
        errors.append("Pet name is required.")

    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_appointments"))
    try:
        with conn.cursor() as cur:
            client = None
            if client_raw.isdigit():
                cur.execute("SELECT id, full_name FROM clients WHERE id=%s"
                            " LIMIT 1", (int(client_raw),))
                client = cur.fetchone()
                if not client:
                    errors.append("That client no longer exists.")
            elif phone and phone.startswith("09") and len(phone) == 11:
                cur.execute("SELECT id, full_name FROM clients WHERE phone=%s"
                            " LIMIT 1", (phone,))
                client = cur.fetchone()

            pet = None
            if pet_raw.isdigit():
                cur.execute("SELECT id, client_id FROM pets WHERE id=%s LIMIT 1",
                            (int(pet_raw),))
                pet = cur.fetchone()
                if not pet:
                    errors.append("That pet no longer exists.")
                elif client and pet["client_id"] != client["id"]:
                    errors.append("That pet belongs to a different client.")

            vet_id = None
            if vet_raw.isdigit():
                cur.execute("SELECT id FROM vets WHERE id=%s AND is_active=1"
                            " LIMIT 1", (int(vet_raw),))
                if cur.fetchone():
                    vet_id = int(vet_raw)

            if errors:
                for msg in errors:
                    flash(msg, "danger")
                return redirect(url_for("admin_appointments"))

            with tx(conn):
                if client is None:
                    cur.execute(
                        "INSERT INTO clients (full_name, phone) VALUES (%s,%s)",
                        (owner_name, phone))
                    client_id = cur.lastrowid
                else:
                    client_id = client["id"]
                if pet is None:
                    cur.execute(
                        "INSERT INTO pets (client_id, name, species)"
                        " VALUES (%s,%s,%s)", (client_id, pet_name, species))
                    pet_id = cur.lastrowid
                else:
                    pet_id = pet["id"]
                cur.execute(
                    "INSERT INTO appointments (pet_id, client_id, vet_id,"
                    " appointment_date, appointment_time, reason, source, status)"
                    " VALUES (%s,%s,%s,%s,%s,%s,'walkin','approved')",
                    (pet_id, client_id, vet_id, appt_date, appt_time, service))
                appt_id = cur.lastrowid
            flash(f"Appointment #{appt_id} booked for {pet_name}.", "success")
            if queue_now:
                nxt, err = _queue_ticket(conn, cur, appt_id, pet_id,
                                         client_id, vet_id)
                if nxt:
                    flash(f"Added to today's queue as #{nxt}.", "success")
                else:
                    flash(err, "danger")
    except pymysql.MySQLError as e:
        print(f"New appointment failed: {e}")
        flash("Could not save the appointment.", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_appointments"))


@app.route("/admin/appointments/<int:appt_id>/status", methods=["POST"])
@role_required("admin")
def admin_appointment_status(appt_id):
    if not verify_admin_password():
        flash("Wrong admin password — the booking was not changed.", "danger")
        ref = request.referrer or ""
        if "/admin/appointments" in ref and "/status" not in ref:
            return redirect(ref)
        return redirect(url_for("admin_appointments"))
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
                    cur.execute("SELECT id FROM appointments WHERE id=%s LIMIT 1",
                                (appt_id,))
                    if not cur.fetchone():
                        flash(f"Appointment #{appt_id} not found.", "danger")
                    else:
                        cur.execute(
                            "UPDATE appointments SET status=%s WHERE id=%s",
                            (new_status, appt_id),
                        )
                        if new_status == "approved":
                            # Same-day slots join the line as soon as their time
                            # arrives; afternoon/future slots wait for that time.
                            _auto_queue_due(conn, cur)
                            cur.execute(
                                "SELECT queue_number FROM clinic_queue"
                                " WHERE appointment_id=%s LIMIT 1", (appt_id,))
                            ticket = cur.fetchone()
                            if ticket:
                                flash(f"Appointment #{appt_id} approved and added"
                                      f" to queue as #{ticket['queue_number']}.",
                                      "success")
                            else:
                                flash(f"Appointment #{appt_id} approved — it will"
                                      " join the queue automatically when its"
                                      " scheduled time arrives.", "success")
                        else:
                            flash(f"Appointment #{appt_id} → {new_status}.",
                                  "success")
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


def _queue_filters(period="All Time", q="", status="all"):
    where = (" WHERE q.queue_date<=CURDATE()"
             f" AND {period_cond('q.queue_date', period)}")
    params = []
    if status in QUEUE_STATUSES:
        where += " AND q.status=%s"
        params.append(status)
    if q:
        like = f"%{q}%"
        where += " AND (p.name LIKE %s OR o.full_name LIKE %s)"
        params.extend([like, like])
    return where, params


def _queue_ticket(conn, cur, appt_id, pet_id, client_id, vet_id):
    """Give an approved appointment the next per-day queue number.
    Returns (number, None) or (None, message)."""
    for attempt in range(2):
        try:
            with tx(conn):
                cur.execute(
                    "SELECT COALESCE(MAX(queue_number),0)+1 AS nxt"
                    " FROM clinic_queue WHERE queue_date=CURDATE()")
                nxt = cur.fetchone()["nxt"]
                cur.execute(
                    "INSERT INTO clinic_queue"
                    " (appointment_id, pet_id, client_id, vet_id,"
                    " queue_number, queue_date)"
                    " VALUES (%s,%s,%s,%s,%s,CURDATE())",
                    (appt_id, pet_id, client_id, vet_id, nxt))
            return nxt, None
        except pymysql.IntegrityError:
            if attempt:
                return None, "That appointment is already queued."
        except pymysql.MySQLError as err:
            print(f"Queue ticket failed: {err}")
            return None, "Could not add to the queue."
    return None, "Could not add to the queue."


def _auto_queue_due(conn, cur):
    """Queue today's approved appointments whose slot time has arrived.
    Future dates and later-in-the-day slots stay out until due. One ticket per
    appointment (clinic_queue.appointment_id is UNIQUE); deleting a ticket sets
    appointments.auto_queue=0 so it is not recreated automatically."""
    cur.execute(
        "SELECT a.id, a.pet_id, a.client_id, a.vet_id"
        " FROM appointments a"
        " LEFT JOIN clinic_queue q ON q.appointment_id=a.id"
        " WHERE a.status='approved' AND a.auto_queue=1 AND q.id IS NULL"
        " AND a.appointment_date=CURDATE() AND a.appointment_time<=CURTIME()"
        " ORDER BY a.appointment_time ASC")
    added = 0
    for appt in cur.fetchall():
        nxt, _err = _queue_ticket(conn, cur, appt["id"], appt["pet_id"],
                                  appt["client_id"], appt["vet_id"])
        if nxt:
            added += 1
    return added


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
    pg = None
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/queue.html", queue=[], eligible=[], qkpi=qkpi,
                               q=q, qstatus=qstatus, now_serving=now_serving,
                               up_next=up_next, statuses=QUEUE_STATUSES, pager=None)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                try:
                    appt_id = int(request.form.get("appointment_id", 0))
                except ValueError:
                    appt_id = 0
                if appt_id > 0:
                    cur.execute(
                        "SELECT pet_id, client_id, vet_id FROM appointments"
                        " WHERE id=%s AND status='approved' LIMIT 1", (appt_id,)
                    )
                    appt = cur.fetchone()
                    if not appt:
                        flash("Only approved appointments can join the queue.", "danger")
                    else:
                        cur.execute(
                            "SELECT id FROM clinic_queue WHERE appointment_id=%s"
                            " LIMIT 1", (appt_id,))
                        if cur.fetchone():
                            flash("That appointment already has a queue ticket.",
                                  "danger")
                        else:
                            nxt, err = _queue_ticket(
                                conn, cur, appt_id, appt["pet_id"],
                                appt["client_id"], appt["vet_id"])
                            if nxt:
                                flash(f"Added to queue as #{nxt}.", "success")
                            else:
                                flash(err, "danger")
            queued_now = _auto_queue_due(conn, cur)
            if queued_now:
                flash(f"{queued_now} scheduled appointment(s) joined the queue"
                      " automatically.", "success")
            where, params = _queue_filters(period, q, qstatus)
            base = (" FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                    " JOIN clients o ON o.id=q.client_id"
                    " LEFT JOIN vets v ON v.id=q.vet_id")
            pg = paginated(
                cur, "SELECT COUNT(*) AS c" + base + where, params,
                "SELECT q.id, q.queue_number, q.status, q.appointment_id,"
                " q.queue_date, p.name AS pet_name, o.full_name AS owner_name,"
                " v.full_name AS vet_name" + base + where +
                " ORDER BY q.queue_date DESC, q.queue_number ASC")
            queue = pg["rows"]
            for key in ("waiting", "serving", "done", "skipped"):
                cur.execute("SELECT COUNT(*) AS c FROM clinic_queue"
                            f" WHERE status=%s AND {period_cond('queue_date', period)}",
                            (key,))
                qkpi[key] = cur.fetchone()["c"]
            # Now-serving strip: first serving ticket today + next 2 waiting.
            cur.execute(
                "SELECT q.queue_number, p.name AS pet_name, o.full_name AS owner_name"
                " FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
                " JOIN clients o ON o.id=q.client_id"
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
                           up_next=up_next, statuses=QUEUE_STATUSES, pager=pg)


@app.route("/admin/queue/<int:qid>/status", methods=["POST"])
@role_required("admin", "staff")
def admin_queue_status(qid):
    return _set_queue_status(qid, "admin_queue")


@app.route("/admin/queue/<int:qid>/delete", methods=["POST"])
@role_required("admin")
def admin_queue_delete(qid):
    if not verify_admin_password():
        flash("Wrong admin password — nothing was deleted.", "danger")
        return redirect(url_for("admin_queue"))
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT queue_number, appointment_id FROM clinic_queue"
                    " WHERE id=%s LIMIT 1", (qid,))
                ticket = cur.fetchone()
                if not ticket:
                    flash(f"Queue entry #{qid} not found.", "danger")
                else:
                    with tx(conn):
                        # Opt the appointment out of auto-queueing so deleting
                        # the ticket sticks instead of being recreated on the
                        # next dashboard/queue refresh.
                        cur.execute(
                            "UPDATE appointments SET auto_queue=0 WHERE id=%s",
                            (ticket["appointment_id"],))
                        cur.execute("DELETE FROM clinic_queue WHERE id=%s", (qid,))
                    flash(f"Queue ticket #{ticket['queue_number']} deleted.",
                          "success")
        except pymysql.MySQLError as e:
            print(f"Queue delete failed: {e}")
            flash("Could not delete the queue ticket.", "danger")
        finally:
            conn.close()
    return redirect(url_for("admin_queue"))


def _set_queue_status(qid, redirect_endpoint):
    new_status = request.form.get("status", "").strip()
    appointment_id = None
    if new_status not in QUEUE_STATUSES:
        flash("Invalid queue status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, appointment_id FROM clinic_queue"
                                " WHERE id=%s LIMIT 1", (qid,))
                    ticket = cur.fetchone()
                    if not ticket:
                        flash(f"Queue entry #{qid} not found.", "danger")
                    else:
                        cur.execute("UPDATE clinic_queue SET status=%s WHERE id=%s",
                                    (new_status, qid))
                        appointment_id = ticket["appointment_id"]
                        if new_status == "done":
                            flash("Queue entry done — record the consultation"
                                  " and billing to finish the visit.", "success")
                        else:
                            flash(f"Queue entry → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"Queue status failed: {e}")
                flash("Could not update queue.", "danger")
            finally:
                conn.close()
    # Marking done leads straight into a prefilled consultation + billing.
    if new_status == "done" and appointment_id:
        return redirect(url_for("admin_consultations", log=appointment_id))
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
    pg = None
    eligible = []
    active_vets = []
    services = []
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
                base = (" FROM consultations c JOIN pets p ON p.id=c.pet_id"
                        " JOIN vets u ON u.id=c.vet_id"
                        " LEFT JOIN services s ON s.id=c.service_id")
                where = f" WHERE {period_cond('c.consultation_date', period)}"
                params = []
                if rx == "yes":
                    where += (" AND EXISTS (SELECT 1 FROM prescriptions_treatments r"
                              " WHERE r.consultation_id=c.id)")
                elif rx == "no":
                    where += (" AND NOT EXISTS (SELECT 1 FROM prescriptions_treatments r"
                              " WHERE r.consultation_id=c.id)")
                if q:
                    like = f"%{q}%"
                    where += " AND (c.diagnosis LIKE %s OR p.name LIKE %s)"
                    params.extend([like, like])
                pg = paginated(
                    cur, "SELECT COUNT(*) AS c" + base + where, params,
                    "SELECT c.id, c.diagnosis, c.consultation_date,"
                    " p.name AS pet_name, u.full_name AS vet_name,"
                    " s.name AS service_name" + base + where +
                    " ORDER BY c.consultation_date DESC")
                rows = pg["rows"]
                cur.execute(
                    "SELECT a.id, a.appointment_date, a.reason, a.vet_id,"
                    " p.name AS pet_name, o.full_name AS owner_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN clients o ON o.id=a.client_id"
                    " WHERE a.status='approved'"
                    " ORDER BY a.appointment_date DESC, a.id DESC LIMIT 50"
                )
                eligible = cur.fetchall()
                cur.execute(
                    "SELECT id, full_name FROM vets WHERE is_active=1"
                    " ORDER BY full_name ASC"
                )
                active_vets = cur.fetchall()
                cur.execute(
                    "SELECT id, name, fee, duration, inclusions FROM services"
                    " WHERE is_active=1 ORDER BY sort_order ASC, name ASC"
                )
                services = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Consult list failed: {e}")
        finally:
            conn.close()
    log_raw = request.args.get("log", "").strip()
    log_appt = int(log_raw) if log_raw.isdigit() else None
    return render_template("admin/consultations.html", rows=rows, ckpi=ckpi, q=q,
                           rx=rx, eligible=eligible, active_vets=active_vets,
                           services=services, log_appt=log_appt, pager=pg)


@app.route("/admin/consultations/new", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_consultation_new():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/consultation_form.html", eligible=[],
                               active_vets=[], services=[], prefill=None)
    eligible, active_vets, services, prefill = [], [], [], None
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                try:
                    appt_id = int(request.form.get("appointment_id", 0))
                except ValueError:
                    appt_id = 0
                try:
                    vet_id = int(request.form.get("vet_id", 0))
                except ValueError:
                    vet_id = 0
                try:
                    service_id = int(request.form.get("service_id", 0))
                except ValueError:
                    service_id = 0
                diagnosis = request.form.get("diagnosis", "").strip()
                treatment = request.form.get("treatment", "").strip() or None
                notes = request.form.get("notes", "").strip() or None
                if appt_id <= 0 or not diagnosis:
                    flash("Appointment and diagnosis are required.", "danger")
                elif vet_id <= 0:
                    flash("Select the attending vet.", "danger")
                else:
                    cur.execute("SELECT id FROM vets WHERE id=%s AND is_active=1"
                                " LIMIT 1", (vet_id,))
                    vet_ok = cur.fetchone()
                    cur.execute("SELECT id, name, fee FROM services"
                                " WHERE id=%s AND is_active=1 LIMIT 1",
                                (service_id,))
                    service = cur.fetchone()
                    if not vet_ok:
                        flash("Invalid vet (must be active).", "danger")
                    elif not service:
                        flash("Select a valid active service.", "danger")
                    else:
                        cur.execute(
                            "SELECT pet_id, client_id FROM appointments"
                            " WHERE id=%s AND status='approved' LIMIT 1",
                            (appt_id,),
                        )
                        appt = cur.fetchone()
                        if not appt:
                            flash("Invalid appointment (must be approved).", "danger")
                        else:
                            amount = service["fee"] or 0
                            with tx(conn):
                                cur.execute(
                                    "INSERT INTO consultations"
                                    " (appointment_id, pet_id, vet_id, service_id,"
                                    " diagnosis, treatment, notes)"
                                    " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                    (appt_id, appt["pet_id"], vet_id, service_id,
                                     diagnosis, treatment, notes),
                                )
                                consult_id = cur.lastrowid
                                cur.execute(
                                    "UPDATE appointments SET status='completed', vet_id=%s"
                                    " WHERE id=%s",
                                    (vet_id, appt_id),
                                )
                                cur.execute(
                                    "UPDATE clinic_queue SET vet_id=%s"
                                    " WHERE appointment_id=%s",
                                    (vet_id, appt_id),
                                )
                                if amount > 0:
                                    cur.execute(
                                        "INSERT INTO invoices (client_id, appointment_id,"
                                        " consultation_id, amount)"
                                        " VALUES (%s,%s,%s,%s)",
                                        (appt["client_id"], appt_id, consult_id,
                                         amount))
                            if amount > 0:
                                flash(f"Consultation logged + bill ₱{amount:.2f}"
                                      f" ({service['name']}) issued.", "success")
                            else:
                                flash(f"Consultation logged ({service['name']}) —"
                                      " no fee on this service.", "success")
                            conn.close()
                            return redirect(url_for("admin_consultation_detail",
                                                    consult_id=consult_id))
            cur.execute(
                "SELECT a.id, a.appointment_date, a.reason, a.vet_id,"
                " p.name AS pet_name, o.full_name AS owner_name"
                " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " JOIN clients o ON o.id=a.client_id"
                " WHERE a.status='approved'"
                " ORDER BY a.appointment_date DESC, a.id DESC LIMIT 50"
            )
            eligible = cur.fetchall()
            cur.execute("SELECT id, full_name FROM vets WHERE is_active=1"
                        " ORDER BY full_name ASC")
            active_vets = cur.fetchall()
            cur.execute("SELECT id, name, fee, duration, inclusions FROM services"
                        " WHERE is_active=1 ORDER BY sort_order ASC, name ASC")
            services = cur.fetchall()
            pre_raw = request.args.get("appointment_id", "").strip()
            if pre_raw.isdigit():
                cur.execute(
                    "SELECT a.id, a.reason, a.vet_id, p.name AS pet_name,"
                    " o.full_name AS owner_name"
                    " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                    " JOIN clients o ON o.id=a.client_id"
                    " WHERE a.id=%s AND a.status='approved' LIMIT 1",
                    (int(pre_raw),))
                prefill = cur.fetchone()
    except pymysql.MySQLError as e:
        print(f"Consult create failed: {e}")
        flash("Could not save consultation.", "danger")
        eligible = []
        active_vets = []
        services = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/consultation_form.html", eligible=eligible,
                           active_vets=active_vets, services=services,
                           prefill=prefill)


@app.route("/admin/consultations/<int:consult_id>", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_consultation_detail(consult_id):
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_consultations"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.*, p.name AS pet_name, v.full_name AS vet_name,"
                " s.name AS service_name, s.fee AS service_fee"
                " FROM consultations c"
                " JOIN pets p ON p.id=c.pet_id"
                " JOIN vets v ON v.id=c.vet_id"
                " LEFT JOIN services s ON s.id=c.service_id"
                " WHERE c.id=%s LIMIT 1", (consult_id,)
            )
            consult = cur.fetchone()
            if not consult:
                flash("Consultation not found.", "danger")
                return redirect(url_for("admin_consultations"))
            if request.method == "POST":
                medicine = request.form.get("medicine_name", "").strip() or None
                dosage = request.form.get("dosage", "").strip() or None
                instructions = request.form.get("instructions", "").strip() or None
                if not (medicine or dosage or instructions):
                    flash("Enter a medicine or some instructions first.", "danger")
                else:
                    cur.execute(
                        "INSERT INTO prescriptions_treatments"
                        " (consultation_id, medicine_name, dosage,"
                        " quantity_used, instructions)"
                        " VALUES (%s,%s,%s,1,%s)",
                        (consult_id, medicine, dosage, instructions),
                    )
                    flash("Treatment added.", "success")
            cur.execute(
                "SELECT r.*, COALESCE(r.medicine_name, i.item_name) AS item_name"
                " FROM prescriptions_treatments r"
                " LEFT JOIN inventory i ON i.id=r.inventory_id"
                " WHERE r.consultation_id=%s ORDER BY r.id ASC", (consult_id,)
            )
            rxs = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Consult detail failed: {e}")
        flash("Could not load consultation.", "danger")
        return redirect(url_for("admin_consultations"))
    finally:
        conn.close()
    can_edit = True  # shared surface: admin + staff operate jointly
    return render_template("admin/consultation_detail.html",
                           consult=consult, rxs=rxs, can_edit=can_edit)


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
    pg = None
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/invoices.html", invoices=[], owners=[],
                               vkpi=vkpi, q=q, vstatus=vstatus,
                               statuses=INV_STATUSES, pager=None)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                if session.get("role") != "admin":
                    flash("Only Admin can issue invoices.", "danger")
                    return redirect(url_for("admin_invoices"))
                try:
                    owner_id = int(request.form.get("client_id",
                                                    request.form.get("owner_id", 0)))
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
                    flash("Select a client.", "danger")
                elif amount <= 0:
                    flash("Amount must be more than zero.", "danger")
                else:
                    cur.execute("SELECT id FROM clients WHERE id=%s LIMIT 1",
                                (owner_id,))
                    if not cur.fetchone():
                        flash("Invalid client.", "danger")
                    else:
                        ref_error = None
                        if appt_id is not None:
                            cur.execute(
                                "SELECT client_id FROM appointments WHERE id=%s"
                                " LIMIT 1", (appt_id,))
                            appt = cur.fetchone()
                            if not appt or appt["client_id"] != owner_id:
                                ref_error = ("That appointment does not belong to"
                                             " the selected client.")
                        if ref_error is None and cons_id is not None:
                            cur.execute(
                                "SELECT a.client_id FROM consultations c"
                                " JOIN appointments a ON a.id=c.appointment_id"
                                " WHERE c.id=%s LIMIT 1", (cons_id,))
                            cons = cur.fetchone()
                            if not cons or cons["client_id"] != owner_id:
                                ref_error = ("That consultation does not belong to"
                                             " the selected client.")
                        if ref_error:
                            flash(ref_error, "danger")
                        else:
                            cur.execute(
                                "INSERT INTO invoices (client_id, appointment_id,"
                                " consultation_id, amount) VALUES (%s,%s,%s,%s)",
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
            base = " FROM invoices i JOIN clients o ON o.id=i.client_id"
            where = f" WHERE {pcond}"
            params = []
            if vstatus != "all":
                where += " AND i.status=%s"
                params.append(vstatus)
            if q:
                where += " AND o.full_name LIKE %s"
                params.append(f"%{q}%")
            pg = paginated(
                cur, "SELECT COUNT(*) AS c" + base + where, params,
                "SELECT i.*, o.full_name AS owner_name" + base + where +
                " ORDER BY i.issued_date DESC")
            invoices = pg["rows"]
            cur.execute("SELECT id, full_name FROM clients"
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
                           vkpi=vkpi, q=q, vstatus=vstatus, statuses=INV_STATUSES,
                           pager=pg)


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
                " FROM invoices i JOIN clients o ON o.id=i.client_id"
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
    if not verify_admin_password():
        flash("Wrong admin password — the invoice was not changed.", "danger")
        return redirect(url_for("admin_invoices"))
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
                    cur.execute("SELECT id FROM invoices WHERE id=%s LIMIT 1",
                                (inv_id,))
                    if not cur.fetchone():
                        flash(f"Invoice #{inv_id} not found.", "danger")
                    else:
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

USER_ROLES = ["admin", "staff"]


@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    astatus = request.args.get("astatus", "all").strip()
    if astatus not in ("all", "pending", "approved", "rejected"):
        astatus = "all"
    ukpi = {"total": 0, "admins": 0, "staff": 0, "pending": 0}
    pg = None
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/users.html", users=[], roles=USER_ROLES,
                           ukpi={"total": 0, "admins": 0, "staff": 0,
                                 "pending": 0},
                           q="", astatus="all", pager=None)
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
                if len(password) < 8:
                    errors.append("Password must be at least 8 characters.")
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
            where = f" WHERE {period_cond('created_at', period)}"
            params = []
            if astatus != "all":
                where += " AND status=%s"
                params.append(astatus)
            if q:
                where += " AND (username LIKE %s OR full_name LIKE %s)"
                params.extend([f"%{q}%"] * 2)
            pg = paginated(
                cur, "SELECT COUNT(*) AS c FROM users" + where, params,
                "SELECT id, full_name, username, email, role, status, created_at"
                " FROM users" + where + " ORDER BY role, username ASC")
            users = pg["rows"]
            pcond = period_cond('created_at', period)
            cur.execute("SELECT COUNT(*) AS c FROM users"
                        f" WHERE {pcond}")
            ukpi["total"] = cur.fetchone()["c"]
            for key, role in (("admins", "admin"), ("staff", "staff"),
                              ("pending", None)):
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
                           astatus=astatus, roles=USER_ROLES, pager=pg)


@app.route("/admin/users/<int:user_id>/status", methods=["POST"])
@role_required("admin")
def admin_user_status(user_id):
    if not verify_admin_password():
        flash("Wrong admin password — the account was not changed.", "danger")
        return redirect(url_for("admin_users"))
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
                    cur.execute("SELECT id FROM users WHERE id=%s LIMIT 1",
                                (user_id,))
                    if not cur.fetchone():
                        flash("User not found.", "danger")
                    else:
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
    if not verify_admin_password():
        flash("Wrong admin password — nothing was deleted.", "danger")
        return redirect(url_for("admin_users"))
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
    pg = None
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM clients")
                ckpi["total"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(DISTINCT a.client_id) AS c FROM appointments a"
                            f" WHERE {period_cond('a.created_at', period)}")
                ckpi["active"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM clients u"
                            f" WHERE {period_cond('u.created_at', period)}")
                ckpi["new"] = cur.fetchone()["c"]
                where = f" WHERE {period_cond('u.created_at', period)}"
                params = []
                if q:
                    like = f"%{q}%"
                    where += " AND (u.full_name LIKE %s OR u.phone LIKE %s)"
                    params.extend([like, like])
                pg = paginated(
                    cur, "SELECT COUNT(*) AS c FROM clients u" + where, params,
                    "SELECT u.id, u.full_name, u.phone,"
                    " (SELECT COUNT(*) FROM pets p WHERE p.client_id=u.id) AS pets,"
                    " (SELECT COUNT(*) FROM appointments a WHERE a.client_id=u.id) AS visits"
                    " FROM clients u" + where + " ORDER BY u.full_name ASC")
                rows = pg["rows"]
        except pymysql.MySQLError as e:
            print(f"Clients failed: {e}")
            flash("Could not load clients.", "danger")
        finally:
            conn.close()
    return render_template("admin/clients.html", rows=rows, q=q, ckpi=ckpi, pager=pg)


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
                address = request.form.get("address", "").strip() or None
                if not name:
                    flash("Client name is required.", "danger")
                elif not phone.startswith("09") or len(phone) != 11:
                    flash("Invalid phone number: " + PH_MOBILE_HINT, "danger")
                else:
                    try:
                        cur.execute("UPDATE clients SET full_name=%s, phone=%s,"
                                    " address=%s WHERE id=%s",
                                    (name, phone, address, owner_id))
                    except pymysql.IntegrityError:
                        flash("That phone number is already registered.", "danger")
                        conn.close()
                        return redirect(url_for("admin_client_detail",
                                                owner_id=owner_id))
                    flash("Client record updated.", "success")
                    conn.close()
                    return redirect(url_for("admin_client_detail", owner_id=owner_id))
            cur.execute("SELECT id, full_name, phone, address, created_at FROM clients"
                        " WHERE id=%s LIMIT 1", (owner_id,))
            owner = cur.fetchone()
            if not owner:
                flash("Client not found.", "danger")
                conn.close()
                return redirect(url_for("admin_clients"))
            cur.execute("SELECT * FROM pets WHERE client_id=%s ORDER BY name ASC",
                        (owner_id,))
            pets = cur.fetchall()
            cur.execute(
                "SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,"
                " p.name AS pet_name, v.full_name AS vet_name"
                " FROM appointments a JOIN pets p ON p.id=a.pet_id"
                " LEFT JOIN vets v ON v.id=a.vet_id"
                " WHERE a.client_id=%s ORDER BY a.appointment_date DESC LIMIT 20",
                (owner_id,))
            visits = cur.fetchall()
            cur.execute("SELECT id, amount, status, issued_date FROM invoices"
                        " WHERE client_id=%s ORDER BY issued_date DESC LIMIT 20", (owner_id,))
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
    pg = None
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
                where = f" WHERE {pcond}"
                params = []
                if species != "All":
                    where += " AND p.species=%s"
                    params.append(species)
                if q:
                    like = f"%{q}%"
                    where += " AND (p.name LIKE %s OR o.full_name LIKE %s)"
                    params.extend([like, like])
                pg = paginated(
                    cur, "SELECT COUNT(*) AS c FROM pets p"
                    " JOIN clients o ON o.id=p.client_id" + where, params,
                    "SELECT p.*, o.full_name AS owner_name, o.phone"
                    " FROM pets p JOIN clients o ON o.id=p.client_id" + where +
                    " ORDER BY p.name ASC")
                rows = pg["rows"]
        except pymysql.MySQLError as e:
            print(f"Pets failed: {e}")
            flash("Could not load pets.", "danger")
        finally:
            conn.close()
    return render_template("admin/pets.html", rows=rows, species=species, q=q,
                           pkpi=pkpi, species_choices=["All"] + SPECIES_CHOICES,
                           pager=pg)


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
                age_raw = request.form.get("age", "").strip()
                weight_raw = request.form.get("weight", "").strip()
                age = weight = None
                errors = []
                if not name:
                    errors.append("Pet name is required.")
                if species not in SPECIES_CHOICES:
                    errors.append("Please select a valid species.")
                if gender is not None and gender not in GENDER_CHOICES:
                    errors.append("Please select a valid gender.")
                if age_raw:
                    try:
                        age = int(age_raw)
                        if not 0 <= age <= 50:
                            raise ValueError
                    except ValueError:
                        errors.append("Age must be a whole number from 0 to 50.")
                if weight_raw:
                    try:
                        weight = float(weight_raw)
                        if not 0 <= weight <= 200:
                            raise ValueError
                    except ValueError:
                        errors.append("Weight must be a number from 0 to 200 kg.")
                for e in errors:
                    flash(e, "danger")
                if not errors:
                    cur.execute(
                        "UPDATE pets SET name=%s, species=%s, breed=%s, age=%s,"
                        " gender=%s, weight=%s WHERE id=%s",
                        (name, species, breed, age, gender, weight, pet_id))
                    flash("Pet record updated.", "success")
                    conn.close()
                    return redirect(url_for("admin_pets", species=species))
            cur.execute("SELECT p.*, o.full_name AS owner_name FROM pets p"
                        " JOIN clients o ON o.id=p.client_id WHERE p.id=%s LIMIT 1",
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


VET_STATUSES = ["active", "inactive"]


@app.route("/admin/vets", methods=["GET", "POST"])
@role_required("admin", "staff")
def admin_vets():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    q = request.args.get("q", "").strip()
    vstatus = request.args.get("vstatus", "all").strip()
    if vstatus not in ("all", "active", "inactive"):
        vstatus = "all"
    vkpi = {"total": 0, "active": 0, "consults": 0, "today": 0}
    rows = []
    pg = None
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/vets.html", rows=[], vkpi=vkpi, q=q,
                               vstatus=vstatus, statuses=VET_STATUSES, pager=None)
    try:
        with conn.cursor() as cur:
            if request.method == "POST":
                if session.get("role") != "admin":
                    flash("Only Admin can add vets.", "danger")
                    return redirect(url_for("admin_vets"))
                full_name = request.form.get("full_name", "").strip()
                specialty = request.form.get("specialty", "").strip() or None
                phone = "".join(c for c in request.form.get("phone", "")
                                if c.isdigit()) or None
                if not full_name:
                    flash("Vet name is required.", "danger")
                elif phone is not None and len(phone) < 7:
                    flash("Phone looks too short (7+ digits).", "danger")
                else:
                    cur.execute(
                        "INSERT INTO vets (full_name, specialty, phone)"
                        " VALUES (%s,%s,%s)", (full_name, specialty, phone))
                    flash(f"Dr. {full_name} added to the directory.", "success")
                    conn.close()
                    return redirect(url_for("admin_vets"))
            pcond = period_cond('created_at', period)
            cur.execute("SELECT COUNT(*) AS c FROM vets"
                        f" WHERE {pcond}")
            vkpi["total"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM vets"
                        f" WHERE is_active=1 AND {pcond}")
            vkpi["active"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM consultations"
                        f" WHERE {period_cond('consultation_date', period)}")
            vkpi["consults"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(DISTINCT vet_id) AS c FROM appointments"
                        " WHERE vet_id IS NOT NULL AND appointment_date=CURDATE()")
            vkpi["today"] = cur.fetchone()["c"]
            where = f" WHERE {pcond}"
            params = []
            if vstatus == "active":
                where += " AND v.is_active=1"
            elif vstatus == "inactive":
                where += " AND v.is_active=0"
            if q:
                like = f"%{q}%"
                where += " AND (v.full_name LIKE %s OR v.specialty LIKE %s)"
                params.extend([like, like])
            pg = paginated(
                cur, "SELECT COUNT(*) AS c FROM vets v" + where, params,
                "SELECT v.*, (SELECT COUNT(*) FROM consultations c"
                " WHERE c.vet_id=v.id) AS consults FROM vets v" + where +
                " ORDER BY v.is_active DESC, v.full_name ASC")
            rows = pg["rows"]
    except pymysql.MySQLError as e:
        print(f"Vets failed: {e}")
        flash("Could not load vets.", "danger")
        rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return render_template("admin/vets.html", rows=rows, vkpi=vkpi, q=q,
                           vstatus=vstatus, statuses=VET_STATUSES, pager=pg)


@app.route("/admin/vets/<int:vet_id>/status", methods=["POST"])
@role_required("admin")
def admin_vet_status(vet_id):
    if not verify_admin_password():
        flash("Wrong admin password — the vet was not changed.", "danger")
        return redirect(url_for("admin_vets"))
    new_status = request.form.get("status", "").strip()
    if new_status not in VET_STATUSES:
        flash("Invalid status.", "danger")
    else:
        conn = db()
        if conn is None:
            flash("Database connection failed.", "danger")
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM vets WHERE id=%s LIMIT 1",
                                (vet_id,))
                    if not cur.fetchone():
                        flash("Vet not found.", "danger")
                    else:
                        cur.execute("UPDATE vets SET is_active=%s WHERE id=%s",
                                    (1 if new_status == "active" else 0, vet_id))
                        flash(f"Vet → {new_status}.", "success")
            except pymysql.MySQLError as e:
                print(f"Vet status failed: {e}")
                flash("Could not update vet.", "danger")
            finally:
                conn.close()
    return redirect(url_for("admin_vets"))


# ---------------- Services (fixed price list) ----------------

@app.route("/admin/services")
@role_required("admin", "staff")
def admin_services():
    q = request.args.get("q", "").strip()
    sstatus = request.args.get("sstatus", "all").strip()
    if sstatus not in ("all", "active", "inactive"):
        sstatus = "all"
    rows = []
    skpi = {"total": 0, "active": 0, "inactive": 0, "avg": 0}
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total,"
                            " SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active,"
                            " COALESCE(AVG(fee), 0) AS avg_fee FROM services")
                counts = cur.fetchone()
                total = counts["total"] or 0
                active = counts["active"] or 0
                skpi = {"total": total, "active": active,
                        "inactive": total - active,
                        "avg": counts["avg_fee"] or 0}
                sql = ("SELECT id, name, fee, duration, inclusions, is_active"
                       " FROM services")
                where, params = [], []
                if sstatus == "active":
                    where.append("is_active=1")
                elif sstatus == "inactive":
                    where.append("is_active=0")
                if q:
                    like = f"%{q}%"
                    where.append("(name LIKE %s OR inclusions LIKE %s)")
                    params.extend([like, like])
                if where:
                    sql += " WHERE " + " AND ".join(where)
                cur.execute(sql + " ORDER BY sort_order ASC, name ASC", params)
                rows = cur.fetchall()
        except pymysql.MySQLError as e:
            print(f"Services list failed: {e}")
            flash("Could not load services.", "danger")
        finally:
            conn.close()
    return render_template("admin/services.html", rows=rows, skpi=skpi, q=q,
                           sstatus=sstatus)


@app.route("/admin/services/<int:service_id>", methods=["POST"])
@role_required("admin")
def admin_service_update(service_id):
    if not verify_admin_password():
        flash("Wrong admin password — the service was not changed.", "danger")
        return redirect(url_for("admin_services"))
    try:
        fee = float(request.form.get("fee", ""))
    except ValueError:
        fee = -1
    duration = request.form.get("duration", "").strip()[:40] or None
    inclusions = request.form.get("inclusions", "").strip()[:800] or None
    is_active = 1 if request.form.get("is_active") == "1" else 0
    if fee < 0 or fee > 1000000:
        flash("Enter a valid fee between 0 and 1,000,000.", "danger")
        return redirect(url_for("admin_services"))
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
    else:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE services SET fee=%s, duration=%s, inclusions=%s,"
                    " is_active=%s WHERE id=%s",
                    (fee, duration, inclusions, is_active, service_id))
                if cur.rowcount:
                    flash("Service updated — the new fee applies to future"
                          " consultations.", "success")
                else:
                    flash("Service not found.", "danger")
        except pymysql.MySQLError as e:
            print(f"Service update failed: {e}")
            flash("Could not update the service.", "danger")
        finally:
            conn.close()
    return redirect(url_for("admin_services"))


# ---------------- Settings (own profile + vet profiles) ----------------

@app.route("/admin/settings")
@role_required("admin", "staff")
def admin_settings():
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    profile, vets = None, []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, full_name, username, email, phone, role, status, avatar"
                " FROM users WHERE id=%s LIMIT 1", (session["user_id"],))
            profile = cur.fetchone()
            cur.execute(
                "SELECT v.*, (SELECT COUNT(*) FROM consultations c"
                " WHERE c.vet_id=v.id) AS consults FROM vets v"
                " ORDER BY v.is_active DESC, v.full_name ASC")
            vets = cur.fetchall()
    except pymysql.MySQLError as e:
        print(f"Settings load failed: {e}")
        flash("Could not load settings.", "danger")
    finally:
        conn.close()
    return render_template("admin/settings.html", profile=profile, vets=vets)


@app.route("/admin/settings/profile", methods=["POST"])
@role_required("admin", "staff")
def admin_settings_profile():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    current = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    want_pw = bool(current or new_pw or confirm)

    errors = []
    if len(full_name) < 2:
        errors.append("Enter your full name.")
    if "@" not in email or len(email) < 5:
        errors.append("Enter a valid email address.")
    if want_pw:
        if len(new_pw) < 8:
            errors.append("The new password needs at least 8 characters.")
        if new_pw != confirm:
            errors.append("The new passwords do not match.")
    if errors:
        for msg in errors:
            flash(msg, "danger")
        return redirect(url_for("admin_settings"))

    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM users WHERE email=%s AND id<>%s LIMIT 1",
                        (email, session["user_id"]))
            if cur.fetchone():
                flash("That email is already used by another account.", "danger")
                return redirect(url_for("admin_settings"))
            if want_pw:
                cur.execute("SELECT password FROM users WHERE id=%s LIMIT 1",
                            (session["user_id"],))
                row = cur.fetchone()
                try:
                    ok = bool(row) and bcrypt.checkpw(
                        current.encode(), row["password"].encode())
                except ValueError:
                    ok = False
                if not ok:
                    flash("Your current password is incorrect.", "danger")
                    return redirect(url_for("admin_settings"))
                hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                cur.execute("UPDATE users SET full_name=%s, email=%s, password=%s"
                            " WHERE id=%s",
                            (full_name, email, hashed, session["user_id"]))
            else:
                cur.execute("UPDATE users SET full_name=%s, email=%s WHERE id=%s",
                            (full_name, email, session["user_id"]))
        session["full_name"] = full_name
        flash("Profile saved." + (" Password changed." if want_pw else ""), "success")
    except pymysql.MySQLError as e:
        print(f"Profile save failed: {e}")
        flash("Could not save your profile.", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_settings"))


@app.route("/admin/settings/photo", methods=["POST"])
@role_required("admin", "staff")
def admin_settings_photo():
    uid = session["user_id"]
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT avatar FROM users WHERE id=%s LIMIT 1", (uid,))
            row = cur.fetchone()
            old = (row or {}).get("avatar")
            if request.form.get("photo_action") == "remove":
                cur.execute("UPDATE users SET avatar=NULL WHERE id=%s", (uid,))
                _delete_image("avatars", old)
                session["avatar"] = None
                flash("Profile photo removed.", "success")
                return redirect(url_for("admin_settings"))
            name, err = _store_image(request.files.get("photo"), "avatars",
                                     f"u{uid}")
            if err:
                flash(err, "danger")
                return redirect(url_for("admin_settings"))
            cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (name, uid))
        _delete_image("avatars", old)
        session["avatar"] = name
        flash("Profile photo updated.", "success")
    except pymysql.MySQLError as e:
        print(f"Photo save failed: {e}")
        flash("Could not save the photo.", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_settings"))


@app.route("/admin/settings/vets", methods=["POST"])
@role_required("admin")
def admin_settings_vet_save():
    vet_raw = request.form.get("vet_id", "").strip()
    full_name = request.form.get("full_name", "").strip()
    specialty = request.form.get("specialty", "").strip() or None
    phone = "".join(c for c in request.form.get("phone", "") if c.isdigit()) or None
    email = request.form.get("email", "").strip() or None
    license_no = request.form.get("license_no", "").strip() or None
    bio = request.form.get("bio", "").strip() or None
    is_active = 1 if request.form.get("is_active") == "1" else 0

    errors = []
    if len(full_name) < 2:
        errors.append("Enter the vet's full name.")
    if phone and not 7 <= len(phone) <= 13:
        errors.append("Phone must contain 7 to 13 digits.")
    if email and ("@" not in email or len(email) < 5):
        errors.append("Enter a valid email address.")
    if errors:
        for msg in errors:
            flash(msg, "danger")
        return redirect(url_for("admin_settings") + "#vets")

    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))
    vet_id = int(vet_raw) if vet_raw.isdigit() else None
    old_photo = None
    try:
        with conn.cursor() as cur:
            if vet_id:
                cur.execute("SELECT photo FROM vets WHERE id=%s LIMIT 1", (vet_id,))
                row = cur.fetchone()
                if not row:
                    flash(f"Vet #{vet_id} not found.", "danger")
                    return redirect(url_for("admin_settings") + "#vets")
                old_photo = row["photo"]
                cur.execute(
                    "UPDATE vets SET full_name=%s, specialty=%s, phone=%s,"
                    " email=%s, license_no=%s, bio=%s, is_active=%s WHERE id=%s",
                    (full_name, specialty, phone, email, license_no, bio,
                     is_active, vet_id))
            else:
                cur.execute(
                    "INSERT INTO vets (full_name, specialty, phone, email,"
                    " license_no, bio, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (full_name, specialty, phone, email, license_no, bio,
                     is_active))
                vet_id = cur.lastrowid

            upload = request.files.get("photo")
            if upload and (upload.filename or "").strip():
                name, err = _store_image(upload, "vets", f"v{vet_id}")
                if err:
                    flash(err, "danger")
                else:
                    cur.execute("UPDATE vets SET photo=%s WHERE id=%s",
                                (name, vet_id))
                    _delete_image("vets", old_photo)
            elif request.form.get("remove_photo") == "1" and old_photo:
                cur.execute("UPDATE vets SET photo=NULL WHERE id=%s", (vet_id,))
                _delete_image("vets", old_photo)
        flash(f"Vet profile for Dr. {full_name} saved.", "success")
    except pymysql.MySQLError as e:
        print(f"Vet profile save failed: {e}")
        flash("Could not save the vet profile.", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_settings") + "#vets")


@app.route("/admin/guide")
@login_required
def admin_guide():
    """Plain-language English user guide so anyone can operate and demo the
    system. Read-only: no DB access, no role restriction."""
    return render_template("admin/guide.html")


# ---------------- Reports (read-only registers, CPSC hub pattern) ----------------

REPORTS_MENU = [
    {"label": "Operations", "cards": [
        {"kind": "appointments", "title": "Appointments Report",
         "blurb": "Every booking by status, with pet, owner, vet, reason and source.",
         "icon": "i-calendar"},
        {"kind": "queue", "title": "Queue Report",
         "blurb": "Queue tickets by day: waiting, serving, done and skipped visits.",
         "icon": "i-queue"},
        {"kind": "consultations", "title": "Consultations Report",
         "blurb": "Consults with attending vet, diagnosis, prescriptions and billing.",
         "icon": "i-pulse"},
    ]},
    {"label": "Clients & Pets", "cards": [
        {"kind": "clients", "title": "Clients Report",
         "blurb": "Client register with contact, pets owned and visits in the period.",
         "icon": "i-users"},
        {"kind": "pets", "title": "Pets Report",
         "blurb": "Pet registry by species, with owner, breed, gender and age.",
         "icon": "i-paw"},
        {"kind": "vets", "title": "Vets Report",
         "blurb": "Veterinarian directory: specialty, status and consults handled.",
         "icon": "i-stethoscope"},
    ]},
    {"label": "Finance", "cards": [
        {"kind": "invoices", "title": "Invoices Report",
         "blurb": "Every bill by status with amounts: paid, unpaid and cancelled.",
         "icon": "i-receipt"},
    ]},
]

REPORTS_WIDE = {"kind": "revenue", "title": "Revenue & Collections",
                "blurb": "Monthly collected income against outstanding balances, "
                         "with every bill in the period.",
                "icon": "i-dashboard"}

REPORT_KINDS = {c["kind"] for g in REPORTS_MENU for c in g["cards"]}
REPORT_KINDS.add(REPORTS_WIDE["kind"])


@app.route("/admin/reports")
@role_required("admin", "staff")
def admin_reports():
    return render_template("admin/reports_hub.html", groups=REPORTS_MENU,
                           wide=REPORTS_WIDE)


@app.route("/admin/reports/lookup")
@role_required("admin", "staff")
def admin_report_lookup():
    """Record Lookup: jump straight to the ledger that holds the typed record.
    Accepts a booking #, invoice #, queue ticket #, phone number or name."""
    q = request.args.get("q", "").strip()
    if not q:
        flash("Type a booking #, invoice #, ticket #, phone or name first.", "danger")
        return redirect(url_for("admin_reports"))
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_reports"))
    try:
        with conn.cursor() as cur:
            if q.isdigit():
                n = int(q)
                cur.execute("SELECT id FROM appointments WHERE id=%s LIMIT 1", (n,))
                if cur.fetchone():
                    flash(f"Opened booking #{n}.", "success")
                    return redirect(url_for("admin_appointments", q=q))
                cur.execute("SELECT id FROM invoices WHERE id=%s LIMIT 1", (n,))
                if cur.fetchone():
                    flash(f"Opened invoice #{n}.", "success")
                    return redirect(url_for("admin_invoices", q=q))
                cur.execute("SELECT id FROM clinic_queue WHERE queue_number=%s"
                            " LIMIT 1", (n,))
                if cur.fetchone():
                    flash(f"Opened queue ticket #{n}.", "success")
                    return redirect(url_for("admin_queue", q=q))
            like = f"%{q}%"
            cur.execute("SELECT id FROM clients WHERE full_name LIKE %s"
                        " OR phone LIKE %s LIMIT 1", (like, like))
            if cur.fetchone():
                flash("Matched a client — Clients ledger opened.", "success")
                return redirect(url_for("admin_clients", q=q))
            cur.execute("SELECT id FROM pets WHERE name LIKE %s LIMIT 1", (like,))
            if cur.fetchone():
                flash("Matched a pet — Pets registry opened.", "success")
                return redirect(url_for("admin_pets", q=q))
            cur.execute("SELECT id FROM vets WHERE full_name LIKE %s LIMIT 1", (like,))
            if cur.fetchone():
                flash("Matched a vet — Vets directory opened.", "success")
                return redirect(url_for("admin_vets", q=q))
            cur.execute("SELECT id FROM appointments WHERE reason LIKE %s LIMIT 1",
                        (like,))
            if cur.fetchone():
                flash("Matched a booking reason — Appointments ledger opened.",
                      "success")
                return redirect(url_for("admin_appointments", q=q))
        flash("No record matched. Try a booking #, invoice #, ticket #, phone"
              " or name.", "danger")
        return redirect(url_for("admin_reports"))
    except pymysql.MySQLError as e:
        print(f"Report lookup failed: {e}")
        flash("Lookup failed.", "danger")
        return redirect(url_for("admin_reports"))
    finally:
        conn.close()


def _report_ctx():
    period = request.args.get("period", "All Time")
    if period not in PERIODS:
        period = "All Time"
    return period, request.args.get("q", "").strip()


@app.route("/admin/reports/<kind>")
@role_required("admin", "staff")
def admin_report_register(kind):
    if kind not in REPORT_KINDS:
        flash("Unknown report.", "danger")
        return redirect(url_for("admin_reports"))
    period, q = _report_ctx()
    conn = db()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_reports"))
    try:
        with conn.cursor() as cur:
            if kind == "appointments":
                return _report_appointments(cur, period, q)
            if kind == "queue":
                return _report_queue(cur, period, q)
            if kind == "consultations":
                return _report_consultations(cur, period, q)
            if kind == "invoices":
                return _report_invoices(cur, period, q)
            if kind == "clients":
                return _report_clients(cur, period, q)
            if kind == "pets":
                return _report_pets(cur, period, q)
            if kind == "vets":
                return _report_vets(cur, period, q)
            return _report_revenue(cur, period, q)
    except pymysql.MySQLError as e:
        print(f"Report {kind} failed: {e}")
        flash("Could not load the report.", "danger")
        return redirect(url_for("admin_reports"))
    finally:
        conn.close()


def _report_appointments(cur, period, q):
    status = request.args.get("status", "all").strip()
    if status not in ("all", "pending", "approved", "completed", "cancelled"):
        status = "all"
    pcond = period_cond("a.appointment_date", period)
    rkpi = {}
    for key, cond in (("total", "1=1"), ("pending", "a.status='pending'"),
                      ("approved", "a.status='approved'"),
                      ("completed", "a.status='completed'"),
                      ("cancelled", "a.status='cancelled'")):
        cur.execute("SELECT COUNT(*) AS c FROM appointments a"
                    f" WHERE {pcond} AND {cond}")
        rkpi[key] = cur.fetchone()["c"]
    base = (" FROM appointments a JOIN pets p ON p.id=a.pet_id"
            " JOIN clients o ON o.id=a.client_id"
            " LEFT JOIN vets v ON v.id=a.vet_id")
    where = f" WHERE {pcond}"
    params = []
    if status != "all":
        where += " AND a.status=%s"
        params.append(status)
    if q:
        like = f"%{q}%"
        where += (" AND (p.name LIKE %s OR o.full_name LIKE %s"
                  " OR o.phone LIKE %s OR a.reason LIKE %s)")
        params.extend([like] * 4)
    pg = paginated(
        cur, "SELECT COUNT(*) AS c" + base + where, params,
        "SELECT a.id, a.appointment_date, a.appointment_time, a.reason,"
        " a.status, a.source, p.name AS pet_name, o.full_name AS owner_name,"
        " o.phone, v.full_name AS vet_name" + base + where +
        " ORDER BY a.appointment_date DESC, a.appointment_time DESC")
    return render_template("admin/report_appointments.html", rows=pg["rows"],
                           rkpi=rkpi, pager=pg, period=period, q=q, status=status,
                           periods=PERIODS,
                           statuses=["all", "pending", "approved", "completed",
                                     "cancelled"])


def _report_queue(cur, period, q):
    qstatus = request.args.get("qstatus", "all").strip()
    if qstatus != "all" and qstatus not in QUEUE_STATUSES:
        qstatus = "all"
    where, params = _queue_filters(period, q, qstatus)
    base = (" FROM clinic_queue q JOIN pets p ON p.id=q.pet_id"
            " JOIN clients o ON o.id=q.client_id"
            " LEFT JOIN vets v ON v.id=q.vet_id")
    pg = paginated(
        cur, "SELECT COUNT(*) AS c" + base + where, params,
        "SELECT q.queue_number, q.status, q.queue_date, p.name AS pet_name,"
        " o.full_name AS owner_name, v.full_name AS vet_name" + base + where +
        " ORDER BY q.queue_date DESC, q.queue_number ASC")
    rkpi = {}
    for key in QUEUE_STATUSES:
        cur.execute("SELECT COUNT(*) AS c FROM clinic_queue"
                    f" WHERE status=%s AND {period_cond('queue_date', period)}",
                    (key,))
        rkpi[key] = cur.fetchone()["c"]
    return render_template("admin/report_queue.html", rows=pg["rows"], rkpi=rkpi,
                           pager=pg, period=period, q=q, qstatus=qstatus,
                           periods=PERIODS, statuses=QUEUE_STATUSES)


def _report_consultations(cur, period, q):
    rx = request.args.get("rx", "all").strip()
    if rx not in ("all", "yes", "no"):
        rx = "all"
    pcond = period_cond("c.consultation_date", period)
    cur.execute("SELECT COUNT(*) AS c FROM consultations c"
                f" WHERE {pcond}")
    total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM consultations c"
                f" WHERE {pcond} AND EXISTS (SELECT 1 FROM"
                " prescriptions_treatments r WHERE r.consultation_id=c.id)")
    withrx = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(DISTINCT pet_id) AS c FROM consultations"
                f" WHERE {period_cond('consultation_date', period)}")
    pets = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(SUM(i.amount),0) AS s FROM invoices i"
                " JOIN consultations c ON c.id=i.consultation_id"
                f" WHERE {pcond}")
    billed = float(cur.fetchone()["s"])
    base = (" FROM consultations c JOIN pets p ON p.id=c.pet_id"
            " JOIN appointments a ON a.id=c.appointment_id"
            " JOIN clients o ON o.id=a.client_id"
            " JOIN vets u ON u.id=c.vet_id"
            " LEFT JOIN invoices i ON i.consultation_id=c.id")
    where = f" WHERE {pcond}"
    params = []
    if rx == "yes":
        where += (" AND EXISTS (SELECT 1 FROM prescriptions_treatments r"
                  " WHERE r.consultation_id=c.id)")
    elif rx == "no":
        where += (" AND NOT EXISTS (SELECT 1 FROM prescriptions_treatments r"
                  " WHERE r.consultation_id=c.id)")
    if q:
        like = f"%{q}%"
        where += (" AND (c.diagnosis LIKE %s OR p.name LIKE %s"
                  " OR o.full_name LIKE %s OR u.full_name LIKE %s)")
        params.extend([like] * 4)
    pg = paginated(
        cur, "SELECT COUNT(*) AS c" + base + where, params,
        "SELECT c.id, c.consultation_date, c.diagnosis,"
        " p.name AS pet_name, o.full_name AS owner_name,"
        " u.full_name AS vet_name, i.amount AS billed, i.status AS bill_status,"
        " (SELECT COUNT(*) FROM prescriptions_treatments r"
        " WHERE r.consultation_id=c.id) AS rx" + base + where +
        " ORDER BY c.consultation_date DESC")
    return render_template("admin/report_consultations.html", rows=pg["rows"],
                           rkpi={"total": total, "withrx": withrx, "pets": pets,
                                 "billed": billed},
                           pager=pg, period=period, q=q, rx=rx, periods=PERIODS)


def _report_invoices(cur, period, q):
    vstatus = request.args.get("vstatus", "all").strip()
    if vstatus not in ("all", "unpaid", "paid", "cancelled"):
        vstatus = "all"
    pcond = period_cond("i.issued_date", period)
    rkpi = {}
    for key, cond in (("issued", "1=1"), ("paid", "i.status='paid'"),
                      ("unpaid", "i.status='unpaid'"),
                      ("cancelled", "i.status='cancelled'")):
        cur.execute("SELECT COUNT(*) AS c FROM invoices i"
                    f" WHERE {pcond} AND {cond}")
        rkpi[key] = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(SUM(i.amount),0) AS s FROM invoices i"
                f" WHERE {pcond} AND i.status='paid'")
    rkpi["collected"] = float(cur.fetchone()["s"])
    cur.execute("SELECT COALESCE(SUM(i.amount),0) AS s FROM invoices i"
                f" WHERE {pcond} AND i.status='unpaid'")
    rkpi["outstanding"] = float(cur.fetchone()["s"])
    base = " FROM invoices i JOIN clients o ON o.id=i.client_id"
    where = f" WHERE {pcond}"
    params = []
    if vstatus != "all":
        where += " AND i.status=%s"
        params.append(vstatus)
    if q:
        like = f"%{q}%"
        where += " AND (o.full_name LIKE %s OR o.phone LIKE %s)"
        params.extend([like, like])
    pg = paginated(
        cur, "SELECT COUNT(*) AS c" + base + where, params,
        "SELECT i.id, i.issued_date, i.amount, i.status,"
        " o.full_name AS owner_name, o.phone" + base + where +
        " ORDER BY i.issued_date DESC, i.id DESC")
    return render_template("admin/report_invoices.html", rows=pg["rows"],
                           rkpi=rkpi, pager=pg, period=period, q=q,
                           vstatus=vstatus, periods=PERIODS,
                           statuses=["all"] + INV_STATUSES)


def _report_clients(cur, period, q):
    pcond = period_cond("u.created_at", period)
    cur.execute("SELECT COUNT(*) AS c FROM clients")
    total = cur.fetchone()["c"]
    cur.execute(f"SELECT COUNT(*) AS c FROM clients u WHERE {pcond}")
    new = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(DISTINCT a.client_id) AS c FROM appointments a"
                f" WHERE {period_cond('a.created_at', period)}")
    active = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM pets")
    pets = cur.fetchone()["c"]
    where = f" WHERE {pcond}"
    params = []
    if q:
        like = f"%{q}%"
        where += " AND (u.full_name LIKE %s OR u.phone LIKE %s)"
        params.extend([like, like])
    pg = paginated(
        cur, "SELECT COUNT(*) AS c FROM clients u" + where, params,
        "SELECT u.id, u.full_name, u.phone, u.created_at,"
        " (SELECT COUNT(*) FROM pets p WHERE p.client_id=u.id) AS pets,"
        " (SELECT COUNT(*) FROM appointments a WHERE a.client_id=u.id) AS visits"
        " FROM clients u" + where + " ORDER BY u.full_name ASC")
    return render_template("admin/report_clients.html", rows=pg["rows"],
                           rkpi={"total": total, "new": new, "active": active,
                                 "pets": pets},
                           pager=pg, period=period, q=q, periods=PERIODS)


def _report_pets(cur, period, q):
    species = request.args.get("species", "All").strip()
    if species not in SPECIES_CHOICES:
        species = "All"
    pcond = period_cond("p.created_at", period)
    cur.execute(f"SELECT COUNT(*) AS c FROM pets p WHERE {pcond}")
    total = cur.fetchone()["c"]
    rkpi = {"total": total}
    for key, sp in (("dogs", "Dog"), ("cats", "Cat")):
        cur.execute("SELECT COUNT(*) AS c FROM pets p"
                    f" WHERE p.species=%s AND {pcond}", (sp,))
        rkpi[key] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM pets p"
                f" WHERE p.species NOT IN ('Dog','Cat') AND {pcond}")
    rkpi["others"] = cur.fetchone()["c"]
    where = f" WHERE {pcond}"
    params = []
    if species != "All":
        where += " AND p.species=%s"
        params.append(species)
    if q:
        like = f"%{q}%"
        where += " AND (p.name LIKE %s OR o.full_name LIKE %s)"
        params.extend([like, like])
    pg = paginated(
        cur, "SELECT COUNT(*) AS c FROM pets p"
        " JOIN clients o ON o.id=p.client_id" + where, params,
        "SELECT p.name, p.species, p.breed, p.gender, p.age, p.created_at,"
        " o.full_name AS owner_name, o.phone"
        " FROM pets p JOIN clients o ON o.id=p.client_id" + where +
        " ORDER BY p.name ASC")
    return render_template("admin/report_pets.html", rows=pg["rows"], rkpi=rkpi,
                           pager=pg, period=period, q=q, species=species,
                           periods=PERIODS, species_choices=["All"] + SPECIES_CHOICES)


def _report_vets(cur, period, q):
    vstatus = request.args.get("vstatus", "all").strip()
    if vstatus not in ("all", "active", "inactive"):
        vstatus = "all"
    cur.execute("SELECT COUNT(*) AS c FROM vets")
    total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM vets WHERE is_active=1")
    active = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM consultations"
                f" WHERE {period_cond('consultation_date', period)}")
    consults = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(DISTINCT vet_id) AS c FROM appointments"
                " WHERE vet_id IS NOT NULL AND appointment_date=CURDATE()")
    today = cur.fetchone()["c"]
    where = " WHERE 1=1"
    params = []
    if vstatus == "active":
        where += " AND v.is_active=1"
    elif vstatus == "inactive":
        where += " AND v.is_active=0"
    if q:
        like = f"%{q}%"
        where += " AND (v.full_name LIKE %s OR v.specialty LIKE %s)"
        params.extend([like, like])
    pg = paginated(
        cur, "SELECT COUNT(*) AS c FROM vets v" + where, params,
        "SELECT v.*, (SELECT COUNT(*) FROM consultations c"
        " WHERE c.vet_id=v.id) AS consults FROM vets v" + where +
        " ORDER BY v.is_active DESC, v.full_name ASC")
    return render_template("admin/report_vets.html", rows=pg["rows"],
                           rkpi={"total": total, "active": active,
                                 "consults": consults, "today": today},
                           pager=pg, period=period, q=q, vstatus=vstatus,
                           periods=PERIODS)


def _report_revenue(cur, period, q):
    pcond = period_cond("i.issued_date", period)
    cur.execute("SELECT COALESCE(SUM(i.amount),0) AS s FROM invoices i"
                f" WHERE {pcond} AND i.status='paid'")
    collected = float(cur.fetchone()["s"])
    cur.execute("SELECT COALESCE(SUM(i.amount),0) AS s FROM invoices i"
                f" WHERE {pcond} AND i.status='unpaid'")
    outstanding = float(cur.fetchone()["s"])
    rkpi = {"collected": collected, "outstanding": outstanding}
    for key, cond in (("paid", "i.status='paid'"), ("unpaid", "i.status='unpaid'")):
        cur.execute("SELECT COUNT(*) AS c FROM invoices i"
                    f" WHERE {pcond} AND {cond}")
        rkpi[key] = cur.fetchone()["c"]
    # Monthly collections for the last 6 months (paid bills), zero-filled.
    cur.execute(
        "SELECT DATE_FORMAT(issued_date, '%Y-%m') AS ym,"
        " DATE_FORMAT(issued_date, '%b ''%y') AS lbl,"
        " COALESCE(SUM(amount),0) AS v"
        " FROM invoices"
        " WHERE status='paid'"
        " AND issued_date >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 5 MONTH), '%Y-%m-01')"
        " GROUP BY ym, lbl ORDER BY ym ASC"
    )
    got = {r["ym"]: (r["lbl"], float(r["v"])) for r in cur.fetchall()}
    labels, values = [], []
    first = date.today().replace(day=1)
    for offset in range(5, -1, -1):
        month_first = (first.year, first.month)
        y, m = month_first
        for _ in range(offset):
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        ym = f"{y:04d}-{m:02d}"
        lbl = date(y, m, 1).strftime("%b '%y")
        labels.append(lbl)
        values.append(got.get(ym, (lbl, 0.0))[1])
    base = " FROM invoices i JOIN clients o ON o.id=i.client_id"
    where = f" WHERE {pcond}"
    params = []
    if q:
        like = f"%{q}%"
        where += " AND (o.full_name LIKE %s OR o.phone LIKE %s)"
        params.extend([like, like])
    pg = paginated(
        cur, "SELECT COUNT(*) AS c" + base + where, params,
        "SELECT i.id, i.issued_date, i.amount, i.status,"
        " o.full_name AS owner_name" + base + where +
        " ORDER BY i.issued_date DESC, i.id DESC")
    return render_template("admin/report_revenue.html", rows=pg["rows"],
                           rkpi=rkpi, pager=pg, period=period, q=q,
                           periods=PERIODS, chart={"labels": labels,
                                                   "values": values})


if __name__ == "__main__":
    # Port 5000 belongs to the IM 103 project; default to 5001.
    # Debug is opt-in: $env:FLASK_DEBUG=1; $env:PORT=5001; python app.py
    app.run(host="127.0.0.1",
            port=int(os.environ.get("PORT", 5001)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
