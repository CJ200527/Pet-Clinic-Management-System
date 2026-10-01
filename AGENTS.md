# AGENTS.md — AI Agent Rules (Pet Clinic, Flask)

Read `SESSION.md` at the start of every new session, then update it at the end.

## Stack (locked)
- Python **Flask** + **PyMySQL** + **bcrypt** + Jinja2 + Bootstrap 5 CDN + MySQL (XAMPP).
- Do NOT reintroduce PHP. Do NOT add Django/FastAPI/ORMs unless the user asks.

## Project Map
- `app.py` — all routes (single file — blueprint split proposed, pending):
  auth (`POST /login`; `GET /login` bounces to curtain; NO public register),
  public `/` landing + `POST /book-guest` (guest booking, auto owner/pet),
  records (`/clients`, `/clients/<id>` (staff-editable contact),
  `/pets`, `/pets/<id>/edit` (staff-editable), `/walk-in` (approved visit + queue)),
  admin (`/dashboard`, `/appointments`, `/consultations`, `/consultations/new`,
  `/consultations/<id>`, `/users` (admin-only), `/users/<id>/delete`,
  `/appointments/<id>/status` (admin-only), `/queue` (read: admin+staff; add: admin),
  `/queue/<id>/status` (admin+staff), `/inventory` (read: admin+staff; add: admin),
  `/inventory/<id>/edit|delete` (admin-only), `/invoices` (read: admin+staff;
  issue: admin), `/invoices/<id>/status` (admin-only)).
  Roles: `admin` (full), `staff` (operate + view, no approve/delete/users),
  `vet` (record-only name), `owner` (record rows only, no login surface).
- `config.py` — `get_connection()` (DictCursor, autocommit). Same XAMPP creds
  (`localhost / petclinic / root / ""`).
- `database/setup_db.py` — source of truth for schema (8 tables) + Admin/Staff
  seeds (bcrypt at runtime). Guarded by `if __name__ == "__main__"`.
  Don't change schema without updating it + CHANGELOG.
- `templates/landing.html` + `static/css/landing.css` — EAVS Telly pattern, vet palette;
  login lives ONLY in the `#loginCurtain` card (no standalone login page).
- `templates/` + `static/` — Jinja2 + Bootstrap 5 CDN (until CPSC admin port drops it).

## Coding Rules
1. Parameterized queries only (`%s` placeholders). Never format user input into SQL.
2. Passwords: `bcrypt.hashpw(pw, gensalt())` on register/seed,
   fail-closed `bcrypt.checkpw()` on login. Never pass hashes through PowerShell
   double-quoted strings (`$` gets expanded — use parameterized Python instead).
3. Every dashboard/booking route needs `login_required` / `role_required`.
   Guards bounce to the landing curtain (`/?auth=open`), never a login page.
4. Re-validate ownership server-side (e.g. pet belongs to `session user_id`).
5. Flash messages for errors/success; login failures use the `?auth=failed` popup flow.
6. Standard port is **5001** (`$env:PORT=5001`); port 5000 belongs to the IM 103 project.
7. Dashboard header law (CPSC pattern): the dashboard header holds the page label,
   a live clock beneath it, period filter, refresh, bell, and the logged-in user
   block (first name + role pill + initial avatar) at the far right.
   List-page headers are slim (label, clock, bell, user) — their filter +
   refresh live in the action bar's combined funnel panel (Period + page Status).
   Implementation: shared `_page_header.html` include (`full_header` flag only on
   the dashboard) + `inject_bell` context processor. Never hand-roll a header.
   The period filter drives every list page through `period_cond()`; detail/form
   pages use the slim header (`show_filter = False`).
8. Icons are SVG sprite symbols only (`_sprite.html`: `i-*` actions, `k-*` KPIs,
   CPSC path geometry) — never emoji in app UI.
9. Sidebar law: logo block, grouped buttons with trailing label lines, dividers
   below the logo and above Logout; USERS group renders for Admin only.
   Bump `?v=` on static links whenever CSS/JS changes (kills stale-cache ghosts).
10. List-page law (CPSC control pattern, dashboard excluded): header → KPI row
    (period-aware counts, cards link-filter the ledger) → action bar
    (search + refresh + funnel side-by-side; funnel panel holds Period + page
    Status categories; add-record button only where records originate) →
    roomy badge table (`.table-card-fill` min-height) with sprite icon buttons
    (`icon-view/edit/approve/reject/del`; Admin-only actions hidden for Staff).
    Row mutations stay server-guarded regardless of hidden buttons.

## Session Protocol
1. Read `SESSION.md` (last-done / current-state / next-steps / blockers).
2. Do the work; run verification (`py_compile`, `pip install`, smoke test).
3. Append to `CHANGELOG.md` (Unreleased/vX.Y entry).
4. Update `SESSION.md` before finishing (no stale state).
5. Never commit/push unless explicitly asked.
