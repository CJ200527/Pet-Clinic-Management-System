# Changelog

## [Unreleased] — landing service details comparison dock (2026-11-18)
### Added
- **Clickable "What we offer" cards** on the landing page. The six cards are
  now buttons carrying the live service fee, duration and inclusions from the
  `services` table; hover lifts the card and reveals a "View details" hint.
- **`static/js/landing-services.js`**: each card opens a floating detail panel
  in `#svcDock` (fixed bottom-right) showing fee, duration and what is
  included. Any number of panels can stay open for side-by-side comparison;
  each collapses to its header with the minus button (plus to expand), closes
  with the × (animated), and Escape closes the most recently opened one. Card
  `aria-expanded`/`is-open` stay in sync, and re-clicking a card mid-close
  reopens it cleanly instead of leaving a ghost panel.
- New `i-minus` sprite symbol.

### Changed
- Landing dock styles in `landing.css` (scoped to `button.amenity`, so the
  vet-directory cards keep their static look); panels keep their natural
  height and the dock scrolls when many are open; mobile dock spans the
  viewport below 576px.
- `landing.css` / `landing-services.js` bumped to `?v=20261118b`.

### Verified
- `node --check`, `py_compile` clean. Browser on :5002: all six cards open
  panels with the seeded fee/duration/inclusions, six panels coexist and the
  dock scrolls, minimize swaps to plus and collapses the body, header click
  restores, × removes one and clears the card state, Escape removes the most
  recent, and a card clicked while its panel is closing reopens exactly once.
  Curtain (z 2000) still layers above the dock (z 1500). Temp server stopped;
  :5001 untouched.

## [Unreleased] — fixed service fees, Services page, queue→consultation handoff (2026-11-18)
### Added
- **`services` table** (fixed price list) in `setup_db.py`: six seeded
  services with researched mid-range Philippine fees and plain-language
  inclusions — General Checkup ₱500 (30 min), Vaccination ₱600 (20 min),
  Grooming ₱500 (60 min), Boarding ₱450/night, Surgery Consult ₱800 (30 min),
  Emergency ₱1,000 (30 min). `consultations.service_id` added via an
  idempotent upgrade (applied to the live DB).
- **`/admin/services` price-list page** (Admin + Staff view): KPI row
  (fixed/bookable/hidden/average fee), search + availability funnel, roomy
  table with fee, duration, inclusions and status. Admin edits fee, duration,
  inclusions and bookability through a `vet-overlay` modal that requires the
  admin's own password; the service name is read-only and services cannot be
  created or deleted. Staff sees no edit action and the route bounces.
- **Queue → consultation handoff**: marking a queue entry **done** now flashes
  "record the consultation and billing" and redirects to
  `/admin/consultations?log=<appointment_id>`. The Log Consultation modal
  opens itself, preselects the appointment, its vet and the service named in
  the booking reason, shows the fixed fee + inclusions, and focuses the
  diagnosis box.
- New `i-tag` sprite symbol; Services item in the Billing sidebar group.

### Changed
- **Consultation billing is server-derived**: the POST takes `service_id`
  and an invoice is created for `services.fee` (no editable `bill_amount`
  anymore). Saving completes the appointment and backfills queue/appointment
  vet as before; zero-fee services create no invoice.
- Landing "Popular Visits" cards, the guest booking dropdown, the New
  Appointment service dropdown and the consultation pickers all read the live
  service list with fees; hidden services disappear from booking.
- Consultations list gained a **Service** column; the detail page shows the
  service and its fee.
- `clinic.css ?v=20261118f` (fee preview, price tag, inclusions and toggle
  styles).

### Verified
- `py_compile` clean. Test client: queue done → 302 to the prefilled modal;
  consultation POST stored the chosen `service_id`, issued a ₱500 unpaid
  invoice for Grooming (ignoring a posted fake amount), completed the
  appointment; services edit rejected a wrong password (fee unchanged) and
  applied the correct one; Staff could view but not edit (POST bounced).
  Temp rows removed and seeded fees restored.
- Browser on :5002: Services page renders all six seeded fees/inclusions, the
  admin edit modal opens with fee/duration/inclusions/availability/password;
  `/admin/consultations?log=<id>` auto-opened the modal with appointment,
  Vaccination ₱600, the booking vet, inclusions and diagnosis focused.
  Temp server stopped; :5001 untouched.

## [Unreleased] — admin own-password gate for deletes and approvals (2026-11-18)
### Added
- **`verify_admin_password()`** in `app.py`: re-checks the signed-in admin's
  own bcrypt password for privileged writes. Fails closed on blank input, a
  non-admin session, a DB error, or a corrupt hash (same pattern as CPSC
  Inventory's destructive-confirm gate).
- **Password field in the shared decision modal** (`_decision_modal.html`):
  appears only for forms marked `data-confirm-password="required"`; confirms
  cannot be sent blank, the eye button shows/hides the text, and the typed
  secret is injected as a hidden `admin_password` field on submit.
- `i-eye` sprite symbol; `.decision-pw` / `.pw-toggle` styles in
  `vet-modals.css`.

### Changed
- These admin actions now require the admin's password:
  approve/reject a booking (`/appointments/<id>/status`), mark an invoice paid
  or cancel it (`/invoices/<id>/status`), approve/reject a login account
  (`/users/<id>/status`), delete a login account (`/users/<id>/delete`),
  activate/deactivate a vet (`/vets/<id>/status`), and delete a queue ticket
  (`/queue/<id>/delete`).
- Staff-facing routine actions stay password-free: queue serve/done/skip,
  logging consultations, editing client/pet records, own profile/photo.
- Wrong/blank password flashes a plain "Wrong admin password — nothing was
  changed." and leaves the record untouched.
- Guide: new "When the clinic asks for your password" section plus notes on
  each protected step.
- Static `vet-modals.css ?v=20261118c`, `vet-modals.js ?v=20261118c`.

### Verified
- `py_compile` and `node --check` clean.
- Test client (Admin): all 6 gated routes reject blank and wrong passwords
  (flash shown, no change) and accept the correct password; Staff is bounced
  from the admin-only route even when sending a password; every list page
  renders the password-marked form and the modal's password input.
- Browser on :5002: delete modal shows the password box, blank confirm is
  blocked client-side, wrong password returns "Wrong admin password — nothing
  was deleted." with the row count unchanged, eye toggle works, skip modal
  stays password-free; typed password is injected as `admin_password`.
- Temp :5002 server stopped; :5001 untouched.

## [Unreleased] — queue automation, clearer actions, popup stacking (2026-11-18)
### Added
- **Auto-queue**: approving a same-day appointment adds it to the queue as soon
  as its scheduled time arrives. A sweeper runs on Dashboard and Queue loads
  (`_auto_queue_due`), and both pages auto-refresh every 30s, so an afternoon
  slot joins in the afternoon without anyone pressing Add to Queue. Future
  dates stay out until their day/time. Manual **Add to Queue** is retained for
  walk-ins, emergencies and early service.
- **Delete ticket** (Admin only, X icon, confirmation): hard-deletes the queue
  row and sets `appointments.auto_queue=0` so the sweeper does not recreate it.
  Staff still use **Skip** (ticket kept, marked Skipped).
- `i-play` and `i-skip` sprite icons; `.icon-serve` / `.icon-skip` hover colors.
- `appointments.auto_queue TINYINT(1) DEFAULT 1` in `setup_db.py` plus an
  idempotent upgrade (applied to the live DB).

### Changed
- Queue row actions: **play** = start serving, **check** = mark done,
  **skip-forward** = skip, **X** = delete. Status badges are capitalized and
  the table is titled "Queue Entries" so Skipped/Done rows are obvious.
- Manual queue add now checks for an existing ticket first ("already has a
  queue ticket") on top of the UNIQUE `appointment_id` constraint.
- **Filter popups** no longer paint behind frosted cards: `.action-bar` is
  `position:relative; z-index:150`, and `clinic.js` adds `.pop-front`
  (`z-index:140`) to the card hosting an open panel; header stays at 200.
- Guide updated for auto-queue, the new icons, and skip vs delete.
- Static `clinic.css ?v=20261118e`, `clinic.js ?v=20261118c`.

### Verified
- `py_compile` clean. Test client 14/14 checks: due appointment auto-queued;
  future-time and tomorrow appointments not queued; approving a due pending
  booking queues it with a clear flash; skip renders as "Skipped"; delete
  removes the ticket, opts the appointment out, and stays deleted; manual
  duplicate blocked; delete button visible to Admin only.
- Browser on :5002: queue rows show play/check/skip/X for Waiting, check/skip/X
  for Serving, X for Done; card filter host computes `z-index:140`, action bar
  `150`, header `200`.

## [Unreleased] — readable dates in every data table (2026-11-18)
### Added
- **`pretty_date` / `pretty_when` Jinja filters** in `app.py`:
  - `pretty_date` → `August 30, 2026` (datetimes drop their time).
  - `pretty_when` → `August 30, 2026 | 12:00`; with a second argument it
    joins a DATE column and its TIME column
    (`a.appointment_date|pretty_when(a.appointment_time)`).
  - Handles `date`, `datetime`, MySQL `TIME` (PyMySQL returns `timedelta`),
    `time`, and ISO strings; missing values render `—`. Time is 24-hour
    `HH:MM`, matching the requested `12:00` sample.

### Changed
- Every data table now uses the filters instead of raw values: dashboard
  Recent Activity (Booked + Visit Date), Appointments (table + view modal),
  Queue, Consultations (table, detail header, appointment pickers), Invoices,
  Client record (visit history + bills), all eight report registers, and the
  printed receipt (date-only).

### Verified
- `py_compile` clean; Flask test client renders all list/detail/report pages
  with the new format and zero leftover `YYYY-MM-DD` cells; browser on :5002
  confirmed appointments, queue and report tables. Fixed a name collision
  found during verification (`datetime.time` shadowed the `time` module —
  imported as `clock_time`).

## [Unreleased] — Reports section (CPSC hub pattern, clinic data) (2026-11-18)
### Added
- **Reports module** (sidebar → Reports; Admin + Staff, read-only):
  - **Hub** (`/admin/reports`): grouped report cards in the CPSC hub pattern
    (Operations: Appointments / Queue / Consultations; Clients & Pets:
    Clients / Pets / Vets; Finance: Invoices; wide Performance card:
    Revenue & Collections) plus a **Record Lookup** box that jumps straight
    to the ledger holding a typed booking #, invoice #, queue ticket #,
    phone number or name (`/admin/reports/lookup`).
  - **Register reports** (`/admin/reports/<kind>`) for appointments, queue,
    consultations, invoices, clients, pets, vets and revenue. Each follows
    the list-page law: period-aware KPI row → action bar (search, refresh,
    **print**, period funnel) → left-aligned badge table → pager. Money KPIs
    and print-ready layout included; `@media print` strips the sidebar,
    action bar, toasts and pager.
  - **Revenue & Collections**: Collected / Outstanding / Paid / Unpaid KPIs,
    monthly collections bar chart (paid bills, last 6 months, zero-filled),
    collected-vs-outstanding doughnut, and the period's bills table.
- `clinic.css` gained `.report-*` hub/lookup styles (teal) and the print
  block; static `?v=20261118d`.

### Verified
- `py_compile` clean; Flask test client: all 8 registers 200 (with period /
  status / species / rx filters), bogus kind bounces to the hub, lookup
  redirects correct for name / id / no-match, Staff can read every report.
- Browser on :5002: hub cards render, Appointments Report KPI row + funnel,
  Revenue page renders both charts. Two bugs found and fixed en route
  (pets register SQL had WHERE before FROM; `chart.values` in Jinja hit the
  dict method — now `chart['values']`).

## [Unreleased] — unified creation modals, uniform list pages, per-chart filters (2026-11-18)
### Fixed
- **Every form-wrapped modal had its Cancel/Save footer clipped off the screen**
  (New Appointment, Add to Queue, Log Consultation, Issue Invoice, Create User,
  Add/Edit Vet). The `.vet-modal-box` is a column flex container, but wrapping
  header/body/footer in `<form>` broke the chain, so `.vet-modal-body` could not
  scroll and `overflow:hidden` cut the footer. Added
  `.vet-modal-box > form { flex:1 1 auto; min-height:0; display:flex;
  flex-direction:column; overflow:hidden }`.
- The CPSC page cascade (`main.content.cascade > *`) no longer animates
  `.vet-overlay`; its retained transform was re-anchoring `position:fixed`
  children and delaying first paint.
- Save buttons now disable and read "Saving…" while posting (double-submit
  guard), and reset on `pageshow` when the browser restores a cached page.
- New Appointment no longer rounds the time down to `:00` (keeps `:30` slots);
  existing-client mode now requires the pet and blocks submission until valid.

### Changed
- Action bars on every list page follow one pattern: search + refresh + filter
  funnel grouped left, `.bar-spacer`, create-record button pinned right. Queue's
  separate inline "Add Approved Appointment" card became a CPSC modal.
- Clients gained the Period funnel; pets/clients keep funnel-but-no-create
  because their records originate from booking/Settings.
- Dashboard header lost its period filter and refresh. Each analytics card
  (Bookings, Queue, Revenue, Top Services, Recent Activity) now has its own
  funnel; periods travel as `bk`/`qp`/`rev`/`svc`/`rec` query params and every
  link preserves the other cards' selections. Buckets adapt: hourly (Today),
  daily last-7 (This Week), six monthly (All Time), zero-filled.
- Tables are uniform: every `th`, `td`, and action cell is left-aligned; action
  icon buttons sit left with a right margin; `text-end` removed from Actions
  headers.
- People display surname-first via the `person_name` Jinja filter
  ("Admin, System", "Dela Cruz, Juan") in the header user block and Users list;
  role pills and usernames are unchanged.
- Static versions bumped to `?v=20261118c`.
- **Bell/filter popups no longer hide behind KPI cards** (user-reported,
  dashboard screenshot). The KPI cards build their own stacking contexts
  (backdrop-filter + hover lift), so they painted over the absolutely
  positioned notification panel that lives inside the header. `.top-header`
  now has `position: relative; z-index: 200`, lifting the whole header —
  and its dropdown panels — above every card that follows it. Verified on
  the dashboard (bell panel over KPIs) and appointments (funnel panel over
  the table) in the browser on :5002.

### Verified (browser on a temp :5002 instance, Admin/123)
- Modal footers visible and bodies scrollable on appointments, queue,
  consultations, invoices, users, vets, settings (new + edit vet).
- New Appointment created a real row through the modal; queue modal added an
  approved appointment to today's line. Both test rows removed afterwards.
- Dashboard rendered 4 charts; clicking Bookings → Today produced
  `?bk=Today&qp=All+Time&rev=All+Time&svc=All+Time&rec=All+Time`, changed only
  that card's label/dataset (hourly buckets), and left the others on All Time.
- Header tools on the dashboard contain only the bell and user block; every
  list page reports left-aligned `th`/`td`; Users and the header show
  surname-first names. `py_compile` clean.

## [Unreleased] — simpler clinic scope + Settings with photo uploads (2026-11-18)
### Added
- **Settings** (`/admin/settings`, Admin + Staff): My Profile card (name, email,
  read-only username, optional password change with current-password check) and
  a profile-photo card (PNG/JPG/WEBP up to 3 MB, preview before save, remove).
  The header avatar now renders the uploaded photo and links to Settings.
- **Vet Profiles** on the same page: photo thumbnail, specialty, phone, email,
  license no., short background, active toggle, consults count. Admin gets
  **Add Vet** and per-vet edit modals (multipart). The Vets directory now shows
  the profile thumbnail next to each name.
- **New Appointment** on Appointments (Admin + Staff): books a walk-in/phone
  client. Existing client or new owner + phone (de-duplicated by phone), existing
  or new pet, service/date/time/vet/notes, and an optional same-day queue
  ticket. Saved `approved` with `source='walkin'`.
- Upload pipeline `_store_image()` / `_delete_image()`: real format from magic
  bytes, 3 MB cap, random server-side filename, basename-only deletes; images
  live in `static/uploads/avatars/` and `static/uploads/vets/`.

### Changed
- **Inventory retired from the UI**: routes, list/form templates, sidebar group,
  dashboard KPI, bell low-stock row, and consultation stock picker are gone.
  The `inventory` table stays in MySQL only so legacy prescription names still
  resolve. Prescriptions are now free text (medicine, dosage, instructions).
- Dashboard is now 4 KPI cards (Pending, Queue Today, Unpaid Bills, Consults).
- Queue **Add to Queue** is available to Admin + Staff (was Admin only), matching
  the simplified flow: staff book walk-ins → queue → consult → bill.
- Guide (`/admin/guide`) and `GUIDE.md` updated: English throughout, Inventory
  removed, New Appointment + Settings documented, role matrix and glossary
  refreshed.

### Database
- Idempotent upgrades in `database/setup_db.py`: `users.avatar`,
  `vets.email/license_no/bio/photo`, `prescriptions_treatments.medicine_name`.
  Applied to the live `petclinic` database.

### Verified
- `py_compile` clean; test client: 37/37 checks (settings for both roles,
  avatar upload/remove + file lifecycle, profile validation, vet create/edit
  with photo, staff write blocked, walk-in appointment + queue ticket, removed
  inventory URLs 404, dashboard 200). Test rows and files cleaned up.
- Not verified in a real browser this pass; run the app on :5001 and open
  Settings to confirm the visual layout.

## [Unreleased] — corrections + CPSC-style visual pass (2026-11-17)
### Fixed
- Status/toggle handlers (appointment, queue, invoice, user, vet) now check the
  row exists before `UPDATE`; MariaDB reports 0 affected rows for a no-op
  change, so the old code said "not found" for a real row already in that state.
  Missing rows now flash "… #N not found." instead of silently "succeeding".
- Appointment KPIs complete (`Total / Pending / Approved / Completed /
  Cancelled`); consultations/inventory/users KPI totals no longer depend on the
  active period filter.
- Client edit validates name and phone separately; guest booking and client edit
  share one PH mobile rule (starts `09`, exactly 11 digits).
- Pet edit blocks non-numeric age/weight and out-of-range values with per-field
  messages (age 0–50, weight 0–200).
- Restarting `app.py` no longer leaves anyone logged in: sessions carry a
  per-process `_run` token, so an old cookie is dropped and the landing page is
  shown again. Guarded routes also re-check the account (exists + approved) and
  re-read its role on every request, so a deleted/rejected user or a changed
  role takes effect immediately.
- Sidebar horizontal scrollbar removed (hover slide pushed the nav past its
  width): `.snav` now clips horizontal overflow and keeps vertical scrolling.
- Bell counts come from one query (`inject_bell`) instead of several round trips.
- Removed the dead `/register` stub, a duplicate `timedelta` import, the unused
  `style.css`, and a leftover JS line pointing at a non-existent page.

### Added
- Server-side pagination on all 9 list pages (`?page=`, 20 rows/page) via a
  shared `paginated()` helper + `_pager.html` ("Showing X–Y of Z", windowed page
  numbers). Out-of-range pages clamp to the last page.
- Global flash toasts on the admin shell (`toast-stack`, success/danger icons,
  auto-dismiss 5 s, manual X). Per-page alert strips removed.
- Sprite symbols: `i-chevron-left/right`, `i-alert`, `i-stethoscope`, `i-syringe`,
  `i-scissors`, `i-home`, `i-microscope`, `i-phone`, `i-mail`, `i-pin`.

### Changed (visual pass — teal kept, no backdrop photo)
- `clinic.css` design-system block: frosted white glass panels over a soft teal
  radial + cream linear gradient page background (CSS only — no image), hover
  lifts on KPI cards, animated dropdown/filter panels, sticky table headers,
  row-hover tint, focus rings, styled pager, `badge-teal` KPI card, reduced-motion
  guards.
- `sidebar.css`: rail gradient, hover slide on nav links, active-link glow.
- `vet-modals.css`: blurred backdrop, modal rim, tinted section cards, button
  hover lift.
- Landing page: all emoji replaced with sprite icons (navbar, amenities, footer,
  curtain), icon colours/sizes tuned in `landing.css`.
- `admin/base.html`/`landing.html`/`receipt.html` asset `?v=` bumped to
  `20261117a` (sidebar.css to `20261117b` for the overflow fix).
- In-app guide and `GUIDE.md` rewritten in plain English (sidebar label is now
  **Guide**); no Cebuano text left in the app UI.

### Verified (2026-11-17)
- `py_compile` clean; Flask test client: 9 list pages 200 for Admin and Staff,
  `/admin/users` 302 for Staff, `page=99` clamps, page 2 renders.
- Browser (verification instance on :5002): `.shell` background is the teal
  gradient, `.card` = `rgba(255,255,255,.86)`, sticky `thead`, 5 KPI cards on
  appointments/dashboard, zero `.alert` strips, landing has 0 emoji and 9 sprite
  icons, and a POST to a missing vet id rendered the danger toast
  ("Vet not found.") then auto-dismissed.
- Restart behavior reproduced in a browser: logged in on :5002, restarted the
  server, `GET /admin/dashboard` → `302 /?auth=open` (landing, Login button,
  no Dashboard shortcut). Test client: Admin 200 dashboard/users, Staff 302 on
  `/admin/users`, a session pointing at a missing user id is rejected.
- Guide: renders 200 in English, no Cebuano words left. Sidebar:
  `.snav` scrollWidth == clientWidth (218px) with `overflow-x: hidden`,
  the rail stays 264px wide and only scrolls vertically.

## [Unreleased] — XAMPP/MySQL repair (2026-10-30)
### Fixed
- XAMPP MariaDB 10.4.32 no longer aborts on startup ("MySQL shutdown
  unexpectedly"). Root causes found in the live data directory:
  InnoDB reported `[FATAL] InnoDB: Aborting because of a corrupt database page`
  (crash dump `mysqld.dmp`), the redo log carried a lower LSN than `ibdata1`
  ("page log sequence number ... is in the future"), and the `mysql` system
  tables (Aria/MyISAM) were flagged crashed with broken index headers
  (`Index for table '.\mysql\db' is corrupt`). `C:\xampp\mysql\data` was
  rebuilt with `mysql_install_db.exe`; the `mysql` schema holds only
  `root`/`pma` logins.
- All user databases were preserved: `petclinic`, `cpsc_inventory`,
  `cpsc_inventory_db`, `eavs_homestay`, `production_inventory_db`,
  `sa_attendance_db`, `phpmyadmin`, `test` (logical dump restored, row counts
  identical, `uq_queue_day_number` index intact, `mysqlcheck` all OK).
- `mysql.db` had to be recreated with the `pma` control user restored.
- Residual startup hang (found while re-testing the repair): mysqld created its
  listening socket, logged `Server socket created on IP: '::'`, then never
  reached `ready for connections`; clients sat on `ERROR 2013 (HY000): Lost
  connection ... at 'handshake: reading initial communication packet'` until
  the process was killed. Cause: `mysql/proxies_priv` was left with a corrupt
  index by an earlier force-killed mysqld (`aria_chk -c mysql\proxies_priv` →
  `Index is corrupted` / `doesn't have a correct index definition`, so it could
  not even be repaired). Fix: its three files (`proxies_priv.frm/.MAD/.MAI`)
  were replaced from a throwaway `mysql_install_db.exe` datadir; mysqld then
  logged `Zerofilling moved table: '.\mysql\proxies_priv'` and
  `ready for connections` straight away, and a cold start now becomes ready in
  ~1 second.
### Changed
- `C:\xampp\mysql\bin\my.ini`: `innodb_use_native_aio=0` (Windows async I/O was
  failing with `'aio write' returned OS error 206`), and buffer-pool
  dump/reload at shutdown/startup disabled (stale page IDs aborted or hung
  startup). Both are stability-only trade-offs on a local dev box.
### Verified
- 5 clean start → query → graceful-shutdown cycles on the rebuilt datadir
  (plus isolated steps: install / cycles / grant / restore), `mysqlcheck
  --all-databases` clean, disk write integrity (sequential + random-offset,
  `FlushFileBuffers`) 0 corrupt blocks.
- Flask app against the restored DB: `GET /` 200 (login curtain), `POST /login`
  `Admin`/`123` 200, all 10 admin pages 200 (dashboard, appointments, clients,
  pets, queue, consultations, inventory, invoices, users, vets).
- Post-fix re-run: `mysqlcheck --all-databases --check` → every table `OK`
  (including `mysql.proxies_priv`); petclinic row counts unchanged (clients 7,
  pets 8, appointments 8, queue 5, consultations 5, invoices 5, inventory 4,
  prescriptions_treatments 4, vets 3, users 2); `mysql.user` holds
  `root@{localhost,127.0.0.1,::1,cetwen}` + `pma@localhost`; `uq_queue_day_number`
  intact. Flask smoke test via HTTP session + CSRF: `GET /` 200 (curtain) →
  `POST /login` 302 → all 11 pages under `/admin/*` 200 (dashboard 22785 B,
  appointments, clients, pets, queue, consultations, inventory, invoices,
  users, vets, guide).
### Notes
- Backups kept: `C:\xampp\mysql\data-BAK-2026-10-30-1835` (pre-repair copy of
  the broken datadir) and `C:\xampp\mysql\backup\userdb-dump-2026-10-30-1839.sql`
  (restorable SQL of every user database). Rebuild path:
  `python database/setup_db.py` → `python database/demo_seed.py`.
- `mysql_error.log` can look truncated: after `Server socket created on IP:
  '::'` mysqld writes the remaining startup lines to the console, so a normal
  (non-redirected) start appears to "stop" at that line even though the server
  is healthy. Confirm with `mysqladmin -u root ping`, not with the log tail.
- Never kill mysqld with `Stop-Process -Force` / Task Manager: that is exactly
  what leaves Aria system tables (`db`, `global_priv`, `proxies_priv`) with
  crashed flags and corrupt indexes. Use the XAMPP **Stop** button or
  `C:\xampp\mysql\bin\mysqladmin.exe -u root shutdown`.

## [Unreleased] — in-app plain-language guide (2026-10-30)
### Added
- `/admin/guide` (sidebar → **Help → Giya**): a read-only, DB-free walkthrough
  written in simple Cebuano + English — what the system is, the end-to-end
  patient flow, per-module steps (dashboard → invoices → users), the role
  matrix, a glossary, start commands, pitfalls, and a 5-minute demo script.
  Open to Admin and Staff (`login_required`); no queries, so it renders even
  with MySQL down.
- `GUIDE.md` at the repo root — printable/shareable twin of the guide page.
- Sprite symbol `i-book` for the nav; guide styles in `clinic.css`
  (`?v=20261030b`).

### Verified
- `py_compile` clean. Test client: anonymous `/admin/guide` → 302 to
  `/?auth=open`; Admin 200; Staff 200; the sidebar link renders for both roles;
  the new CSS version serves the `.guide-*` rules. (MySQL was stopped — the
  page is DB-free by design, the only DB log line is the existing bell probe.)

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
