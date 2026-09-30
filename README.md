# Pet Clinic Management System (Flask)

Web-based Pet Clinic Management System built with **Python (Flask)**, **MySQL (XAMPP)**,
**HTML5**, **Bootstrap 5**, and **JavaScript**.

> Stack change (2026-09-28): migrated from native PHP 8 (PDO) to Python Flask per
> instructor requirement. PHP files were deleted; behavior was preserved 1:1.

## Roles
- **Admin** — manage users, appointments, queue, inventory, billing
- **Veterinarian / Staff** — appointments, queue, consultation logging
- **Pet Owner (Client)** — pet registration, booking, queue status, invoices

## Features
- User / pet registration
- Appointment booking (owner → pending → approved/completed)
- Clinic queueing
- Consultation logging + prescriptions/treatments
- Inventory tracking
- Billing / invoices

## Project Structure
```
.
├── app.py                    # Flask app + routes (auth, guest booking, client, admin, vet)
├── config.py                 # MySQL (XAMPP) connection + SECRET_KEY
├── requirements.txt          # flask, pymysql, bcrypt
├── database/
│   ├── setup_db.py           # CREATE DATABASE + 8 tables + Admin/Staff seeds (guarded)
│   └── __init__.py
├── templates/
│   ├── landing.html          # public booking landing page (EAVS Telly pattern + curtain + guest form)
│   ├── _sprite.html          # inline SVG icon sprite (paw, dashboard, calendar, users…)
│   ├── admin/base.html       # admin sidebar shell (logo, profile, buttons, logout)
│   ├── vet/base.html         # vet sidebar shell
│   ├── admin/dashboard.html
│   ├── admin/appointments.html
│   ├── admin/users.html
│   ├── client/dashboard.html
│   ├── client/book_appointment.html
│   ├── client/my_pets.html
│   ├── client/my_invoices.html
│   ├── admin/queue.html
│   ├── admin/inventory.html
│   ├── admin/inventory_form.html
│   ├── admin/invoices.html
│   ├── vet/dashboard.html
│   ├── vet/queue.html
│   ├── vet/consultations.html
│   ├── vet/consultation_form.html
│   └── vet/consultation_detail.html
├── static/
│   ├── css/style.css + landing.css + sidebar.css
│   ├── js/main.js + sidebar.js
├── pictures/                 # pet photo ORIGINALS (do-not-edit; web copies in static/images/)
├── README.md / CHANGELOG.md / AGENTS.md / SESSION.md
└── System Requirements/      # instructor docs (untouched)
```

## Database (8 tables)
`users, pets, appointments, clinic_queue, consultations, inventory,
prescriptions_treatments, invoices` — created by `database/setup_db.py`
(schema source of truth; guarded so imports never run it).

## Setup (Windows + XAMPP) — same steps on any new device
1. Start **MySQL** in XAMPP Control Panel (Apache not needed for Flask).
2. Create the database (safe to re-run; seeds only on empty users table):
   ```powershell
   python database/setup_db.py
   ```
3. Install Python deps:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run (port 5000 is taken by another course project — use 5001):
   ```powershell
   $env:PORT=5001; python app.py
   ```
   Open `http://127.0.0.1:5001/` (landing page; login via the curtain).
   Delete any old `:5000/login` bookmark — that page no longer exists.

## Booking Model (guest-only, no public signup)
- Clients book as guests from the landing page (`POST /book-guest`): the system
  auto-creates an owner record (reused by phone number) + pet record; the
  appointment enters as `pending` with a booking reference #.
- There is NO public registration. All accounts (`/admin/users`, Admin only)
  are for staff/vet; owners never log in.

## Test Accounts (password: `123`, login with **username**, case-sensitive)
- `Admin` → shared dashboard (full powers: approve, mutate, Users management)
- `Staff` → same shared dashboard (view-only + Pending Approvals watchlist)
  plus vet Queue/Consultations pages for serving visits

## Design Language
- Booking landing page follows the EAVS Homestay Telly pattern (same class names:
  `telly-hero, btn-pill, booking-bar, spec-table, stat-num, gallery`), re-paletted
  to clinical teal (`--vet:#0f766e`). Login lives in a roll-down curtain —
  there is no standalone login page.
- Admin/vet dashboards use a left sidebar shell (logo, initial-avatar profile,
  teal active pill, pinned Logout, drawer on mobile) via `admin/base.html` /
  `vet/base.html`; icons are an inline SVG sprite (`_sprite.html`) — no emoji, no CDN.
- Admin system is slated for a full CPSC Inventory port (sidebar + topbar,
  hand-written CSS, modals/toasts) — direction locked, build pending.

## Security Notes
- Parameterized queries only (`%s` placeholders, no string formatting into SQL).
- Passwords hashed with `bcrypt` (`hashpw` on register/seed, fail-closed `checkpw` on login).
- `POST /login` processes auth; `GET /login` bounces to the landing curtain.
- Role guards (`login_required`, `role_required`) on every dashboard/booking route.
- Pet-ownership re-validated server-side on booking (dropdown not trusted).
- Login inputs hardened: `autocomplete=off`, readonly-until-focus, nothing prefilled.
