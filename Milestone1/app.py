"""
app.py — Infosys Springboard Internship 7.0, Milestone 1
User Authentication Module (Streamlit + JWT + Gmail OTP)

Secrets expected as environment variables (set these from Colab Secrets
before launching this app — see the notebook launch cell):
    JWT_SECRET      -> signs session + OTP tokens
    EMAIL_ADDRESS   -> Gmail address that sends OTP mail
    EMAIL_PASSWORD  -> the 16-character Gmail App Password

Admin login is separate from the signup system (Step 11): the admin
credentials are constants below, not a row in the users table.
CHANGE THESE before you ever deploy this somewhere real.
"""

import os
import re
import time
import secrets as pysecrets
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

import jwt
import streamlit as st

import db

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-fallback-secret-change-me")
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
OTP_EXPIRY_MINUTES = 5
SESSION_HOURS = 2

# Hardcoded admin login — deliberately NOT a signup account (Step 11).
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What was the name of your first school?",
]

db.init_db()

st.set_page_config(page_title="Infosys Portal", page_icon="⚡", layout="centered")

COLORS = {
    "bg_main": "#f9fcfc", "bg_card": "#ffffff", "bg_card_alt": "#bae8e8",
    "text_main": "#2d334a", "text_heading": "#272343", "text_muted": "#64748b",
    "accent": "#ffd803", "accent_hover": "#e6c300", "accent_text": "#272343",
    "border": "#272343", "border_light": "#bae8e8", "danger": "#f87171",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Inter:wght@400;500;600&display=swap');
    html, body, .stApp {{ background:{COLORS['bg_main']} !important; font-family:'Inter',sans-serif !important; color:{COLORS['text_main']} !important; }}
    h1,h2,h3,h4 {{ font-family:'Poppins',sans-serif !important; color:{COLORS['text_heading']} !important; }}
    div[data-baseweb="input"] {{ background:{COLORS['bg_card']} !important; border:2px solid {COLORS['border']} !important; border-radius:10px !important; }}
    div[data-testid="stButton"] button {{
        background:{COLORS['accent']} !important; color:{COLORS['accent_text']} !important;
        border:2px solid {COLORS['border']} !important; border-radius:10px !important;
        font-weight:700 !important; box-shadow:4px 4px 0px {COLORS['border']} !important; width:100%;
    }}
    div[data-testid="stButton"] button:hover {{ background:{COLORS['accent_hover']} !important; }}
    .pn-card {{ background:{COLORS['bg_card']}; border:2px solid {COLORS['border']}; border-radius:14px; padding:24px; box-shadow:4px 4px 0px {COLORS['border_light']}; }}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# VALIDATION HELPERS (Step 8)
# ────────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"^[A-Za-z]{2,}[A-Za-z0-9._%+\-]*@[A-Za-z0-9\-]{2,}\.[A-Za-z]{2,}$")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def validate_password(pw: str):
    """Returns a list of unmet rules (empty list = valid)."""
    problems = []
    if len(pw) < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Z]", pw):
        problems.append("one uppercase letter")
    if not re.search(r"[a-z]", pw):
        problems.append("one lowercase letter")
    if not re.search(r"[0-9]", pw):
        problems.append("one number")
    if not re.search(r"[^A-Za-z0-9]", pw):
        problems.append("one special symbol")
    return problems


def require_fields(**fields):
    missing = [name for name, val in fields.items() if not str(val).strip()]
    return missing


# ────────────────────────────────────────────────────────────────
# JWT SESSION HELPERS (Step 7)
# ────────────────────────────────────────────────────────────────
def make_session_jwt(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_session_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────
# OTP HELPERS (Step 9 — email route)
# ────────────────────────────────────────────────────────────────
def generate_otp() -> str:
    return f"{pysecrets.randbelow(900000) + 100000}"


def make_otp_token(email: str, otp: str) -> str:
    import bcrypt
    otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    payload = {
        "sub": email,
        "otp_hash": otp_hash,
        "type": "password_reset_otp",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_otp_token(token: str, input_otp: str, email: str):
    import bcrypt
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") != email or payload.get("type") != "password_reset_otp":
            return False, "Security token mismatch."
        if bcrypt.checkpw(input_otp.encode(), payload["otp_hash"].encode()):
            return True, "Valid"
        return False, "Incorrect OTP code."
    except jwt.ExpiredSignatureError:
        return False, f"That OTP expired after {OTP_EXPIRY_MINUTES} minutes. Request a new one."
    except Exception:
        return False, "Invalid or corrupted verification token."


def send_otp_email(to_email: str, otp: str):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return False, "Email sending isn't configured (EMAIL_ADDRESS / EMAIL_PASSWORD missing)."

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Infosys Portal <{EMAIL_ADDRESS}>"
    msg["To"] = to_email
    msg["Subject"] = "Infosys Portal — Your Verification Code"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    text_body = (
        f"Your Infosys Portal verification code is: {otp}\n"
        f"It expires in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you did not request this, you can ignore this email."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;border:2px solid #272343;
                border-radius:12px;padding:28px;text-align:center;">
        <h2 style="color:#272343;margin-top:0;">Infosys Portal Verification</h2>
        <p style="color:#4a5568;">Use the code below to reset your password:</p>
        <div style="background:#ffd803;color:#272343;font-size:26px;font-weight:700;letter-spacing:6px;
                    padding:14px;border:2px solid #272343;border-radius:8px;display:inline-block;">{otp}</div>
        <p style="color:#4a5568;margin-top:16px;">Expires in {OTP_EXPIRY_MINUTES} minutes.</p>
    </div>
    """
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True, "OTP sent."
    except Exception as e:
        return False, f"SMTP error: {e}"


# ────────────────────────────────────────────────────────────────
# SESSION STATE
# ────────────────────────────────────────────────────────────────
DEFAULTS = {
    "token": None, "role": None, "page": "Login",
    "forgot_method": None, "forgot_username": None, "forgot_email": None,
    "forgot_stage": "start", "otp_token": None,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def goto(page):
    st.session_state.page = page
    st.rerun()


def logout():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.rerun()


def header(title, subtitle=""):
    st.markdown(f"""
    <div style="text-align:center;padding:1rem 0;">
        <div style="font-size:36px;">⚡</div>
        <h1 style="margin:0;font-size:1.8rem !important;">Infosys Portal</h1>
        <p style="color:{COLORS['text_muted']};font-size:13px;">{subtitle}</p>
    </div>
    <h3 style="text-align:center;">{title}</h3>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# LOGGED-OUT ROUTES
# ════════════════════════════════════════════════════════════════
if not st.session_state.token:

    if st.session_state.page not in ("Login", "Signup", "Forgot"):
        st.session_state.page = "Login"

    # ---------------- LOGIN ----------------
    if st.session_state.page == "Login":
        header("Sign in to your account")
        tab_user, tab_admin = st.tabs(["User Login", "Admin Login"])

        with tab_user:
            uid = st.text_input("Username or Email", key="login_uid")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Sign In →", key="login_btn"):
                missing = require_fields(**{"Username/Email": uid, "Password": pwd})
                if missing:
                    st.error(f"⚠️ Required: {', '.join(missing)}")
                else:
                    ok, username, email = db.verify_login(uid.strip(), pwd)
                    if ok:
                        st.session_state.token = make_session_jwt(username, "user")
                        st.session_state.role = "user"
                        goto("Dashboard")
                    else:
                        # Deliberately generic — never reveal which field was wrong.
                        st.error("❌ Invalid username/email or password.")

            c1, c2 = st.columns(2)
            if c1.button("Create Account", key="to_signup"):
                goto("Signup")
            if c2.button("Forgot Password", key="to_forgot"):
                goto("Forgot")

        with tab_admin:
            a_user = st.text_input("Admin Username", key="admin_uid")
            a_pwd = st.text_input("Admin Password", type="password", key="admin_pwd")
            if st.button("Admin Sign In →", key="admin_login_btn"):
                if a_user == ADMIN_USERNAME and a_pwd == ADMIN_PASSWORD:
                    st.session_state.token = make_session_jwt(ADMIN_USERNAME, "admin")
                    st.session_state.role = "admin"
                    goto("Dashboard")
                else:
                    st.error("❌ Invalid admin credentials.")

    # ---------------- SIGNUP ----------------
    elif st.session_state.page == "Signup":
        header("Create an account", "Join Infosys Portal")
        uname = st.text_input("Username")
        email = st.text_input("Email address")
        pwd = st.text_input("Password", type="password", help="Min 8 chars, upper, lower, number, symbol")
        cpwd = st.text_input("Confirm Password", type="password")
        sq = st.selectbox("Security Question", SECURITY_QUESTIONS)
        sa = st.text_input("Security Answer")

        if st.button("Create Account →"):
            missing = require_fields(
                Username=uname, Email=email, Password=pwd,
                **{"Confirm Password": cpwd, "Security Answer": sa},
            )
            if missing:
                st.error(f"⚠️ Required: {', '.join(missing)}")
            elif not validate_email(email):
                st.error("❌ Enter a valid email, e.g. ab@cd.ef")
            elif validate_password(pwd):
                st.error("❌ Password needs: " + ", ".join(validate_password(pwd)))
            elif pwd != cpwd:
                st.error("❌ Passwords do not match.")
            else:
                ok, message = db.create_user(uname, email, pwd, sq, sa)
                if ok:
                    st.success("✅ " + message + " Please log in.")
                    time.sleep(1.2)
                    goto("Login")
                else:
                    st.error("❌ " + message)

        if st.button("← Back to Sign In"):
            goto("Login")

    # ---------------- FORGOT PASSWORD ----------------
    elif st.session_state.page == "Forgot":
        header("Reset your password", "Choose a verification method")

        if st.session_state.forgot_stage == "start":
            method = st.radio("Verification method", ["Security Question", "Email OTP"], horizontal=True)

            if method == "Security Question":
                uname = st.text_input("Username")
                if st.button("Continue →"):
                    if not uname.strip():
                        st.error("⚠️ Username is required.")
                    else:
                        q = db.get_security_question(uname.strip())
                        if q:
                            st.session_state.forgot_username = uname.strip()
                            st.session_state.forgot_method = "sq"
                            st.session_state.forgot_stage = "verify"
                            st.rerun()
                        else:
                            st.error("❌ No account found with that username.")
            else:
                email = st.text_input("Registered email address")
                if st.button("Send OTP →"):
                    if not email.strip():
                        st.error("⚠️ Email is required.")
                    elif not validate_email(email):
                        st.error("❌ Enter a valid email address.")
                    elif not db.get_user_by_email(email.strip()):
                        st.error("❌ Email not registered.")
                    else:
                        otp = generate_otp()
                        with st.spinner("Sending OTP..."):
                            ok, msg = send_otp_email(email.strip(), otp)
                        if ok:
                            st.session_state.forgot_email = email.strip().lower()
                            st.session_state.otp_token = make_otp_token(email.strip().lower(), otp)
                            st.session_state.forgot_method = "otp"
                            st.session_state.forgot_stage = "verify"
                            st.success("✅ OTP sent — check your inbox.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ " + msg)

        elif st.session_state.forgot_stage == "verify":
            if st.session_state.forgot_method == "sq":
                q = db.get_security_question(st.session_state.forgot_username)
                st.info(f"❓ {q}")
                ans = st.text_input("Your answer")
                if st.button("Verify →"):
                    if not ans.strip():
                        st.error("⚠️ Answer is required.")
                    elif db.verify_security_answer(st.session_state.forgot_username, ans):
                        st.session_state.forgot_stage = "reset"
                        st.rerun()
                    else:
                        st.error("❌ Incorrect answer.")
            else:
                st.info(f"📧 Code sent to {st.session_state.forgot_email} (valid {OTP_EXPIRY_MINUTES} min).")
                otp_in = st.text_input("6-digit OTP", max_chars=6)
                if st.button("Verify →"):
                    if not otp_in.strip():
                        st.error("⚠️ OTP is required.")
                    else:
                        ok, msg = verify_otp_token(st.session_state.otp_token, otp_in.strip(), st.session_state.forgot_email)
                        if ok:
                            st.session_state.forgot_stage = "reset"
                            st.rerun()
                        else:
                            st.error("❌ " + msg)

        elif st.session_state.forgot_stage == "reset":
            npw = st.text_input("New Password", type="password")
            cnpw = st.text_input("Confirm New Password", type="password")
            if st.button("Update Password →"):
                missing = require_fields(**{"New Password": npw, "Confirm Password": cnpw})
                if missing:
                    st.error(f"⚠️ Required: {', '.join(missing)}")
                elif validate_password(npw):
                    st.error("❌ Password needs: " + ", ".join(validate_password(npw)))
                elif npw != cnpw:
                    st.error("❌ Passwords do not match.")
                else:
                    if st.session_state.forgot_method == "sq":
                        db.reset_password_by_username(st.session_state.forgot_username, npw)
                    else:
                        db.reset_password_by_email(st.session_state.forgot_email, npw)
                    st.success("✅ Password updated! Please log in.")
                    time.sleep(1.2)
                    st.session_state.forgot_stage = "start"
                    st.session_state.forgot_method = None
                    goto("Login")

        if st.button("← Cancel"):
            st.session_state.forgot_stage = "start"
            st.session_state.forgot_method = None
            goto("Login")

# ════════════════════════════════════════════════════════════════
# LOGGED-IN ROUTES
# ════════════════════════════════════════════════════════════════
else:
    payload = verify_session_jwt(st.session_state.token)
    if not payload:
        logout()

    role = payload.get("role")
    who = payload.get("sub")

    with st.sidebar:
        st.markdown(f"### ⚡ Infosys Portal\n**{'Admin' if role == 'admin' else who}**")
        if st.button("Logout"):
            logout()

    if role == "admin":
        st.title("🛡️ Admin Dashboard")
        st.caption("All registered users — passwords are never shown.")
        users = db.list_all_users()
        if users:
            st.table(
                [{"Username": u, "Email": e, "Joined (UTC)": c} for u, e, c in users]
            )
        else:
            st.info("No users have registered yet.")
    else:
        st.title(f"👋 Welcome, {who}!")
        st.markdown(f"""
        <div class="pn-card">
            <p>You're securely logged in via a JWT session token.</p>
            <p style="color:{COLORS['text_muted']};font-size:13px;">Session valid for {SESSION_HOURS} hours.</p>
        </div>
        """, unsafe_allow_html=True)
