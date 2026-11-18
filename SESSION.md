# SESSION.md — AI Continuity Log (read this every new session)

## Last Done (2026-11-18j — landing service detail comparison dock)
- **"What we offer" cards are clickable** (`button.amenity`) and carry each
  service's live fee, duration and inclusions as `data-svc-*` attributes.
  Hover lifts the card and fades in "View details".
- **`static/js/landing-services.js`** builds a floating panel in `#svcDock`
  (fixed bottom-right) per card: fee, duration, "What is included". Multiple
  panels stay open for side-by-side comparison; minus collapses a panel to its
  header (plus restores), × closes with a 170 ms exit animation, and Escape
  closes the most recent. Card `aria-expanded`/`is-open` stay in sync, and a
  card clicked while its panel is closing reopens exactly once.
- **Styles** in `landing.css` are scoped to `button.amenity` so the vet
  directory (`div.amenity`) stays static. Panels use `flex: none` so six open
  panels scroll inside the dock instead of squashing; below 576px the dock
  spans the viewport (62vh max). Curtain (z 2000) sits above the dock
  (z 1500). New `i-minus` sprite. Assets `?v=20261118b`.
- Verified: `node --check` + `py_compile`; browser :5002 all six panels
  (fees 500/600/500/450/800/1000, seeded inclusions), six coexist and scroll,
  minimize/restore, × clears card state, Escape closes newest, mid-close race
  reopens once. Temp server stopped; :5001 untouched.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py`.
2. Open the landing page → **What we offer**: click Checkup and Grooming; both
   panels stay in the bottom-right dock. Press minus on one, click its header
   to restore, press × to close the other, then Escape to close the last.
3. Edit a fee on **Services** and confirm the popup shows the new amount.
4. Then continue the dashboard clean-up/flow pass the user planned.
5. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18i — fixed service fees + queue→consultation handoff)
- **`services` table** (11th table) seeded with six fixed services, fees and
  inclusions (General Checkup ₱500, Vaccination ₱600, Grooming ₱500, Boarding
  ₱450/night, Surgery Consult ₱800, Emergency ₱1,000). `consultations.service_id`
  added by the idempotent upgrade and applied to the live DB.
- **Services page** (`/admin/services`, Billing group): KPI row, search +
  availability funnel, table with fee/duration/inclusions/status. Admin edits
  fee, duration, inclusions and bookability with **own-password** re-check;
  name is read-only and services cannot be added/deleted. Staff view-only.
- **Queue done → consultation**: `_set_queue_status` redirects to
  `/admin/consultations?log=<appointment_id>`. The modal auto-opens with the
  appointment, its vet, the service named in the booking reason, the fixed fee
  and inclusions; diagnosis gets focus.
- **Billing is server-derived**: consultation POST takes `service_id`, reads
  `services.fee`, stores `service_id`, and issues the unpaid invoice itself.
  The editable `bill_amount` input is gone. Zero fee = no invoice.
- **Live fee display** everywhere: landing popular cards + booking select,
  New Appointment service dropdown, consultation select fee/inclusions,
  consultations list Service column, detail page service + fee.
- Verified: py_compile; test client queue→modal→consult→invoice ₱500→completed,
  fake amount ignored, wrong/right service-edit password, Staff view/edit
  bounce; browser :5002 Services page + prefilled modal. Temp rows cleaned,
  seeded fees restored, temp server stopped.
- Static: `clinic.css ?v=20261118f`.
- **User's :5001 server still runs the old build** — restart to see changes.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py`.
2. Queue → press **check (done)** on a ticket: the consultation modal should
   open with appointment/vet/service/fee filled — finish and save; the
   invoice appears unpaid.
3. Sidebar → **Services**: try editing a fee with the wrong password (blocked)
   and the right one (applies). Check the new fee on landing/booking.
4. Then continue the dashboard clean-up/flow pass the user planned.
5. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18h — admin own-password gate)
- **`verify_admin_password()`**: reads `admin_password` from the POST, checks
  it with bcrypt against the signed-in user's hash, fails closed (blank,
  non-admin session, DB error, corrupt hash). CPSC Inventory's confirm-gate
  pattern, adapted.
- **Protected admin actions** (password required): approve/reject booking,
  mark invoice paid/cancel, approve/reject account, delete account,
  activate/deactivate vet, delete queue ticket. Routine staff actions
  (serve/done/skip, consultations, client/pet edits, own profile) stay open.
- **UI**: shared decision modal gained an optional password field, shown only
  for `data-confirm-password="required"` forms. Blank confirm is blocked
  client-side; eye toggle; typed value becomes a hidden `admin_password`
  field. `i-eye` sprite added. `vet-modals.css/js ?v=20261118c`.
- Verified: py_compile + node --check; test client 6/6 routes reject blank and
  wrong, accept right, Staff bounced; every page renders the marked form.
  Browser :5002 confirmed modal flow, wrong-password flash with unchanged row
  count, eye toggle, and skip modal staying password-free. Temp server stopped.
- **User's :5001 server still runs the old build** — restart to see changes.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py`.
2. As Admin, try approving a booking / deleting a queue ticket; the card asks
   for the password (`123` on the demo seed). Wrong password changes nothing.
3. As Staff, confirm those buttons are absent and the routes bounce.
4. Then continue the dashboard clean-up/flow pass the user planned.
5. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18g — queue automation + clearer actions)
- **Auto-queue**: `_auto_queue_due()` sweeps approved appointments where
  `appointment_date=CURDATE() AND appointment_time<=CURTIME()` and creates
  tickets (one per appointment via UNIQUE `appointment_id`). Runs after
  approval and on Dashboard/Queue loads; those pages auto-refresh every 30s,
  so afternoon slots join when their time comes. Future dates wait.
- **Opt-out**: new `appointments.auto_queue` column (default 1). Deleting a
  queue ticket (Admin only) sets it to 0 so the sweeper cannot recreate it.
  Column added to `setup_db.py` + upgrade, and applied to the live DB.
- **Queue actions**: play = start serving, check = mark done, skip-forward =
  skip, X = delete ticket (Admin only). Status badges capitalized; table
  retitled "Queue Entries"; skipped KPI uses the skip icon.
- **Duplicate guard**: manual Add to Queue reports "already has a queue
  ticket" before touching the DB.
- **Popups**: `.action-bar` z-150; `clinic.js` adds `.pop-front` (z-140) to
  the card hosting an open filter panel, so funnels render over KPI/table
  cards. Header stays z-200 for the bell. `clinic.css ?v=20261118e`,
  `clinic.js ?v=20261118c`.
- Verified: `py_compile`; 14/14 test-client checks (auto-queue due vs future
  vs tomorrow, approval flash, skipped label, delete persistence, duplicate
  block, Admin-only delete); browser DOM check of queue icons and z-indexes.
- **User's :5001 server still runs the old build** — restart to see changes.
- DB note: existing today's approved bookings already queued are untouched.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py`.
2. Queue: approve a due pending booking → ticket appears; watch an afternoon
   booking join on its own (Dashboard/Queue refresh every 30s).
3. Try play/check/skip/delete; delete as Admin should stick after refresh.
4. Then continue the dashboard clean-up/flow pass the user has planned.
5. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18f — readable dates across all data tables)
- Added `pretty_date` ("August 30, 2026") and `pretty_when`
  ("August 30, 2026 | 12:00") Jinja filters in `app.py`; `pretty_when` takes
  an optional TIME value so `appointment_date` + `appointment_time` join
  cleanly. Handles date/datetime/timedelta/time/ISO strings; missing → "—".
- Applied everywhere dates render: dashboard Recent Activity, Appointments
  table + view modal, Queue, Consultations list/detail/pickers, Invoices,
  Client record visits + bills, all 8 report registers, printed receipt.
- Verification: `py_compile`; test client on every list/detail/report page
  (all 200, new format present, no ISO leftovers); browser on :5002 checked
  appointments, queue, report invoices. Fixed a shadowing bug: `datetime.time`
  was imported as `time`, clobbering the `time` module used by login throttle
  (now `clock_time`). Temp :5002 server stopped. No CSS/JS change, so no `?v=`
  bump.
- **User's :5001 server still runs the old build** — restart to see changes.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py` → check Appointments, Queue,
   Consultations, Invoices, Client record, Dashboard and Reports.
2. Then the user's planned pass: clean/enhance each dashboard and fix flows.
3. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18e — Reports section, the deferred roadmap item)
- Built the **Reports module** modeled on CPSC's reports hub, teal/clinic:
  - `/admin/reports` hub — grouped report cards (Operations, Clients & Pets,
    Finance, wide Revenue & Collections) + Record Lookup box
    (`/admin/reports/lookup` → redirects to the ledger holding the typed
    booking #, invoice #, ticket #, phone or name).
  - `/admin/reports/<kind>` registers × 8 (appointments, queue, consultations,
    invoices, clients, pets, vets, revenue): KPI row → action bar (search,
    refresh, print, funnel) → table → pager. All read-only, Admin + Staff.
  - Revenue page: monthly collections chart (6 months, zero-filled) +
    collected-vs-outstanding doughnut + bills table.
  - Print styles (`@media print` strips shell chrome). Sidebar Reports link.
  - `?v=20261118d`. Bugs fixed en route: pets register SQL (WHERE before
    FROM) and `chart.values` Jinja dict-method trap (`chart['values']`).
- Verified: py_compile; test client all 8 registers + filters + lookup +
  staff access; browser screenshots of hub, appointments report, revenue.
- **User's :5001 server still runs the old build** — restart to see Reports.

### Next Steps
1. Restart: `$env:PORT=5001; python app.py` → Sidebar → **Reports**.
2. Open each card, try the funnel (period) and the print button.
3. Record Lookup: try `Bantay`, `19`, a phone number, and a bogus value.
4. Nothing committed — commit only if the user asks.

## Last Done (2026-11-18d — bell/filter panels behind KPI cards)
- User screenshot showed the dashboard bell popup hidden behind the KPI cards.
  Cause: `.kpi-card` (backdrop-filter, hover transform) builds a stacking
  context that paints after the header, swallowing the header's absolutely
  positioned notification panel (its `z-index: 50` only competes *inside*
  the header). Fix: `.top-header { position: relative; z-index: 200; }` in
  `clinic.css` (one line; every page uses the shared header include, so this
  covers all dashboards). `?v=20261118c`.
- Browser-verified on :5002: bell panel on dashboard paints above KPI cards;
  appointments funnel panel drops above the table. Temp server stopped.

## Last Done (2026-11-18c — modals, uniform lists, per-chart filters)
- **Modal footer bug fixed everywhere**: `.vet-modal-box > form` now carries the
  column flex layout, so `.vet-modal-body` scrolls and Cancel/Save stay visible.
  The page cascade no longer animates `.vet-overlay` (fixed-position trap).
  Save buttons disable + show "Saving…" while posting.
- **Action bars unified**: search + refresh + funnel left, `.bar-spacer`,
  create button right. Queue's inline add card became a modal. Clients gained
  a Period funnel.
- **Dashboard header** now has no filter/refresh (label, clock, bell, user only).
  Each analytics card has its own funnel driven by `bk`/`qp`/`rev`/`svc`/`rec`;
  adaptive hourly/daily/monthly buckets; links preserve the other cards.
- **Tables uniform**: all `th`, `td`, action cells left-aligned; action icons
  left with right margin.
- **Surname-first names** via `person_name` filter ("Admin, System") in the
  header block and Users list; role pill unchanged.
- Static `?v=20261118b`. Browser-verified on :5002 (all modals' footers visible,
  modal saves work, per-chart filter URL/dataset isolation, left alignment,
  surname display). Test appointment/queue rows cleaned; `py_compile` clean.
- **User's :5001 server still runs the old build** — restart it to see changes.

### Next Steps
1. Restart the live server: `$env:PORT=5001; python app.py` → log in → open New
   Appointment, Add to Queue, Log Consultation, Issue Invoice and confirm the
   Cancel/Save footer is visible.
2. On the dashboard, use each card's funnel (e.g. Bookings → Today) and confirm
   only that card changes.
3. Reports dashboard remains deferred (last roadmap item).
4. Do not commit/push unless the user asks.

## Last Done (2026-11-18 — simpler scope, Settings/photos, staff walk-ins)
- User confirmed the simplified clinic flow: guest booking → approve → queue →
  consult → invoice/receipt. **Inventory is retired from the UI** (routes,
  templates, sidebar, dashboard KPI, bell low-stock, consultation stock picker).
  The MySQL `inventory` table is kept only for legacy prescription names.
- New **Settings** page: own profile + password + profile photo upload, and
  **Vet Profiles** with photos. CPSC-style glass cards, circular photo preview,
  `vet-overlay` edit modals, admin-only vet writes. Uploads: magic-byte format
  check, 3 MB cap, random filenames, `static/uploads/{avatars,vets}`.
- New **Appointment** button (Admin + Staff) books walk-ins/phone clients with
  auto client/pet and optional queue ticket; saved approved + `source='walkin'`.
- Queue add is now Admin + Staff. Prescriptions are free text.
- DB upgraded in place (idempotent): `users.avatar`, vets
  `email/license_no/bio/photo`, prescriptions `medicine_name`.
- Docs updated: guide.html, GUIDE.md, AGENTS.md, README, CHANGELOG.
- Verified with the Flask test client: 37/37 checks, test data + uploaded test
  files cleaned up. **Not yet checked in a real browser** — next step is a
  visual pass on :5001 (Settings page + New Appointment modal).

### Next Steps
1. Visual check in the browser (`$env:PORT=5001; python app.py` → login →
   Settings, upload a photo, open New Appointment). Adjust spacing if needed.
2. Reports dashboard is still deferred (last item on the roadmap).
3. Optional: drop the legacy `inventory` table in a future schema cleanup.

## Last Done (2026-11-17b — session hardening, sidebar fix, English guide)
- Sessions are tied to the running process (`RUN_ID` + `session["_run"]`); a
  restart drops old cookies, so `/` always shows the landing page and
  `/admin/*` bounces to `/?auth=open`. `_session_user_ok()` also re-reads
  `users.status`/`users.role` every guarded request (deleted/rejected users are
  kicked out, role changes apply at once; DB outage keeps the session).
- Sidebar horizontal scrollbar gone: `.snav { overflow-x: hidden }` (the 3px
  hover slide was overflowing the rail). `sidebar.css?v=20261117b`.
- `/admin/guide` + `GUIDE.md` rewritten in plain English; sidebar label
  "Giya" → "Guide". Verified 200, zero Cebuano strings.
- Verified in browser on :5002: restart → dashboard 302 to `/?auth=open`,
  landing shows Login and no Dashboard shortcut; `.snav` 218/218 px.
- Pending decision (user's call): drop Inventory for a simpler clinic scope
  and add Settings (own profile + vet profiles) + staff-created walk-in
  appointments. User asked for a recommendation before building.

## Last Done (2026-11-17 — corrections + CPSC look, teal kept, no backdrop photo)
- Phase 1 correctness: row-existence checks before every status/toggle UPDATE
  (MariaDB returns 0 affected rows on a no-op, so "not found" was lying);
  appointment KPIs completed (Total/Pending/Approved/Completed/Cancelled);
  all-time KPI totals where a period filter shouldn't apply; PH mobile rule
  (starts `09`, 11 digits) shared by guest booking + client edit; pet age/weight
  range + numeric checks; single-query bell; dead `/register` stub, duplicate
  import, `style.css`, and a stale `main.js` line removed.
- Phase 2: server-side pagination on the 9 list pages (`paginated()` +
  `_pager.html`, 20/page, out-of-range clamps). Global flash toasts replace
  per-page alert strips. Visual pass on design system: frosted panels over a
  teal gradient (CSS only — **no photo background**), KPI hover lifts, animated
  filter panels, sticky table headers, styled pager, sidebar hover/active glow,
  blurred modal backdrop; landing emoji → sprite icons. `?v=20261117a`.
- Verified: `py_compile` clean; test client 9/9 list pages 200 for both roles,
  Staff `/admin/users` 302, `page=99` clamps; browser on a :5002 verification
  instance — teal gradient shell, `rgba(255,255,255,.86)` cards, sticky thead,
  5 KPI cards, no alert strips, landing 0 emoji / 9 sprite icons, danger toast
  appears then auto-dismisses. Pixel-level screenshots unavailable (browser
  viewport reported 0x0), so visual judgement is the user's next step.
- Only photo background left in `static/css`: `landing.css:96` — the **public
  landing login curtain** (pre-existing design, not the admin system). Left
  untouched; remove if the user asks.

## Last Done (2026-10-30 — plain-language Giya)
- New `/admin/guide` page (sidebar → **Help → Giya**) for Admin + Staff,
  `login_required`, zero SQL: Cebuano-first walkthrough so anyone (Cetrin)
  can operate and demo the system — "unsa ni", 5-step patient flow, 10 module
  cards with steps, role matrix, glossary, start commands, pitfalls,
  5-minute demo script.
- `GUIDE.md` added at repo root as the printable/shareable twin.
- Sprite gained `i-book`; `clinic.css` gained `.guide-*` styles
  (`?v=20261030b` in `admin/base.html`).
- Verified via test client (MySQL off by design): anon 302 → `/?auth=open`,
  Admin 200, Staff 200, sidebar link present both roles, CSS version serves
  the guide rules; `py_compile` clean.

## Last Done (2026-10-30 — XAMPP/MySQL repair, no app code touched)
- Diagnosed "MySQL shutdown unexpectedly": `mysqld.dmp` said `[FATAL] InnoDB:
  Aborting because of a corrupt database page`; redo log LSN was behind
  `ibdata1`; the `mysql` Aria/MyISAM system tables were flagged crashed with
  broken index headers (`Index for table '.\mysql\db' is corrupt`, repair
  impossible). Symptom chain: corruption → mysqld aborts at startup → XAMPP
  shows "shutdown unexpectedly"; a hung/zombie mysqld then blocks the next
  start ("ibdata1 must be writable").
- Rebuilt `C:\xampp\mysql\data` with `mysql_install_db.exe` and restored every
  user DB from a logical dump (petclinic, cpsc_inventory, cpsc_inventory_db,
  eavs_homestay, production_inventory_db, sa_attendance_db, phpmyadmin, test).
  `pma` control user recreated; row counts verified identical.
- `C:\xampp\mysql\bin\my.ini`: `innodb_use_native_aio=0` (was throwing
  `'aio write' returned OS error 206` on `ib_logfile0`) and buffer-pool
  dump/reload disabled (stale page IDs aborted or hung startup).
- Verified: install → cycles → grant → import all left `mysql.db` healthy;
  5 clean start/stop cycles; `mysqlcheck --all-databases` OK; disk write
  integrity (sequential + random-offset + flush) 0 bad blocks; Flask app
  login `Admin`/`123` and all 10 admin pages 200 on the restored DB.
- Backups: `C:\xampp\mysql\data-BAK-2026-10-30-1835` (broken dir, pre-repair),
  `C:\xampp\mysql\backup\userdb-dump-2026-10-30-1839.sql` (all user DBs).
- Follow-up (same day): a later start hung right after `Server socket created on
  IP: '::'` and clients got `ERROR 2013 ... at 'handshake: reading initial
  communication packet'`. Cause: `mysql/proxies_priv` had been left with a
  corrupt index by an earlier force-killed mysqld (`aria_chk -c
  mysql\proxies_priv` → `Index is corrupted` / `doesn't have a correct index
  definition`, so it could not be repaired offline). Fixed by replacing
  `proxies_priv.frm/.MAD/.MAI` from a throwaway `mysql_install_db.exe` datadir;
  mysqld then logged `Zerofilling moved table: '.\mysql\proxies_priv'` and
  `ready for connections` immediately.
- Final state verified: `mysqlcheck --all-databases --check` → every table OK,
  petclinic row counts unchanged (clients 7, pets 8, appointments 8, queue 5,
  consultations 5, invoices 5, inventory 4, prescriptions_treatments 4, vets 3,
  users 2), `pma@localhost` present, `uq_queue_day_number` intact; Flask
  `GET /` 200 → `POST /login` (`Admin`/`123`) 302 → all 11 `/admin/*` pages 200
  (dashboard 22785 B); cold start ready in ~1 s. **MySQL was left stopped**
  (clean shutdown, no stale `mysql.pid`) — start it from the XAMPP Control Panel
  or `C:\xampp\mysql_start.bat`.

## Last Done (2026-10-30 — security + data-integrity pass)
- Fixed the live `/admin/vets` 500 (`VET_STATUSES` was never defined; reproduced
  via test client). Constant added and the status dropdown now uses it.
- Removed the half-wired walk-in surface: `admin_walkin()` route and
  `templates/admin/walkin.html` deleted (nav never linked it); README/AGENTS/
  SESSION claims corrected.
- CSRF: session token + `before_request` guard (400 on missing/mismatched) on
  every non-GET; `_csrf` hidden input added to all 27 POST forms; Logout is a
  POST form.
- Config/security: `PETCLINIC_*` env vars for DB + secret, cookie flags
  (HttpOnly, SameSite=Lax, Secure opt-in), 12h permanent sessions, debug opt-in,
  default port 5001, login throttle (5 failures / 5 min per IP+username).
- New accounts require 8+ characters; seeded Admin/Staff stay `123` (demo-only).
- Transactions (`tx()`) around guest booking, consultation + auto-bill,
  prescription + stock, and queue numbering. Queue gained a per-day unique
  ticket index (live DB migrated). Guest booking no longer renames clients and
  reuses pets. Invoice references must belong to the selected client.
  Referenced inventory items cannot be deleted. Pet age/weight keep 0 values.
  DB-down render paths completed.
- Verified 33/33 on a disposable `petclinic_test` DB (all GET routes, CSRF 400,
  booking dedupe, approve → queue → consult → rx → paid → receipt, staff
  restrictions, invoice-ref rejection, throttle, queue index). Test DB dropped;
  the demo DB only gained the queue index.

## Last Done (2026-10-30 — login curtain copy cleanup)
- Cleaned up the login curtain modal in `templates/landing.html`:
  - Filtered out the "Booking received!" success flash message so it only appears on the main landing page booking feedback area rather than inside the curtain.
  - Updated the subtitle text from "Login to book visits and manage your pets." to "Admin and Staff portal login." (clarifying that clients do not log in).
  - Removed the redundant "Staff? Use your assigned username." prompt and replaced the footer note with "Admin & Staff login only."
- Verified syntax with `py_compile`.
- Fixed the landing page "Book Now" button alignment: added a matching hidden label row above the submit button so it lines up perfectly with Date and Time inputs.
- Removed the dynamic phone helper text (`gPhoneHelp`) since phone inputs natively format cleanly as `09XXXXXXXXX`.
- Added a robust server-side guard in `book_guest()` (`app.py`) ensuring phone numbers start with `09` and are exactly 11 digits, flashing a clear reminder if invalid.
- Verified syntax with `py_compile`.
- `/` no longer redirects a logged-in user to the dashboard: the landing page is
  always the entry point (`signed_in` flag swaps the Login button for a
  Dashboard shortcut). Login/logout redirects unchanged.
- Animation flash fixed: cascade unveil is CSS-only (`main.content.cascade > *`
  + `nth-child` delays, `animation-fill-mode: both`) so it applies at first
  paint. Removed the JS stagger (it added classes after paint = flash) and the
  `@view-transition` opt-in (competed with the cascade). Faster: 0.4s/block,
  0.045s step. `clinic.css`/`clinic.js?v=20261030`.
- Verified 27/27 via Flask test client (landing-first for guests + both roles,
  11 admin pages + Staff dashboard on the new CSS/JS versions, CSS/JS contents).

## Last Done (2026-10-29 — sidebar responsiveness)
- Fixed the nav rail: `position: fixed` viewport-height sidebar (top:0; bottom:0),
  Logout pinned visible via flex:none footer, nav links scroll internally only,
  link/label spacing tightened so the whole menu fits at 100% zoom. `.main`
  offset 264px (0 at mobile breakpoint); `sidebar.css?v=20261029` cache-bust.
- Verified: 11 admin pages + Staff dashboard render 200 with the new CSS version;
  test server stopped, no orphan processes.

## Last Done (2026-10-02 — CPSC modals)
- Hand-rolled popup system live on all popups (droplet, fx21, Cancel/Save,
  locked backdrop, shared decision shell); native confirms + Bootstrap JS gone.
- Verified shells on 6 pages, decision approve flow, test rows cleaned.
- Ported CPSC cascade-unveil + view-transition morph (sidebar frozen, content
  glides on sidebar clicks); skeleton keeps fresh-login arrivals; reduced-motion
  respected. Also rewrote clinic.js cleanly after accumulated structure damage.
- Bold teal headers back, light strip back; doughnut renders gray "No queue
  today" ring on empty days (was blank — today has zero queue rows).
- Shimmer overlay mimicking the shell plays ~1.2s on fresh login only
  (`?welcome=1`); verified show/hide for both roles + fade JS present.
- Cleaned up 5 orphaned smoke-test servers squatting on :5001 (lesson: always
  stop test servers; they masked real results twice).
- Reverted the header/strip color swap per user call; charts fill cards
  (aspect lock off, thicker bars, centered pie); Revenue ↔ Top Services swapped.
- Page headers take the bold teal gradient (white text/avatar/pill); strip takes
  the light card style; analytics grid 70/30; toggle restyled for light strip.
  Verified all shells render.
- Dashboard charts wired to real data (adaptive buckets, zero-filled; verified
  against DB counts), Now-Serving strip + next-2 below KPIs, 30s auto-refresh
  with own toggle key. Staff sees strip + charts.
- `users.status` migration live (existing approved); login gates on status.
- Users page on concept: 5 KPIs, Period/Status funnel, Create modal,
  approve/reject icons. Verified full lifecycle; test user cleaned.
- Invoices on page concept (Period/Status funnel, Issue modal, print icons,
  full-height table); consult amount auto-issues linked unpaid bill; receipt
  view with PAID stamp. Verified auto-bill + receipt; test rows cleaned.
- Fixed Items KPI rendering raw dict method text (key collision, renamed).
- Inventory now follows page concept: funnel (Period + Category), Add Item modal,
  full-width table. Verified count, modal, funnel, Staff view.
- Pets funnel (Period + Species folded in); walk-in is now a history page
  (Total/Today KPIs, search, Period/Status funnel, queue numbers, modal create).
- `appointments.source` migration live (guest/walkin stamped; old rows = guest).
- Verified: modal walk-in, history search, species filter; test rows cleaned.
- Bar regrouped (funnel beside Log button), Log is now an in-page modal with
  Cancel/Save, search-box stretch fixed globally. Verified modal save E2E.
- Regrouped bar (search/refresh/funnel left, Log right), Period + Prescription
  funnel, full-height table. Verified markup + rx filter select.
- Queue is dashboard-like: Now-Serving strip + next-2 chips, 30s auto-refresh
  with pause toggle, Period+Status funnel, full-height table. Verified markup,
  filter select, staff view.
- Slim list headers (bell-only); funnel+refresh moved beside Search; combined
  Period+Status funnel panel on appointments (standalone status dropdown gone).
- Roomier tables (padding, viewport-fill card, responsive scroll); fixed a
  clinic.js brace bug that would have broken all panel toggles.
- CPSC list-page law live on all 8 list pages: KPI row → action bar → badge table
  with sprite icon buttons; appointments pilot verified (approve/reject/search),
  then queue/consults/inventory/invoices/clients/pets/users replicated.
- Staff view-only holds on all new buttons (queue-serve icons intentionally
  staff-visible). Standing docs rule kept: CHANGELOG/README/AGENTS/SESSION updated.
- Root cause of narrow pages found (my code, not browser): `.container py-4`
  wrapper on all list/form pages. Unwrapped all 14; verified 9/9 full-width.
- Full filter cluster on every list page header; period drives all 8 lists
  (verified Today hides old rows); detail/form pages use slim header.
- Bell via context processor everywhere admin-side; queue table shows dates.
- Deleted owner-login surface (5 routes, `templates/client/`); owners are record
  rows only. New: Clients list+profile (search, staff-editable), Pets registry
  (filter, edit), Walk-in form (approved visit + optional queue).
- Nav: Operations gains Clients, Pets, Walk-in. Verified: record flows for both
  roles, guest booking green, test rows cleaned.
- Shared header includes on all 13 pages (`admin/_page_header.html` with bell via
  `inject_bell` processor; `client/_page_header.html` without); dashboard refactored
  onto the include; clinic.js clock handles class-based clocks.
- Sidebar: USERS group fully hidden for Staff, trailing group-label lines, logo +
  logout dividers, `?v=` cache-bust everywhere (kills stale-CSS ghosts like the
  appointments screenshot).
- Verified: 8/8 admin + 4/4 client headers, Staff bell + no Users, view-only holds.
- Vet-as-user deleted (6 routes, `templates/vet/` gone; vet = record-only name);
  consultations now `/admin/*` shared (Admin+Staff), queue-serve opened to Staff.
- Pending Approvals card off dashboard (ledger-only approvals); profile block off
  all sidebars; client converted to sidebar+header+KPI shell (`client/base.html`).
- Verified: 8/8 admin + 4/4 client pages in shells, vet URLs 404, Staff view-only
  holds, guest booking green.
- Admin dashboard rebuilt in CPSC pattern: header (label, live clock, period
  filter, refresh, live-count bell, user block), 5 SVG KPI cards, 4 Chart.js
  analytics frames (empty), period-driven KPIs/activity, grouped sidebar nav.
- New `clinic.css`/`clinic.js`, sprite +8 symbols (CPSC geometry). AGENTS.md rule 7+8
  (header law, sprite-only icons). Verified all markup + filter + staff view-only.
- `staff` is now a real ENUM role (setup_db.py + live ALTER); Staff lands on the
  shared admin dashboard, keeps vet Queue/Consultations; Users page Admin-only.
- Shared view: Pending Approvals card (Approve/Decline Admin-only), all list pages
  readable by Staff, every mutation Admin-only server-side + hidden buttons,
  view-only banner, Users hidden from Staff sidebar.
- Verified: Staff sees data w/ zero actions (Users bounce, direct POST bounce);
  Admin full powers intact; Staff vet pages intact.
- Left sidebar on Admin + Vet (screenshot pattern, vet-teal): logo, initial-avatar
  profile, teal active pill, pinned Logout, mobile drawer; shared base templates,
  11 pages converted (top navbars gone); SVG sprite icons, zero emoji in admin/vet.
- New `/admin/appointments` ledger (filter + inline setter, returns to ledger).
- Verified: all 6 admin + 3 vet pages render in shell, active pills correct,
  ledger filter works. (Also fixed a self-made IndentationError on the way.)
- Login UX fixed (Enter→password focus, readonly stripped on submit; no-save kept).
- Public registration removed (curtain link, `/register` bounce, template deleted).
- Guest booking live: `POST /book-guest` auto-creates owner (phone dedupe) + pet,
  `pending` + ref# confirm; verified new + repeat-phone + past-date block.
- Admin Users page live (create admin/vet/owner, self/last-admin guards);
  verified create → vet login. Test rows cleaned (Admin/Staff only).
- Consolidated docs for next session: CHANGELOG Unreleased restructured (was fragmented),
  README gained Design Language + current Security Notes, AGENTS.md route map + rules
  updated (curtain-only login, port 5001, no-hash-through-PowerShell rule).
- Verified `py_compile` clean across `app.py`, `config.py`, `database/setup_db.py`.
- [2026-10-08 — offline + checking readiness] Vendored Bootstrap CSS/bundle JS +
  Chart.js into `static/vendor/` (4 CDN tags swapped: landing, admin shell,
  receipt, dashboard); dashboard chart guard confirmed offline-safe.
- [2026-10-08] New `database/demo_seed.py` (inline creds, no import-path trap):
  injected Maria/Juan ledger (pending guest + queued walk-in + paid history,
  4 stock items); stray `Tambal` row removed.
- [2026-10-08] 33/33 offline E2E smoke via Flask test client: guest booking →
  approve → queue → serve → consult + P500 auto-bill → Rx stock 5→3 → paid →
  receipt; all 10 admin pages 200 with zero `cdn.jsdelivr` refs; vendor files
  200; Staff approve blocked, serve allowed. Smoke rows cleaned, demo intact.
- [2026-10-09 — clients/vets split] `users` is logins-only (`admin`/`staff`);
  new `clients` table (phone-dedupe, address) + `vets` directory (specialty,
  active toggle); `owner_id`→`client_id` everywhere; consults take an
  attending vet (active-only dropdown) and backfill appointment + queue.
- [2026-10-09] New `/admin/vets` list page (sidebar nav, 4 KPIs, funnel, Add
  Vet modal, activate/deactivate; Staff read-only) per list-page law.
- [2026-10-09] Live migration ran clean (`migrate_clients_vets.py`): Maria/Juan
  → clients with history intact, legacy consult → Duty Vet; 52/52 E2E on the
  new schema (incl. vet-required/inactive-reject, Staff-add blocked).

## Current State
- Stack: Flask + PyMySQL + bcrypt + Jinja2 + hand-rolled CSS/JS + MySQL (XAMPP, `petclinic`).
- Public `/` landing; login ONLY via `#loginCurtain`. Logins: `Admin`/`Staff`
  (pw `123`) — `users` holds logins only. Clients + vets are record tables.
- Demo ledger live: clients Maria Santos + Juan Dela Cruz (3 pets, pending
  guest Bantay, queued walk-in Mingming #1, paid P850 Tweety history w/ Dra.
  Ana Reyes); vets directory: Duty Veterinarian + Ana Reyes + Mark Villanueva.
  Rebuild: `python database/setup_db.py` then `python database/demo_seed.py`.
- Fully offline-capable: Bootstrap + Chart.js vendored in `static/vendor/`.
- Modules live: pet CRUD, booking + prefill, queue (admin/vet), consultations +
  free-text prescriptions, fixed **Services** price list (fees + inclusions),
  invoices + client pay. Inventory is retired from the UI (the table stays for
  legacy prescription names).
  In-app plain-language manual at `/admin/guide` (Help → Guide; Admin + Staff,
  DB-free) with the printable twin `GUIDE.md`.
  There is **no walk-in page** (removed 2026-10-30; `source='walkin'` rows from
  past data still display in the appointment ledger).
- Security: CSRF on all POSTs, 12h sessions, login throttle, 8+ password policy
  for new accounts, env-driven config. `logout` is POST-only.
- DB source: `database/setup_db.py` (guarded, idempotent, runtime bcrypt seeds;
  also adds the queue per-day unique index).
- Standard run: `python app.py` → `http://127.0.0.1:5001/`
  (`PORT` overrides; `FLASK_DEBUG=1` is opt-in).
- Live DB verified matching schema (incl. `uq_queue_day_number`); test rows
  cleaned after each E2E.

## Next Steps (CHECKING DAY — run order)
1. Start XAMPP MySQL → `$env:PORT=5001; python app.py` → `http://127.0.0.1:5001/`
   (WiFi can stay OFF). Login `Admin` / `123` via curtain.
2. Live path: approve Bantay (Appointments) → Queue add/serve → Consultations
   Log + attending vet + bill → Rx (Syringe) → Invoices receipt → paid.
3. Show Vets page (directory + Add Vet modal + deactivate), then Staff limits:
   login `Staff` — queue-serve + consults work, approve/add/toggles blocked.
4. If ledger gets messy mid-demo: re-run `python database/demo_seed.py` (2 min
   rebuild, Admin/Staff untouched).
5. Do NOT create `vet`-role users (dead login — dashboard guard is admin/staff
   only); new users enter `pending` and need approval before they can log in.
1. Landing polish: confirm real clinic name/fees/address/phone/email/hours
   (current values are placeholders); remap new pet photos as supplied.
2. Booking flow review: landing bar → curtain → prefilled form; confirm copy + validation UX.
3. Admin CPSC port (direction locked): cream sidebar + sky topbar, hand-written CSS,
   body-level modals, toasts, filter panels; drop Bootstrap on admin pages.
4. Blueprint split for `app.py` (~1100 lines): propose `auth/client/admin/vet` blueprints.
5. Re-verify full E2E after each change; keep CHANGELOG + this file updated.

## Blockers / Notes
- MySQL data dir was rebuilt on 2026-10-30 (see Last Done). Never start a
  second `mysqld`: stop MySQL with XAMPP's **Stop** or
  `C:\xampp\mysql\bin\mysqladmin.exe -u root shutdown`. Force-killing mysqld
  leaves Aria/InnoDB files flagged crashed and the next start aborts
  ("corrupt database page" / "Index for table '.\mysql\db' is corrupt") —
  that is exactly what broke MySQL before this repair.
- Force-killing mysqld also corrupts `mysql.proxies_priv`, and that one does
  **not** abort — it hangs the server silently right after `Server socket
  created on IP: '::'`, with clients failing on the handshake. If a start ever
  hangs there: check `aria_chk -c mysql\proxies_priv` from
  `C:\xampp\mysql\data` (server stopped), then copy
  `proxies_priv.frm/.MAD/.MAI` over from a throwaway
  `mysql_install_db.exe --datadir=<temp>` and start again.
- `mysql_error.log` can look truncated: when mysqld is launched without its
  stdio redirected, post-socket startup lines go to the console and never reach
  the log — a healthy server can look "stuck" at `Server socket created`.
  Confirm with `mysqladmin -u root ping`, never with the log tail.
- If MySQL ever aborts at startup again: restore from
  `C:\xampp\mysql\backup\userdb-dump-2026-10-30-1839.sql` after
  `mysql_install_db.exe --datadir=C:\xampp\mysql\data` (3 min; user DBs only,
  `mysql` schema is rebuilt). Pre-repair copy:
  `C:\xampp\mysql\data-BAK-2026-10-30-1835`.
- `my.ini` intentional tweaks: `innodb_use_native_aio=0` and buffer-pool
  dump/reload off. Do not re-enable without a soak test.
- Usernames are case-sensitive (`Admin` ≠ `admin`).
- Port 5000 belongs to the IM 103 project; app now defaults to 5001.
- Never pass bcrypt hashes through PowerShell double-quoted strings.
- Login throttling is in-memory and per process (resets on restart); the seeded
  `123` passwords are demo-only. Set `PETCLINIC_SECRET_KEY` outside this machine.
- Any scripted POST must fetch a page first and send its `_csrf` token.
- `System Requirements/` docs untouched. Never commit/push unless asked.
