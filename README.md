# Pet Clinic Management System (Flask)

Web-based Pet Clinic Management System built with **Python (Flask)**, **MySQL (XAMPP)**,
**HTML5**, **Bootstrap 5**, and **JavaScript**.

> Stack change (2026-09-28): migrated from native PHP 8 (PDO) to Python Flask per
> instructor requirement. PHP files were deleted; behavior was preserved 1:1.

## Roles
- **Admin** — full powers: approve, mutate, Users + Vets management
- **Staff** — operates the system: shared dashboard, queue-serve,
  consultation logging (picks attending vet); no approve/add/toggle/users
- **Vets** — directory rows (`vets` table: name, specialty, active toggle),
  not logins; the attending vet is chosen when logging a consultation
- **Clients** — record rows (`clients` table: name, unique phone, address),
  auto-made by guest bookings (phone dedupe); no login surface

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
│   ├── setup_db.py           # CREATE DATABASE + 10 tables + Admin/Staff/Duty-Vet seeds (guarded)
│   ├── migrate_clients_vets.py  # one-shot live upgrade (owners→clients, vet FKs, role ENUM)
│   ├── demo_seed.py          # rerunnable checking ledger (vets, clients, visits, bills)
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
│   ├── admin/users.html
│   ├── admin/vets.html     # vet directory (KPIs, funnel, Add modal, toggles)
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

## Database (10 tables)
`users` (logins: admin/staff only), `clients, vets, pets, appointments,
clinic_queue, consultations, inventory, prescriptions_treatments, invoices`
— created by `database/setup_db.py` (schema source of truth; guarded so
imports never run it). One-shot live upgrade:
`database/migrate_clients_vets.py`. Demo ledger: `database/demo_seed.py`.

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
4. Run (defaults to port 5001; port 5000 belongs to another course project):
   ```powershell
   python app.py
   ```
   Open `http://127.0.0.1:5001/` (landing page; login via the curtain).
   Debug mode is opt-in with `$env:FLASK_DEBUG=1`.

## Booking Model (guest-only, no public signup)
- Clients book as guests from the landing page (`POST /book-guest`): the system
  reuses the client record by phone (a public form never renames it), reuses an
  existing pet of the same client/name/species, and adds a `pending` appointment
  with a booking reference #.
- Consultations name the attending vet (active directory only); the visit's
  vet fields backfill automatically. There is NO public registration.

## Test Accounts (password: `123`, login with **username**, case-sensitive)
- `Admin` → shared dashboard (full powers: approve, mutate, Users management)
- `Staff` → same shared dashboard (operates queue + consultations; no
  approve/add/toggle/users)
- The seeded `123` password is **demo-only**; new accounts require 8+ characters.

## Design Language
- Booking landing page follows the EAVS Homestay Telly pattern (same class names:
  `telly-hero, btn-pill, booking-bar, spec-table, stat-num, gallery`), re-paletted
  to clinical teal (`--vet:#0f766e`). Login lives in a roll-down curtain —
  there is no standalone login page.
- Admin/staff dashboards use a left sidebar shell (logo, teal active pill,
  pinned Logout, drawer on mobile) via `admin/base.html`; icons are an inline
  SVG sprite (`_sprite.html`) — no emoji, no CDN.
- The admin system follows the CPSC Inventory port: sidebar + topbar,
  hand-written CSS, modal shells, KPI/funnel list pages.

## Security Notes
- Parameterized queries only (`%s` placeholders, no string formatting into SQL).
- Passwords hashed with `bcrypt` (`hashpw` on register/seed, fail-closed `checkpw` on login).
- Every non-GET request carries a session CSRF token (`_csrf`); a missing or
  mismatched token is rejected with HTTP 400. `Logout` is a POST form.
- Login is throttled per client address + username (5 failures / 5 minutes,
  in-memory per process). New accounts require 8+ characters.
- `POST /login` processes auth; `GET /login` bounces to the landing curtain.
- Role guards (`login_required`, `role_required`) on every dashboard/booking route.
- Server-side re-validation on every mutation: guest booking never renames a
  client, invoice references must belong to the selected client, inventory
  deletes are blocked while prescriptions reference the item, and
  consultation/prescription/queue writes run in transactions.
- Session cookies are HttpOnly + SameSite=Lax, expire after 12 hours, and are
  Secure only when `PETCLINIC_COOKIE_SECURE=1` (HTTPS deployments).
- Config is environment-driven: `PETCLINIC_DB_HOST/NAME/USER/PASS`,
  `PETCLINIC_SECRET_KEY`, `PETCLINIC_COOKIE_SECURE`, `PORT`, `FLASK_DEBUG`.
  The checked-in dev fallbacks are not production-safe.
- Login inputs hardened: `autocomplete=off`, readonly-until-focus, nothing prefilled.
