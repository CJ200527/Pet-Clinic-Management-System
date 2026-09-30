# AGENTS.md — AI Agent Rules (Pet Clinic, Flask)

Read `SESSION.md` at the start of every new session, then update it at the end.

## Stack (locked)
- Python **Flask** + **PyMySQL** + **bcrypt** + Jinja2 + Bootstrap 5 CDN + MySQL (XAMPP).
- Do NOT reintroduce PHP. Do NOT add Django/FastAPI/ORMs unless the user asks.

## Project Map
- `app.py` — all routes (single file, ~1100 lines — blueprint split proposed, pending):
  auth (`POST /login`; `GET /login` bounces to curtain; NO public register),
  public `/` landing + `POST /book-guest` (guest booking, auto owner/pet),
  client (owner-role routes kept for accounts admin creates), admin (`/dashboard`,
  `/appointments`, `/users` (admin-only), `/users/<id>/delete`,
  `/appointments/<id>/status` (admin-only), `/queue` (read: admin+staff),
  `/queue/<id>/status` (admin-only), `/inventory` (read: admin+staff),
  `/inventory/<id>/edit|delete` (admin-only), `/invoices` (read: admin+staff),
  `/invoices/<id>/status` (admin-only)), vet (`/dashboard`, `/queue`,
  `/queue/<id>/status`, `/consultations`, `/consultations/new`, `/consultations/<id>`).
  Roles: `admin` (full), `staff` (shared dashboard view-only + vet pages),
  `vet` (vet pages), `owner` (client pages).
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

## Session Protocol
1. Read `SESSION.md` (last-done / current-state / next-steps / blockers).
2. Do the work; run verification (`py_compile`, `pip install`, smoke test).
3. Append to `CHANGELOG.md` (Unreleased/vX.Y entry).
4. Update `SESSION.md` before finishing (no stale state).
5. Never commit/push unless explicitly asked.
