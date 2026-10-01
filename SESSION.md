# SESSION.md — AI Continuity Log (read this every new session)

## Last Done (2026-10-01 — chart fill + swap revert)
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

## Current State
- Stack: Flask + PyMySQL + bcrypt + Jinja2 + Bootstrap 5 CDN + MySQL (XAMPP, `petclinic`).
- Public `/` landing (EAVS Telly, vet teal); login ONLY via `#loginCurtain`
  (username + password, `?auth=open|failed` flows, Cancel/Confirm error popup).
- Seeds: `Admin` (admin) + `Staff` (vet role), pw `123`. No owner seed — register via curtain.
- Modules live: pet CRUD, booking + prefill, queue (admin/vet), consultations +
  prescriptions w/ stock deduction, inventory CRUD, invoices + client pay.
- DB source: `database/setup_db.py` (guarded, idempotent, runtime bcrypt seeds).
- Standard run: `$env:PORT=5001; python app.py` → `http://127.0.0.1:5001/`.
- Live DB verified matching schema; test rows cleaned after each E2E.

## Next Steps (next session: refine design + process flow)
1. Landing polish: confirm real clinic name/fees/address/phone/email/hours
   (current values are placeholders); remap new pet photos as supplied.
2. Booking flow review: landing bar → curtain → prefilled form; confirm copy + validation UX.
3. Admin CPSC port (direction locked): cream sidebar + sky topbar, hand-written CSS,
   body-level modals, toasts, filter panels; drop Bootstrap on admin pages.
4. Blueprint split for `app.py` (~1100 lines): propose `auth/client/admin/vet` blueprints.
5. Re-verify full E2E after each change; keep CHANGELOG + this file updated.

## Blockers / Notes
- Usernames are case-sensitive (`Admin` ≠ `admin`).
- Port 5000 belongs to the IM 103 project; never use it here.
- Never pass bcrypt hashes through PowerShell double-quoted strings.
- `System Requirements/` docs untouched. Never commit/push unless asked.
