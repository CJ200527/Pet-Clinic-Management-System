# Changelog

## [Unreleased] — security hardening + data integrity (2026-10-30)
### Fixed
- `/admin/vets` raised `NameError: VET_STATUSES` (HTTP 500) whenever MySQL was
  reachable; the constant is defined again and drives the status dropdown.
- Removed the half-wired walk-in surface (`/admin/walk-in` redirect and the
  orphaned template) and corrected every doc that still advertised it.
- Guest booking can no longer rename an existing client by phone, and reuses
  the client's existing pet instead of inserting a duplicate row.
- Manual invoices reject appointment/consultation references that belong to a
  different client.
- Referenced inventory items can no longer be deleted (preserves prescription
  history). Pet age/weight `0` values are preserved instead of becoming NULL.
- DB-down render paths now receive complete template contexts.
### Added
- CSRF protection on every non-GET request: token in session, hidden `_csrf`
  input in all 27 POST forms, HTTP 400 on missing/mismatch. Logout is a POST.
- Login throttle (5 failures / 5 minutes per address + username) with a
  generic failure message; new accounts require 8+ character passwords
  (seeded demo accounts remain `123`).
- Transactions around guest booking, consultation + auto-bill, prescription +
  stock deduction, and queue numbering; queue now has a per-day unique ticket
  index with an idempotent upgrade in `setup_db.py`.
- Environment-driven config (`PETCLINIC_DB_*`, `PETCLINIC_SECRET_KEY`,
  `PETCLINIC_COOKIE_SECURE`), HttpOnly/SameSite=Lax cookies, 12-hour sessions,
  opt-in debug mode, default port 5001.
### Verified
- 33/33 checks on a disposable `petclinic_test` database: all GET routes
  (vets 200, walk-in 404), CSRF 400, booking dedupe/no-rename, approve → queue →
  consult → rx → paid → receipt, staff restrictions, invoice-ref rejection,
  throttle logic, queue unique index. Test DB dropped; demo data untouched.

## [Unreleased] — motion, modals, analytics, queue board, unified shell
### Added
- `/` always renders the public landing page (no auto-redirect into the admin
  dashboard when a session cookie exists). Signed-in staff now get a
  **Dashboard** nav shortcut instead of the Login button.
- Cascade unveil rebuilt as CSS-only (`main.content.cascade > *`,
  `nth-child` delays): the animation starts at first paint, so content no
  longer flashes fully rendered and then disappears into the entrance. Header
  lands first, blocks cascade downward, 0.4s per block / 0.045s step (~0.85s
  worst case vs the old 0.9s-per-block JS stagger). View Transitions opt-in and
  the JS class-adding stagger were removed (they competed with the cascade);
  `clinic.css`/`clinic.js` bumped to `?v=20261030`.
- Fixed sidebar shell: nav rail is `position: fixed` to the viewport (`top:0;
  bottom:0`) so scrolling the page no longer moves the sidebar; only content
  scrolls. Logout pinned via a `flex:none` footer, nav links scroll internally
  (`overflow-y:auto`) when the list exceeds screen height, and link/label
  spacing tightened so the full menu + Logout fit at 100% zoom. `.main` takes a
  `264px` offset (reset to 0 in the mobile drawer breakpoint); `sidebar.css`
  cache-bust bumped to `?v=20261029`.
- CPSC popup system (`vet-modals.css` + `vet-modals.js`): droplet entrance,
  fx21 floating fields, section cards, Cancel/Save footer, locked backdrop,
  one reusable decision shell replacing every native `confirm()`.
- All popups converted (walk-in, log consult, issue bill, create user, add
  item, booking view, auth error); Bootstrap JS dropped from converted pages.
- CPSC motion system: cascade-unveil staggered entrances on every admin page
  (header → content blocks, 0.22s steps, 0.9s settle) + View Transitions morph
  (frozen sidebar, gliding workspace) gated to sidebar clicks; skeleton owns
  fresh-login arrivals; reduced-motion respected throughout.
- Skeleton shimmer overlay (CPSC pattern) on fresh login: layout-mimicking gray
  blocks, `?welcome=1` trigger, ~1.2s play then fade; sidebar clicks bypass it.
- Live analytics on the dashboard: adaptive buckets (Today hourly / Week daily /
  All Time monthly, zero-filled), Bookings Trend, Queue Load doughnut, Top
  Services, Revenue from paid invoices; Now-Serving strip + next-2 below KPIs;
  30s auto-refresh with pause toggle (own state key).
- User approval flow: `users.status` (pending/approved/rejected; setup_db migrates
  old DBs, existing rows stay approved); new accounts enter pending, login
  blocks non-approved; approve/reject icon buttons; 5 KPI cards (Total, Admins,
  Staff, Vets, Pending); Period + Status funnel; Create User modal.
- Invoices follow page concept: Period + Status funnel, Issue Bill modal,
  print icon per row, full-height table.
- Auto-billing: optional amount on consultation logging auto-issues a linked
  unpaid bill (empty = no bill); printable receipt view with PAID stamp.
- Walk-in history page: Total/Today KPI cards, search + Period/Status funnel,
  full-height table with queue numbers, creation moved to an in-page modal.
- `appointments.source` column (`guest`/`walkin`; setup_db migrates old DBs,
  both forms stamp new rows) so histories can tell origins apart.
- Live queue board: Now-Serving strip (serving ticket + next-2 chips), 30s
  auto-refresh with pause toggle (state in sessionStorage), Period + Status
  funnel, full-height table; queue-serve icons stay staff-operable.
- CPSC control pattern on every list page (appointments pilot, then queue,
  consultations, inventory, invoices, clients, pets, users): header → KPI row
  (period-aware, cards link-filter their ledger) → action bar (search + refresh
  + existing filters) → badge table with 32px sprite icon buttons
  (view/edit/approve/reject/delete) + view modals where needed.
- Sprite gains `i-view`, `i-edit`, `i-x`; new `.action-bar`, `.badge-*`,
  `.icon-act` styles in `clinic.css`.
- Client records (no logins): `/admin/clients` searchable list + full profile
  (info, pets, visits, bills; staff-editable contact), `/admin/pets` registry
  with species filter + edit, `/admin/walk-in` front-desk form (approved visit
  today, optional instant queue).
- Offline vendor bundle (`static/vendor/`: Bootstrap 5.3.3 CSS + bundle JS,
  Chart.js 4.4.1) replacing every jsdelivr CDN tag (landing, admin shell,
  receipt, dashboard) — styling, charts, and mobile nav work with no internet.
  Dashboard chart init already guards `!window.Chart`, so a missing chart lib
  degrades to empty frames instead of breaking page JS.
- `database/demo_seed.py` (rerunnable): wipes owner/transactional test rows,
  keeps Admin/Staff, injects the checking ledger — Maria Santos + Juan Dela
  Cruz owners; Bantay (pending guest, tomorrow), Mingming (approved walk-in,
  queued #1 today), Tweety (completed + consult + paid P850 invoice); 4 stock
  items (Syringe 5ml at low-stock bell threshold).
- `clients` table (full_name, phone UNIQUE dedupe key, address) — everyone who
  booked or walked in; `users` is logins-only again (`admin`/`staff`).
- `vets` directory (full_name, specialty, phone, is_active) + `/admin/vets`
  list page (KPIs, search, Period/Status funnel, Add Vet modal,
  activate/deactivate toggles, sidebar nav; Admin-only mutate, Staff read).
- Attending-vet dropdown (active vets only) on Log Consultation (modal + form
  page); saving backfills `appointments.vet_id` + `clinic_queue.vet_id`, so the
  Vet column fills in across ledger, queue, and client history.
- `database/migrate_clients_vets.py`: one-shot live-DB migration (owners →
  clients with id remap, `owner_id` → `client_id`, vet FKs → `vets`, legacy
  consult vet_ids → Duty Veterinarian, `users.role` → `('admin','staff')`).
### Removed
- Owner-login surface deleted (5 `/client/*` routes, `templates/client/`);
  owners exist only as record rows (guest/walk-in auto-created).
- `vet` + `owner` roles removed from `users` (logins are admin/staff only);
  owner rows migrated to `clients`, vet names live in the `vets` directory.
- One header everywhere: shared `admin/_page_header.html` + `client/_page_header.html`
  includes (label, live clock, refresh, user block; bell on admin side via a
  context processor, no per-route changes). All admin pages use them.
### Changed
- Re-applied the header/strip color swap per user call (bold teal headers with
  white text; light Now-Serving strip).
- Queue doughnut shows a gray placeholder ring + "No queue today" label when the
  day has no queue rows (previously rendered blank).
- Dashboard charts fill their cards (no aspect lock, thicker bars, centered
  doughnut); Revenue and Top Services positions swapped; grid tuned to 60/40.
- Analytics grid tuned to 60/40.
- Swapped header/strip treatments (abandoned same day): page headers briefly took
  the bold teal gradient (white text, avatar, pill), Now-Serving strip takes the light card style.
- Analytics grid first row is 70/30 (trend wide, doughnut narrow).
  funnel holds Period + Prescription (All/With Rx/Without Rx); full-height table.
- Log Consultation is now an in-page Bootstrap modal (Cancel/Save), no navigation;
  layout tightened (search-box no longer stretches; funnel sits beside the button).
- Appointments action bar refined: search + Search + refresh + funnel clustered
  left; funnel opens one panel with Period + Status categories (standalone status
  dropdown removed); headers on list pages slimmed to bell-only (dashboard keeps
  the full header); tables roomier with viewport-filling card + responsive scroll.
- Sidebar polish: USERS group fully hidden for Staff, trailing lines on group
  labels, dividers below logo + above Logout; `?v=` cache-bust on all static links.
- Bell + live counts on every admin-side header (Admin and Staff alike).
- Consultations moved to `/admin/consultations` (list/new/detail, Admin + Staff
  operate jointly, shared list with logger column); queue-serve opened to Staff.
### Removed
- Vet-as-user surface deleted (6 routes, `templates/vet/`): vets are record-only
  names now; `dashboard_for('vet')` lands on the shared view-only dashboard.
- Pending Approvals card off the dashboard (approvals live in the ledger;
  pending KPI card links there); profile block off all sidebars (header owns it).
- CPSC-pattern admin dashboard: sky-teal header (label + live clock + period
  filter + refresh + bell with live badge + user block), 5 KPI cards with SVG
  icons (pending, queue, low stock, unpaid, consults), 4 Chart.js analytics
  frames (empty, data wired later), period-driven activity list.
- `static/css/clinic.css` + `static/js/clinic.js` (clock, panel toggles);
  sprite gains k-pending/k-queue/k-alert/k-bill/k-check + i-refresh/i-filter/i-bell.
- Sidebar nav regrouped: Dashboard | Operations (Appointments, Queue) |
  Inventory (Inventory, Invoices) | Users (Admin-only).
- Shared Admin/Staff dashboard: same data view for both roles
  (Admin acts, Staff view-only + operates queue/consults).
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
- Inventory Items KPI showed raw `dict.items` method text (key renamed to `total`).
### Changed
- Inventory rebuilt to page concept: KPIs → action bar (search + refresh +
  Period/Category funnel + Add Item modal button) → full-width stock table;
  Add Item is now an in-page modal (Cancel/Save).
- Full-width pages: dropped the Bootstrap `.container` wrapper that squeezed all
  list/form pages (header + tables now span exactly like the dashboard).
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
