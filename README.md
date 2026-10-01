# Pet Clinic Management System (Flask)

Web-based Pet Clinic Management System built with **Python (Flask)**, **MySQL (XAMPP)**,
**HTML5**, **Bootstrap 5**, and **JavaScript**.

> Stack change (2026-09-28): migrated from native PHP 8 (PDO) to Python Flask per
> instructor requirement. PHP files were deleted; behavior was preserved 1:1.

## Roles
- **Admin** — full powers: approve, mutate, Users management
- **Staff** — operates the system: shared dashboard (view-only), queue-serve,
  consultation logging; no approve/delete/users
- **Vet** — record-only name (assignable on bookings/consults, no login surface)
- **Owner rows** — not logins: client records auto-made by guest/walk-in bookings
  (phone dedupe), viewable + editable in Clients/Pets; shown on request

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
├── app.py                    # Flask app + routes (auth, guest booking, records, admin ops)
├── config.py                 # MySQL (XAMPP) connection + SECRET_KEY
├── requirements.txt          # flask, pymysql, bcrypt
├── database/
│   ├── setup_db.py           # CREATE DATABASE + 8 tables + Admin/Staff seeds (guarded)
│   └── __init__.py
├── templates/
│   ├── landing.html          # public booking landing page (EAVS Telly pattern + curtain + guest form)
│   ├── _sprite.html          # inline SVG icon sprite (paw, dashboard, calendar, users…)
│   ├── admin/base.html       # admin+staff sidebar shell (grouped nav, no profile)
│   ├── admin/_page_header.html  # shared header card (label, clock, filter, bell, user)
│   ├── admin/dashboard.html  # CPSC header + KPIs + chart frames + activity
│   ├── admin/appointments.html
│   ├── admin/consultations.html
│   ├── admin/consultation_form.html
│   ├── admin/consultation_detail.html
│   ├── admin/clients.html    # client records: searchable list
│   ├── admin/client_detail.html  # full client profile (pets, visits, bills)
│   ├── admin/pets.html       # pet registry + edit
│   ├── admin/pet_form.html
│   ├── admin/walkin.html     # front-desk walk-in registration
│   ├── admin/users.html
│   ├── admin/queue.html
│   ├── admin/inventory.html
│   ├── admin/inventory_form.html
│   └── admin/invoices.html
├── static/
│   ├── css/style.css + landing.css + sidebar.css + clinic.css
│   ├── js/main.js + sidebar.js + clinic.js
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
