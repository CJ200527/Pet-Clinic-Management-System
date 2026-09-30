# SESSION.md — AI Continuity Log (read this every new session)

## Last Done (2026-09-30 — shared dashboard)
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
