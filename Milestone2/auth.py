"""
FreightQuote AI — auth.py
Adapted from the mentor-provided FranchiseOps template. Keeps the same
tabbed portal structure and Neo-Brutalist styling, and adds the three
hardening layers Milestone 2 requires that the base template didn't have:
    - Progressive account lockout (Section 5)
    - Email OTP as a second Forgot-Password route, with resend cooldown (Section 5.1)
    - Live password strength checker on Register + Reset (Section 6)
"""
import re
import time
import smtplib
import datetime
import sqlite3
import jwt
import bcrypt
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (DB_PATH, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD,
                    FALLBACK_ADMIN_USERNAME, FALLBACK_ADMIN_PASSWORD, EMAIL_ID, EMAIL_PASSWORD)
from ui_theme import COLORS
import db as datastore

JWT_SECRET = JWT_SECRET_KEY
OTP_EXPIRY_MINUTES = 5

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What city were you born in?",
    "What is your favorite school teacher's name?",
]
ROLES = ["Logistics Manager", "Shipper", "Analyst", "Admin"]
EMAIL_RE = re.compile(r"^[A-Za-z]{2,}[A-Za-z0-9._%+\-]*@[A-Za-z0-9\-]{2,}\.[A-Za-z]{2,}$")


def _field_feedback(key):
    fb = st.session_state.get(key)
    if not fb:
        return
    ok, msg = fb
    color = COLORS["green"] if ok else COLORS["red"]
    st.markdown(f'<div style="font-size:12.5px;margin:-6px 0 10px 2px;color:{color};">{msg}</div>',
                unsafe_allow_html=True)


def _check_reg_username():
    v = st.session_state.get("r_u", "").strip()
    if not v:
        st.session_state["fb_r_u"] = (False, "Username is required.")
    elif get_conn().execute("SELECT 1 FROM users WHERE username=?", (v,)).fetchone():
        st.session_state["fb_r_u"] = (False, "This username is already taken.")
    else:
        st.session_state["fb_r_u"] = (True, "Username is available.")


def _check_reg_email():
    v = st.session_state.get("r_e", "").strip()
    if not v:
        st.session_state["fb_r_e"] = (False, "Email is required.")
    elif not EMAIL_RE.match(v):
        st.session_state["fb_r_e"] = (False, "Enter a valid email, e.g. name@example.com")
    elif get_conn().execute("SELECT 1 FROM users WHERE email=?", (v,)).fetchone():
        st.session_state["fb_r_e"] = (False, "This email is already registered.")
    else:
        st.session_state["fb_r_e"] = (True, "Email looks good.")


def _check_reg_confirm():
    pw = st.session_state.get("r_p", "")
    cpw = st.session_state.get("r_cp", "")
    if not cpw:
        st.session_state["fb_r_cp"] = (False, "Please confirm your password.")
    elif cpw != pw:
        st.session_state["fb_r_cp"] = (False, "Passwords do not match.")
    else:
        st.session_state["fb_r_cp"] = (True, "Passwords match.")


def _check_reg_answer():
    v = st.session_state.get("r_a", "").strip()
    st.session_state["fb_r_a"] = (
        (False, "Security answer is required.") if not v else (True, "Looks good.")
    )


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def hash_txt(t):
    return bcrypt.hashpw(t.encode(), bcrypt.gensalt()).decode()


def check_txt(t, h):
    try:
        return bcrypt.checkpw(t.encode(), h.encode()) if h else False
    except Exception:
        return False


def make_jwt(email, username, role):
    return jwt.encode(
        {"email": email, "username": username, "role": role,
         "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)},
        JWT_SECRET, algorithm="HS256",
    )


def verify_jwt(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def _seed_admin_if_missing(conn, login_id, password):
    exists = conn.execute(
        "SELECT id FROM users WHERE email=? OR username=?", (login_id, login_id)
    ).fetchone()
    if exists:
        return
    conn.execute(
        """INSERT OR IGNORE INTO users
           (username, email, password_hash, security_question, security_answer_hash, role, account_status)
           VALUES (?, ?, ?, ?, ?, 'Admin', 'active')""",
        (login_id, login_id, hash_txt(password),
         "What is your pet's name?", hash_txt("admin")),
    )


@st.cache_resource
def init_auth():
    datastore.init_db()
    with get_conn() as conn:
        # Two admin accounts: your own (from ADMIN_USERNAME/ADMIN_PASSWORD
        # secrets) plus a guaranteed fallback — so a secrets typo never
        # fully locks you out of the Admin Dashboard. If both resolve to
        # the same login id (e.g. secrets weren't set), only one is created.
        _seed_admin_if_missing(conn, ADMIN_USERNAME, ADMIN_PASSWORD)
        _seed_admin_if_missing(conn, FALLBACK_ADMIN_USERNAME, FALLBACK_ADMIN_PASSWORD)
        conn.commit()


# ────────────────────────────────────────────────────────────────
# 6. PASSWORD STRENGTH POLICY (Section 6)
# ────────────────────────────────────────────────────────────────
def check_password_strength(password: str):
    """Returns (tier, badge_label, color, message, blocked)."""
    length = len(password)
    if length < 5:
        return ("weak", "Weak", COLORS["red"],
                "Password too weak (minimum 5 characters required).", True)
    if length < 10:
        return ("average", "Average", COLORS["yellow"],
                "Average strength (10+ characters recommended for enterprise security).", False)
    return ("good", "Good", COLORS["green"], "Good password strength.", False)


def render_strength_badge(password: str):
    if not password:
        return
    tier, badge, color, msg, blocked = check_password_strength(password)
    st.markdown(
        f'<span class="pn-badge" style="background:{color};">{badge}</span> '
        f'<span style="font-size:12.5px;color:{COLORS["text_muted"]};">{msg}</span>',
        unsafe_allow_html=True,
    )
    return blocked


# ────────────────────────────────────────────────────────────────
# 5. PROGRESSIVE ACCOUNT LOCKOUT (Section 5)
# ────────────────────────────────────────────────────────────────
LOCKOUT_SCHEDULE = {3: 300, 4: 900}  # seconds: 3rd -> 5 min, 4th -> 15 min


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def attempt_login(identifier: str, password: str):
    """Returns (ok, message, user_row_dict | None)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, role, failed_attempts, "
            "lock_until, account_status FROM users WHERE email=? OR username=?",
            (identifier, identifier),
        ).fetchone()

    if not row:
        return False, "Invalid email/username or password.", None

    (uid, username, email, pw_hash, role, attempts, lock_until_raw, status) = row

    if status == "locked":
        return False, (
            "Account permanently locked due to 5 failed attempts. "
            "Only the System Administrator can unlock this account via the Admin Dashboard."
        ), None

    lock_until = _parse_dt(lock_until_raw)
    now = datetime.datetime.utcnow()
    if lock_until and now < lock_until:
        mins = max(int((lock_until - now).total_seconds()) // 60, 1)
        return False, f"Account temporarily locked. Try again in about {mins} minute(s).", None

    if check_txt(password, pw_hash):
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET failed_attempts=0, lock_until=NULL, account_status='active' WHERE id=?",
                (uid,),
            )
            conn.commit()
        return True, "Login successful.", {"id": uid, "username": username, "email": email, "role": role}

    # Wrong password — advance the counter (counter is NOT reset just
    # because a timed lockout window expired; only a success resets it).
    new_attempts = attempts + 1
    if new_attempts >= 5:
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET failed_attempts=?, lock_until=NULL, account_status='locked' WHERE id=?",
                (new_attempts, uid),
            )
            conn.commit()
        return False, (
            "Account permanently locked due to 5 failed attempts. "
            "Only the System Administrator can unlock this account via the Admin Dashboard."
        ), None
    if new_attempts == 4:
        until = (now + datetime.timedelta(seconds=LOCKOUT_SCHEDULE[4])).isoformat(timespec="seconds")
        with get_conn() as conn:
            conn.execute("UPDATE users SET failed_attempts=?, lock_until=? WHERE id=?", (new_attempts, until, uid))
            conn.commit()
        return False, "Account temporarily locked for 15 minutes due to 4 failed attempts.", None
    if new_attempts == 3:
        until = (now + datetime.timedelta(seconds=LOCKOUT_SCHEDULE[3])).isoformat(timespec="seconds")
        with get_conn() as conn:
            conn.execute("UPDATE users SET failed_attempts=?, lock_until=? WHERE id=?", (new_attempts, until, uid))
            conn.commit()
        return False, "Account temporarily locked for 5 minutes due to 3 failed attempts.", None

    with get_conn() as conn:
        conn.execute("UPDATE users SET failed_attempts=? WHERE id=?", (new_attempts, uid))
        conn.commit()
    remaining = 3 - new_attempts
    return False, f"Invalid email/username or password. {remaining} attempt(s) remaining before a temporary lock.", None


# ────────────────────────────────────────────────────────────────
# 5.1 OTP — email delivery + resend cooldown
# ────────────────────────────────────────────────────────────────
OTP_COOLDOWN_SCHEDULE = {1: 60, 2: 180, 3: 300}
OTP_COOLDOWN_DEFAULT = 3600


def can_resend_otp(email: str):
    key = f"otp_next_allowed::{email}"
    next_allowed = st.session_state.get(key, 0)
    now = time.time()
    if now < next_allowed:
        remaining = int(next_allowed - now)
        msg = (f"Please wait {remaining // 60} minute(s) before requesting another OTP."
               if remaining >= 60 else
               f"Please wait {remaining} second(s) before requesting another OTP.")
        return False, msg
    return True, None


def _register_otp_resend(email: str):
    count_key = f"otp_resend_count::{email}"
    next_key = f"otp_next_allowed::{email}"
    count = st.session_state.get(count_key, 0) + 1
    st.session_state[count_key] = count
    cooldown = OTP_COOLDOWN_SCHEDULE.get(count, OTP_COOLDOWN_DEFAULT)
    st.session_state[next_key] = time.time() + cooldown


def generate_otp():
    import secrets as _secrets
    return f"{_secrets.randbelow(900000) + 100000}"


def send_otp_email(to_email: str, otp: str):
    if not EMAIL_ID or not EMAIL_PASSWORD:
        return False, "Email sending isn't configured (EMAIL_ADDRESS / EMAIL_PASSWORD secrets are missing)."
    msg = MIMEMultipart("alternative")
    msg["From"] = f"FreightQuote AI <{EMAIL_ID}>"
    msg["To"] = to_email
    msg["Subject"] = "FreightQuote AI — Your Password Reset Code"

    text_body = (
        f"Your FreightQuote AI verification code is: {otp}\n"
        f"It expires in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;background:#F7F4ED;padding:32px 16px;">
      <div style="max-width:460px;margin:0 auto;background:#FFFEFB;border:1.5px solid #DED6C3;
                  border-radius:20px;padding:36px 32px;text-align:center;">
        <div style="width:52px;height:52px;border-radius:14px;margin:0 auto 18px;background:#C8A96B;
                    display:flex;align-items:center;justify-content:center;font-size:24px;line-height:52px;">🚛</div>
        <h2 style="margin:0 0 6px;color:#3A4238;font-size:20px;">FreightQuote AI</h2>
        <p style="margin:0 0 24px;color:#7C8577;font-size:13.5px;">Password reset verification</p>
        <p style="margin:0 0 18px;color:#454F42;font-size:14px;">
          Use the code below to reset your password. It expires in
          <b>{OTP_EXPIRY_MINUTES} minutes</b>.
        </p>
        <div style="background:#F7F4ED;border:1.5px dashed #C8A96B;border-radius:14px;
                    padding:18px;margin:0 0 22px;">
          <span style="font-size:30px;font-weight:700;letter-spacing:8px;color:#3A4238;">{otp}</span>
        </div>
        <p style="margin:0;color:#7C8577;font-size:12px;">
          If you didn't request this, you can safely ignore this email.
        </p>
      </div>
    </div>
    """
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as s:
            s.starttls()
            s.login(EMAIL_ID, EMAIL_PASSWORD)
            s.sendmail(EMAIL_ID, to_email, msg.as_string())
        datastore.log_notification("Email", to_email, "Password Reset OTP", "OTP sent", "Sent")
        return True, "OTP sent."
    except Exception as e:
        return False, f"SMTP error: {e}"


def make_otp_token(email, otp):
    otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    payload = {
        "sub": email, "otp_hash": otp_hash, "type": "password_reset_otp",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_otp_token(token, input_otp, email):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") != email or payload.get("type") != "password_reset_otp":
            return False, "Security token mismatch."
        if bcrypt.checkpw(input_otp.encode(), payload["otp_hash"].encode()):
            return True, "Valid"
        return False, "Incorrect OTP code."
    except jwt.ExpiredSignatureError:
        return False, f"OTP expired after {OTP_EXPIRY_MINUTES} minutes. Request a new one."
    except Exception:
        return False, "Invalid or corrupted verification token."


# ────────────────────────────────────────────────────────────────
# UI — same tabbed portal structure as the mentor template
# ────────────────────────────────────────────────────────────────
def render_auth_portal():
    init_auth()
    if "token" not in st.session_state:
        st.session_state["token"] = None
    for k, v in [("reset_email", None), ("reset_q", None), ("reset_method", None), ("otp_token", None)]:
        st.session_state.setdefault(k, v)

    st.markdown(f"""
    <div style="text-align:center;padding:1.5rem 0 1rem;">
        <div style="font-size:44px;margin-bottom:8px;">🚛</div>
        <h1 style="font-size:2rem !important;margin:0;">FreightQuote AI Portal</h1>
        <p style="color:{COLORS['text_muted']};font-size:14px;margin:4px 0 0;">Multi-Agent Freight Intelligence Platform</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        tab1, tab2, tab3 = st.tabs(["Sign In", "Register Account", "Reset Password"])

        with tab1:
            login_id = st.text_input("Email / Username", key="l_email", placeholder="you@example.com")
            login_pw = st.text_input("Password", type="password", key="l_pw", placeholder="••••••••")
            if st.button("Sign In to Portal", key="btn_login"):
                if not login_id or not login_pw:
                    st.warning("Please fill out both fields.")
                else:
                    ok, msg, user = attempt_login(login_id.strip(), login_pw)
                    if ok:
                        st.session_state["token"] = make_jwt(user["email"], user["username"], user["role"])
                        st.session_state["username"] = user["username"]
                        st.session_state["role"] = user["role"]
                        st.success(f"Welcome back, {user['username']} [{user['role']}]")
                        st.rerun()
                    else:
                        st.error(msg)

        with tab2:
            r_user = st.text_input("Username", key="r_u", on_change=_check_reg_username)
            _field_feedback("fb_r_u")

            r_email = st.text_input("Email Address", key="r_e", on_change=_check_reg_email)
            _field_feedback("fb_r_e")

            r_pw = st.text_input("Create Password", type="password", key="r_p")
            if r_pw:
                render_strength_badge(r_pw)

            r_cp = st.text_input("Confirm Password", type="password", key="r_cp", on_change=_check_reg_confirm)
            _field_feedback("fb_r_cp")

            r_role = st.selectbox("Select Role", ROLES, key="r_role")
            r_q = st.selectbox("Security Question", SECURITY_QUESTIONS, key="r_q")
            r_a = st.text_input("Security Answer", key="r_a", on_change=_check_reg_answer)
            _field_feedback("fb_r_a")

            if st.button("Create Account", key="btn_reg"):
                _check_reg_username()
                _check_reg_email()
                _check_reg_confirm()
                _check_reg_answer()
                all_ok = all(st.session_state.get(k, (False, ""))[0]
                             for k in ("fb_r_u", "fb_r_e", "fb_r_cp", "fb_r_a"))
                if not all_ok:
                    st.error("Please fix the highlighted fields above before continuing.")
                elif check_password_strength(r_pw)[4]:
                    st.error(check_password_strength(r_pw)[3])
                else:
                    try:
                        with get_conn() as conn:
                            conn.execute(
                                "INSERT INTO users (username, email, password_hash, security_question, "
                                "security_answer_hash, role, account_status) VALUES (?,?,?,?,?,?,'active')",
                                (r_user, r_email, hash_txt(r_pw), r_q, hash_txt(r_a.lower().strip()), r_role),
                            )
                            conn.commit()
                        st.success(f"Account registered with role [{r_role}]. Please switch to Sign In.")
                        for k in ("fb_r_u", "fb_r_e", "fb_r_cp", "fb_r_a"):
                            st.session_state.pop(k, None)
                    except Exception:
                        st.error("Registration failed: email or username may already exist.")

        with tab3:
            if st.session_state["reset_email"] is None:
                method = st.radio("Verification method", ["Security Question", "Email OTP"], horizontal=True)
                f_email = st.text_input("Registered Email", key="f_e")

                if method == "Security Question":
                    if st.button("Verify Email & Fetch Question", key="btn_f1"):
                        with get_conn() as conn:
                            u = conn.execute(
                                "SELECT security_question FROM users WHERE email=?", (f_email,)
                            ).fetchone()
                        if u:
                            st.session_state["reset_email"] = f_email
                            st.session_state["reset_q"] = u[0]
                            st.session_state["reset_method"] = "sq"
                            st.rerun()
                        else:
                            st.error("Email not found.")
                else:
                    if st.button("Send OTP", key="btn_send_otp"):
                        with get_conn() as conn:
                            exists = conn.execute("SELECT 1 FROM users WHERE email=?", (f_email,)).fetchone()
                        if not exists:
                            st.error("Email not found.")
                        else:
                            allowed, cooldown_msg = can_resend_otp(f_email)
                            if not allowed:
                                st.warning(cooldown_msg)
                            else:
                                otp = generate_otp()
                                st.session_state["reset_email"] = f_email
                                st.session_state["reset_method"] = "otp"
                                st.session_state["otp_token"] = make_otp_token(f_email, otp)
                                ok, msg = send_otp_email(f_email, otp)
                                _register_otp_resend(f_email)
                                if ok:
                                    st.session_state.pop("otp_send_error", None)
                                    st.success("OTP sent — check your inbox.")
                                else:
                                    st.session_state["otp_preview"] = otp
                                    st.session_state["otp_send_error"] = msg
                                st.rerun()

            else:
                reset_email = st.session_state["reset_email"]

                if st.session_state["reset_method"] == "sq":
                    st.info(f"Security Question: {st.session_state['reset_q']}")
                    ans_try = st.text_input("Enter Answer", key="f_ans")
                else:
                    st.info(f"Code sent to {reset_email} (valid {OTP_EXPIRY_MINUTES} minutes).")
                    if st.session_state.get("otp_preview"):
                        real_reason = st.session_state.get("otp_send_error", "Email could not be sent.")
                        st.markdown(
                            f'<div class="pn-card" style="text-align:center;">'
                            f'<b>Delivery failed — {real_reason}</b><br>'
                            f'<span style="font-size:12.5px;color:{COLORS["text_muted"]};">'
                            f'Showing the code here so you can still test.</span><br><br>'
                            f'<span style="font-size:24px;letter-spacing:6px;">{st.session_state["otp_preview"]}</span>'
                            f'</div>', unsafe_allow_html=True,
                        )
                    otp_try = st.text_input("Enter 6-digit OTP", key="f_otp", max_chars=6)
                    resend_allowed, resend_msg = can_resend_otp(reset_email)
                    if st.button("Resend OTP", key="btn_resend_otp"):
                        if not resend_allowed:
                            st.warning(resend_msg)
                        else:
                            otp = generate_otp()
                            st.session_state["otp_token"] = make_otp_token(reset_email, otp)
                            ok, msg = send_otp_email(reset_email, otp)
                            _register_otp_resend(reset_email)
                            if ok:
                                st.session_state.pop("otp_preview", None)
                                st.session_state.pop("otp_send_error", None)
                                st.success("New OTP sent.")
                            else:
                                st.session_state["otp_preview"] = otp
                                st.session_state["otp_send_error"] = msg
                            st.rerun()

                new_pw = st.text_input("New Password", type="password", key="f_npw")
                blocked = render_strength_badge(new_pw) if new_pw else False

                if st.button("Confirm Password Reset", key="btn_f2"):
                    verified = False
                    if st.session_state["reset_method"] == "sq":
                        with get_conn() as conn:
                            u_hash = conn.execute(
                                "SELECT security_answer_hash FROM users WHERE email=?", (reset_email,)
                            ).fetchone()
                        verified = bool(u_hash) and check_txt(ans_try.lower().strip(), u_hash[0])
                        if not verified:
                            st.error("Incorrect security answer.")
                    else:
                        ok, msg = verify_otp_token(st.session_state["otp_token"], otp_try.strip(), reset_email)
                        verified = ok
                        if not verified:
                            st.error(msg)

                    if verified:
                        if check_password_strength(new_pw)[4]:
                            st.error(check_password_strength(new_pw)[3])
                        else:
                            with get_conn() as conn:
                                conn.execute(
                                    "UPDATE users SET password_hash=?, failed_attempts=0, lock_until=NULL, "
                                    "account_status='active' WHERE email=?",
                                    (hash_txt(new_pw), reset_email),
                                )
                                conn.commit()
                            st.success("Password reset successfully. Please sign in.")
                            for k in ("reset_email", "reset_q", "reset_method", "otp_token", "otp_preview", "otp_send_error"):
                                st.session_state.pop(k, None)
                            time.sleep(1)
                            st.rerun()

                if st.button("Cancel", key="btn_reset_cancel"):
                    for k in ("reset_email", "reset_q", "reset_method", "otp_token", "otp_preview", "otp_send_error"):
                        st.session_state.pop(k, None)
                    st.rerun()
