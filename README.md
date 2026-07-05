# Infosys_FranciseOps_AI
# Milestone 1 — User Authentication Module

**Infosys Springboard Internship 7.0 · Batch 1**

## What this milestone is

A self-contained authentication system built with Streamlit and made
publicly reachable from Google Colab via ngrok. It covers full account
lifecycle: signup, login, password recovery, and role-based dashboards,
with all secrets kept out of the codebase.

## Features built

- **Login** — username or email + password, JWT session issued on success,
  one generic error message on failure (never reveals which field was wrong)
- **Signup** — username, email, password + confirm, security question &
  answer; duplicate usernames/emails are rejected with a clear message
- **Forgot Password** — two independent recovery routes:
  - *Security Question* — answer the question set at signup, then set a new password
  - *Email OTP* — a 6-digit code emailed via Gmail, expires after 5 minutes
- **JWT session handling** — a signed token gates access to the dashboard;
  signup and password reset always route back to Login, never auto-login
- **Field validation** — mandatory-field checks, an email-shape rule
  (letters before `@`, letters between `@` and the dot, letters after
  the dot), and a password rule (8+ chars, upper, lower, number, symbol)
- **User Dashboard** — welcome message + logout
- **Admin Dashboard** — separate hardcoded admin login; lists every
  registered user's username/email (passwords are never displayed)

## Tech stack

| Layer            | Tool                          |
|-------------------|-------------------------------|
| UI                | Streamlit                     |
| Sessions          | PyJWT                         |
| Password hashing  | bcrypt                        |
| Storage           | SQLite (`portal.db`)          |
| OTP delivery      | Gmail SMTP (App Password)     |
| Public tunneling  | ngrok (via pyngrok)           |

## Files

- `app.py` — the Streamlit app (all three auth pages + both dashboards)
- `db.py` — SQLite data layer (hashing, lookups, uniqueness checks)
- `requirements.txt` — Python dependencies

## Secrets (set in Colab Secrets, never hard-coded)

| Secret name       | Purpose                              |
|-------------------|---------------------------------------|
| `JWT_SECRET`      | Signs session & OTP tokens            |
| `NGROK_AUTHTOKEN` | Authenticates the ngrok tunnel        |
| `EMAIL_ADDRESS`   | Gmail address that sends OTP mail     |
| `EMAIL_PASSWORD`  | Gmail App Password (16 characters)    |

## How to run (Google Colab)

1. Upload `app.py` and `db.py` to the Colab runtime (or use `%%writefile`).
2. `pip install -r requirements.txt`
3. Add the four secrets above via the Colab Secrets (key icon) panel,
   with notebook access enabled for each.
4. Run the launch cell (fetches secrets, starts Streamlit, opens an
   ngrok tunnel, prints the public URL).
5. Open the printed URL to use the app. The default admin login is
   defined as a constant at the top of `app.py` — change it before any
   real deployment.


