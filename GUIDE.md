# User Guide — Pet Clinic Management System

**For Cetrin Valduhueza (and anyone doing the demo).**
Read it from top to bottom — no coding knowledge needed.
The same guide is inside the app: sidebar → **Help → Guide** (`/admin/guide`).

---

## 1. What is this?

The **Paws & Care Pet Clinic Management System** runs the clinic's day online:

| Role | What they can do | Login? |
|---|---|---|
| **Client** (pet owner) | Just books on the landing page | ❌ no login |
| **Staff** | Runs the day: queue, consultations, edit records; can view everything | ✅ |
| **Admin** | Everything, including approve / add / delete / users | ✅ |
| **Vet** | A directory record only (not an account) | ❌ |

**Demo accounts** (username is case-sensitive, password `123`): `Admin`, `Staff`.

---

## 2. Starting the app

1. Open **XAMPP** → **Start MySQL** (Apache is not needed).
2. In the terminal, inside the project folder:
   ```powershell
   $env:PORT=5001
   python app.py
   ```
3. Open the browser at `http://127.0.0.1:5001/`
4. Press **Login** on the landing page → the **curtain** rolls down →
   type the username + password → **Sign in**.

> Port **5001** is the standard. Port 5000 belongs to another project (IM 103).
> If the demo data gets messy: `python database/demo_seed.py` (≈2 min,
> the Admin/Staff accounts are untouched).
>
> Every time `python app.py` is started, anyone who was logged in is signed out
> on purpose. The landing page is always the first screen.

---

## 3. The life of one patient

```
[Client books on /]  →  [Admin approves]  →  [Queue number]  →  [Consult + bill]  →  [Pay + receipt]
```

1. **Book** — the guest fills in the booking bar on the landing page (name, phone,
   pet, date, time, service). A new client + pet is created automatically.
   The booking arrives as **pending**.
2. **Approve** — Appointments page → **✔** (accept) or **✕** (decline). Admin only.
3. **Queue** — the patient gets a turn number for the day.
4. **Consult** — the vet records the service, diagnosis, treatment and
   prescription. The service's fixed fee becomes the bill.
5. **Pay** — the fixed fee creates an **unpaid invoice** automatically.
   Mark it **paid** → a receipt with a **PAID** stamp appears → print it.

---

## 4. The modules

### Dashboard (`/admin/dashboard`)
- The **Period** filter (Today / This Week / This Month / All Time) changes every
  number on the page.
- **Refresh** reloads the data; the **bell** counts pending bookings
  and unpaid bills.
- 4 KPI cards (click one to open its list) + 4 charts
  (Revenue, Top Services, Bookings trend, Species).

### Appointments (`/admin/appointments`)
- Every booking is listed here (guest bookings and walk-in rows).
- **New Appointment** (Staff or Admin) books a walk-in or phone client.
  Pick an existing client or type a new owner + phone, then pick or create the
  pet. It saves as **approved** and can be queued in the same step.
- **✔ approve**, **✕ reject** (Admin) for guest bookings.
- Search + funnel (Period / Status) sit in the action bar.

### Queue (`/admin/queue`)
- **Add to Queue** (Staff or Admin) gives a number; numbering is per day.
- **Now-Serving** strip + the next two patients.
- The serve / complete icon (Admin + Staff). **Complete (check)** jumps straight
  to the consultation form with the appointment, vet and service prefilled.
- Auto-refresh every 30 seconds (with a pause toggle).

### Consultations (`/admin/consultations`)
- **Log Consultation** → appointment + pet + **service** + **attending vet**
  (active only). The service from the booking is preselected and shows its
  fixed fee + inclusions.
- Diagnosis, treatment, notes.
- Saving completes the appointment and creates an **unpaid invoice** for the
  fixed service fee (zero fee = no invoice).
- Detail page → add a **prescription** as plain text (medicine, dosage,
  instructions). No stock numbers to maintain.

### Services (`/admin/services`)
- Six fixed services, each with a **fixed fee**, duration and **inclusions**.
- Admin edits fee / duration / inclusions / bookability via the pencil; it
  asks for the admin password. Changes apply to future consultations only.
- Services cannot be added or deleted; uncheck **Bookable** to hide one.
- Staff can view the price list but not edit it.

### Clients (`/admin/clients`)
- Search by name or phone; **view** shows the profile + pets + history.
- **Edit** the contact and address (Admin + Staff).
- Guest booking de-duplicates by phone: same phone = same client.

### Pets (`/admin/pets`)
- Search / filter by species; **view / edit** (name, species, breed, age,
  weight, notes). Every pet is linked to its owner (client).

### Vets (`/admin/vets`)
- **Add Vet** (Admin): name, specialty, phone.
- **Deactivate** → the vet cannot be picked in the consultation dropdown
  (history stays).
- **Activate** → the vet is selectable again.
- For photos and the full profile, use **Settings → Vet Profiles**.

### Settings (`/admin/settings`)
- **My Profile**: change your name, email or password (username is fixed).
- **Photo**: pick a PNG / JPG / WEBP image (up to 3 MB) → **Save photo**.
  It shows on the header bar and next to your name.
- **Vet Profiles** (Admin): pencil icon → photo, specialty, license, email,
  background, active toggle. **Add Vet** creates a new profile.

### Invoices (`/admin/invoices`)
- **Issue Bill** (Admin) or automatically from a consultation.
- The reference (appointment/consultation) must belong to the chosen client.
- **Mark paid** → **receipt** with a PAID stamp → **print** icon.

### Users (`/admin/users`, Admin only)
- **Create User**: username, full name, role (`admin` / `staff`), password (8+).
- A new user is **pending** → approve before they can log in.
- Reject / delete; you cannot delete yourself or the last admin.

---

## 5. Who can do what

| Action | Admin | Staff |
|---|:--:|:--:|
| View every list | ✔ | ✔ |
| Approve / reject a booking | ✔ | — |
| Add to queue, serve, complete | ✔ | ✔ |
| Log consultation + prescription | ✔ | ✔ |
| Edit client / pet records | ✔ | ✔ |
| Book a walk-in (New Appointment) | ✔ | ✔ |
| Edit my own profile + photo | ✔ | ✔ |
| Edit vet profiles + photos | ✔ | — |
| Issue an invoice / mark it paid | ✔ | — |
| Add a vet / activate / deactivate | ✔ | — |
| Manage login accounts | ✔ | — |

> Even when a button is hidden from Staff, the server blocks the forbidden
> action itself (double protection).

---

## 6. Words you will see

| Word | Meaning |
|---|---|
| **Pending** | Still waiting for approval. |
| **Approved** | Accepted, ready for the queue. |
| **Completed** | The service is finished. |
| **Cancelled / Rejected** | Dropped or not pushed through. |
| **Queue number** | The patient's turn number for today. |
| **Consult** | The check-up record. |
| **Prescription** | The medicine and instructions written by the vet. |
| **Invoice** | A bill that still has to be paid. |
| **Receipt** | Proof of payment (PAID). |
| **Period** | The date range the numbers cover. |
| **KPI** | The big numbers at the top of a page. |

---

## 7. 5-minute demo script (checking day)

1. Landing page → **Book** "Bantay" with a new phone number → confirmation
   reference. *(show the phone format: `09XXXXXXXXX`, 11 digits)*
2. **Login `Admin` / `123`** → Dashboard: period filter + bell + KPIs.
3. **Appointments** → ✔ approve the new booking.
4. **Queue** → Add to Queue (number) → serve.
5. **Consultations** → Log: service + attending vet + diagnosis → Save
   *(show the fixed-fee unpaid invoice appearing automatically)*.
6. **Detail page** → add a prescription.
7. **Invoices** → mark paid → **receipt** (PAID stamp) → print.
8. **Vets** → Add Vet modal + deactivate toggle.
9. **Logout** → **Login `Staff` / `123`** → same pages, but no
   approve/add/delete (view-only + queue/consult).

---

## 8. Common mistakes to avoid

- **Phone number:** must be `09XXXXXXXXX` (11 digits). The server rejects anything else.
- **Password:** a new account needs 8+ characters. `123` is demo-only.
- **No `vet` login:** a vet is a directory row. Do not create a `vet` user.
- **Period filter** affects every list page — if rows seem missing, they may be
  in another period.
- **Do not edit** the `database/setup_db.py` schema without a migration.
- On an error: read the terminal where `python app.py` is running.
- If the page does not load: **is MySQL running?** and **is the port 5001?**

---

## 9. Where the code lives (for anyone curious)

| File | What |
|---|---|
| `app.py` | All routes (Flask) — booking, admin, records |
| `config.py` | DB connection + SECRET_KEY (env-driven) |
| `database/setup_db.py` | Schema (10 tables) + seed accounts |
| `database/demo_seed.py` | Demo data for the checking |
| `templates/` | HTML (Jinja2): `landing.html`, `admin/*` |
| `static/css/`, `static/js/` | Design + interactions (hand-rolled, offline) |
| `templates/admin/guide.html` | This guide, inside the app (`/admin/guide`) |

---

*Last updated: 2026-11-18 — matches `/admin/guide`.*
