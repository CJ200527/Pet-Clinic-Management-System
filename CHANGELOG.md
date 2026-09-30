# Changelog

## [Unreleased] — landing, curtain auth, full modules, portable DB
### Added
- Shared Admin/Staff dashboard: same data view for both roles, with a prominent
  Pending Approvals card (Approve/Decline inline, Admin only).
- Dedicated `staff` role in the ENUM (`setup_db.py` + live ALTER); Staff lands on
  the shared dashboard, keeps vet Queue/Consultations pages; Users page hidden
  from Staff with a view-only banner on the shared shell.
- Left sidebar nav shell (screenshot pattern, vet-teal theme): logo + name,
  initial-avatar profile block, teal active pill, Logout pinned bottom,
  slide-in drawer on mobile. Shared `admin/base.html` + `vet/base.html`;
  all 11 admin/vet pages extend them (top navbars removed).
- Inline SVG icon sprite (`templates/_sprite.html`): paw, dashboard, calendar,
  users, queue, box, receipt, pulse, logout, menu — no emoji, no CDN.
- Dedicated `/admin/appointments` ledger (status filter + inline setter,
  returns to ledger after save); dashboard keeps recent-8 summary.
- Guest booking (`POST /book-guest`): name + phone + pet + service + date/time,
  no account needed; auto-creates owner (reused by phone) + pet records,
  appointment enters `pending`, confirmation shows booking reference #.
- Admin Users page (`/admin/users` + delete): the ONLY way accounts are made.
- Public `/` booking landing page (EAVS Telly pattern, vet palette `--vet:#0f766e`):
  sticky nav, teal-gradient hero, about+gallery, services split, stats band,
  popular-visit spec cards, booking bar, live vets, contact split, 4-col footer.
- `static/css/landing.css` (same class names as EAVS) + `static/images/` web copies
  of the 7 `pictures/` pet photos (originals untouched).
- Booking-bar passthrough: service/date/time survives login via `safe_next`
  (open-redirect-guarded, query + POST fields) and prefills the booking form.
- EAVS-style roll-down login curtain (`#loginCurtain`: teal shade, blurred puppy bg,
  Esc/shade-click/Back-to-site close, autofocus); carries booking picks as hidden fields.
- Failed logins → `/?auth=failed`: curtain auto-opens with Cancel/Confirm error popup.
- Pet CRUD: `GET/POST /client/my-pets` + ownership-checked delete.
- Client dashboard: live counts + upcoming-5; bills card links to my-invoices.
- Admin: stats, recent-8 appointments with inline status setter, queue add/status,
  inventory CRUD, invoice issue/status, lowest-stock list.
- Vet: assigned appointments, today's queue + status, consultation log (auto-completes
  appointment), detail page with prescription add + automatic stock deduction.
- Invoices: admin issue + client pay (`paid`, ownership-checked).
- `PORT` env override (standard: 5001 — port 5000 belongs to the IM 103 project).
### Changed
- Admin list pages (dashboard, appointments, queue, inventory, invoices) are
  readable by Staff; all mutations stay Admin-only server-side, action buttons
  render for Admin only.
- **Login is username + password** (email rejected): `users.username` UNIQUE;
  register requires username (3+ chars, dual dup-check on username + email).
- Seeds are exactly `Admin` (admin) + `Staff` (staff role), password `123` (bcrypt).
- Database setup is `database/setup_db.py` (guarded `__main__`, runtime bcrypt seeds,
  idempotent); `database/pet_clinic_db.sql` deleted. New-device flow:
  `python database/setup_db.py`.
- Curtain inputs hardened (`autocomplete=off`, readonly-until-focus, no prefill);
  `bcrypt.checkpw` wrapped fail-closed (bad hash → rejected, never 500).
### Removed
- Public registration: curtain link, `/register` route (bounces with notice),
  and `register.html` deleted. Clients book as guests; Admin creates all accounts.
- 8 legacy PHP files + stale `C:\xampp\htdocs\petclinic` deploy copy.
### Fixed
- Login Enter/Tab bug: `readonly` fields skip browser validation, so Enter in
  username submitted an empty password straight to the failure popup. Now Enter
  in username jumps to password, and the form drops `readonly` on submit so
  empties are blocked client-side — popup fires only on real bad credentials.
- Doubled seed-header comment in the old SQL file (editor error badge).

## [v0.2] — 2026-09-28 — Flask migration
### Changed
- Migrated stack from native PHP 8 (PDO) to Python Flask per instructor requirement.
- Replaced `login.php / register.php / logout.php / config/db.php` with
  `app.py + config.py` (Flask routes, Flask session, pymysql, bcrypt).
- Replaced `client/book-appointment.php` with `templates/client/book_appointment.html`
  + `GET/POST /client/book-appointment` route (same validation + `pending` insert).
- Replaced PHP dashboards with Jinja2 templates
  (`templates/client|admin|vet/dashboard.html`).
- Added `requirements.txt` (flask, pymysql, bcrypt), `static/css|js`, `templates/`.
### Removed
- Deleted 8 PHP files: `login.php, register.php, logout.php, config/db.php,
  admin/dashboard.php, vet/dashboard.php, client/dashboard.php,
  client/book-appointment.php`.
- Removed stale deploy copy `C:\xampp\htdocs\petclinic` (PHP no longer served).
### Kept
- `database/pet_clinic_db.sql` unchanged (8 tables + 3 bcrypt seed users).
### Docs
- Added `README.md, CHANGELOG.md, AGENTS.md, SESSION.md`.

## [v0.1] — 2026-09-25 — PHP baseline
- PHP 8 + PDO + MySQL (XAMPP) auth system (`config/db.php`, `register.php`,
  `login.php`, `logout.php`) with role redirects.
- `client/book-appointment.php` (owner pets + vet dropdowns, `pending` insert).
- Placeholder `admin / vet / client` dashboards.
- `database/pet_clinic_db.sql` (8 tables, 3 seed accounts, `password123`).
