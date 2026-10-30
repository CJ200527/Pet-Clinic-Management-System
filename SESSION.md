# SESSION.md — AI Continuity Log (read this every new session)

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
  prescriptions w/ stock deduction, inventory CRUD, invoices + client pay.
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
- Usernames are case-sensitive (`Admin` ≠ `admin`).
- Port 5000 belongs to the IM 103 project; app now defaults to 5001.
- Never pass bcrypt hashes through PowerShell double-quoted strings.
- Login throttling is in-memory and per process (resets on restart); the seeded
  `123` passwords are demo-only. Set `PETCLINIC_SECRET_KEY` outside this machine.
- Any scripted POST must fetch a page first and send its `_csrf` token.
- `System Requirements/` docs untouched. Never commit/push unless asked.
