"""
app.py — Infosys Springboard Internship 7.0, Milestone 1
User Authentication Module (Streamlit + JWT + Gmail OTP)

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

# Admin login is separate from the signup system (Step 11) — it is never
# a row in the users table. Credentials come from environment variables
# (set ADMIN_USERNAME / ADMIN_PASSWORD in Colab Secrets, same as the other
# secrets) so nothing sensitive is hardcoded in this file. The fallbacks
# below only exist so the app still runs during local testing — replace
# them via secrets before this ever goes near a real deployment.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What was the name of your first school?",
]

db.init_db()

# Force a light theme explicitly — without this, Streamlit falls back to
# each viewer's system theme (often dark), which breaks custom CSS that
# assumes a light background and makes text/labels invisible.
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w") as f:
    f.write(
        '[theme]\n'
        'base="light"\n'
        'primaryColor="#7c5cff"\n'
        'backgroundColor="#f6f5ff"\n'
        'secondaryBackgroundColor="#ffffff"\n'
        'textColor="#1e1b34"\n'
    )

st.set_page_config(page_title="Infosys Portal", page_icon="⚡", layout="centered")

COLORS = {
    "bg_main": "#f6f5ff", "bg_card": "#ffffff", "bg_card_alt": "#eee9ff",
    "text_main": "#1e1b34", "text_heading": "#1e1b34", "text_muted": "#6b6785",
    "accent": "#7c5cff", "accent_hover": "#6a4ce0", "accent_text": "#ffffff",
    "border": "#e2defa", "border_strong": "#7c5cff", "danger": "#e0455f",
    "success": "#1fae6e",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

    html, body, .stApp {{
        background: linear-gradient(180deg, #f6f5ff 0%, #eef0fb 100%) !important;
        font-family: 'Inter', sans-serif !important;
        color: {COLORS['text_main']} !important;
    }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    .block-container {{ padding-top: 2rem !important; max-width: 760px; }}

    h1, h2, h3, h4 {{ font-family: 'Poppins', sans-serif !important; color: {COLORS['text_heading']} !important; }}

    /* Labels above inputs — force dark, visible text regardless of theme */
    label, label p, label span, .stMarkdown p {{
        color: {COLORS['text_heading']} !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }}

    /* Text inputs & selects — white surface, dark readable text, always */
    div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {{
        background: {COLORS['bg_card']} !important;
        border: 1.5px solid {COLORS['border']} !important;
        border-radius: 12px !important;
        box-shadow: none !important;
    }}
    div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within {{
        border-color: {COLORS['border_strong']} !important;
        box-shadow: 0 0 0 3px rgba(124,92,255,0.15) !important;
    }}
    input, textarea, div[data-baseweb="select"] span, div[data-baseweb="select"] div {{
        color: {COLORS['text_main']} !important;
        -webkit-text-fill-color: {COLORS['text_main']} !important;
        background: transparent !important;
        font-size: 15px !important;
    }}
    input::placeholder {{ color: {COLORS['text_muted']} !important; opacity: 1 !important; }}

    /* Tabs */
    button[data-baseweb="tab"] {{ color: {COLORS['text_muted']} !important; font-weight: 600 !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: {COLORS['accent']} !important; }}
    div[data-baseweb="tab-highlight"] {{ background-color: {COLORS['accent']} !important; }}

    /* Radio buttons */
    div[role="radiogroup"] label p {{ color: {COLORS['text_main']} !important; font-weight: 500 !important; }}

    /* Primary action buttons */
    div[data-testid="stButton"] button {{
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #9b7bff 100%) !important;
        color: {COLORS['accent_text']} !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        letter-spacing: 0.2px !important;
        height: 46px !important;
        width: 100%;
        box-shadow: 0 4px 14px rgba(124,92,255,0.35) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease !important;
    }}
    div[data-testid="stButton"] button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 22px rgba(124,92,255,0.45) !important;
        filter: brightness(1.04) !important;
    }}
    div[data-testid="stButton"] button:active {{
        transform: translateY(0px) scale(0.98) !important;
        box-shadow: 0 3px 10px rgba(124,92,255,0.35) !important;
    }}
    div[data-testid="stButton"] button p {{ color: {COLORS['accent_text']} !important; }}

    /* Secondary / ghost buttons — any container whose key starts with "secondary" */
    div[class*="st-key-secondary"] div[data-testid="stButton"] button {{
        background: {COLORS['bg_card']} !important;
        color: {COLORS['accent']} !important;
        border: 1.5px solid {COLORS['accent']} !important;
        box-shadow: none !important;
    }}
    div[class*="st-key-secondary"] div[data-testid="stButton"] button p {{ color: {COLORS['accent']} !important; }}
    div[class*="st-key-secondary"] div[data-testid="stButton"] button:hover {{
        background: {COLORS['bg_card_alt']} !important;
        transform: none !important;
    }}

    /* Muted / plain-link style buttons (e.g. Cancel, Back) */
    div[class*="st-key-ghost"] div[data-testid="stButton"] button {{
        background: transparent !important;
        color: {COLORS['text_muted']} !important;
        border: none !important;
        box-shadow: none !important;
        font-weight: 600 !important;
    }}
    div[class*="st-key-ghost"] div[data-testid="stButton"] button p {{ color: {COLORS['text_muted']} !important; }}
    div[class*="st-key-ghost"] div[data-testid="stButton"] button:hover {{ color: {COLORS['accent']} !important; }}

    .pn-card {{
        background: {COLORS['bg_card']};
        border: 1.5px solid {COLORS['border']};
        border-radius: 18px;
        padding: 28px;
        box-shadow: 0 10px 30px rgba(30,27,52,0.06);
    }}
    .pn-hero {{ text-align: center; padding: 8px 0 20px; }}
    .pn-hero .logo {{
        width: 60px; height: 60px; border-radius: 16px; margin: 0 auto 12px;
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #9b7bff 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 28px; box-shadow: 0 8px 20px rgba(124,92,255,0.35);
    }}
    .pn-hero h1 {{ font-size: 1.7rem !important; margin: 0; }}
    .pn-hero p {{ color: {COLORS['text_muted']}; font-size: 13px; margin: 4px 0 0; }}
    .pn-subtitle {{ text-align:center; font-weight:700; font-size:1.1rem; margin-bottom:18px; color:{COLORS['text_heading']}; }}

    /* Dashboard banner */
    .dash-banner {{
        background: linear-gradient(120deg, #1e1b34 0%, #3a2f6b 100%);
        border-radius: 20px;
        padding: 26px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 26px;
        box-shadow: 0 14px 34px rgba(30,27,52,0.25);
    }}
    .dash-banner h2 {{ color: #ffffff !important; margin: 0; font-size: 1.4rem !important; }}
    .dash-banner .sub {{ color: #cfc9ff; font-size: 12.5px; margin-top: 2px; }}
    .dash-avatar {{
        width: 42px; height: 42px; border-radius: 50%;
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #9b7bff 100%);
        color: #fff; display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 16px; flex-shrink: 0;
    }}
    .dash-pill {{
        display: flex; align-items: center; gap: 10px;
        background: rgba(255,255,255,0.08); padding: 6px 16px 6px 6px;
        border-radius: 30px;
    }}
    .dash-pill span {{ color: #fff; font-weight: 600; font-size: 14px; }}

    /* Stat cards */
    .stat-card {{
        background: {COLORS['bg_card']}; border: 1.5px solid {COLORS['border']};
        border-radius: 16px; padding: 18px; text-align: center;
        box-shadow: 0 6px 18px rgba(30,27,52,0.05);
    }}
    .stat-card .icon {{ font-size: 22px; margin-bottom: 6px; }}
    .stat-card .val {{ font-size: 22px; font-weight: 800; color: {COLORS['text_heading']}; }}
    .stat-card .lbl {{ font-size: 11.5px; color: {COLORS['text_muted']}; font-weight: 600; margin-top: 2px; }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{ background: #ffffff !important; border-right: 1px solid {COLORS['border']} !important; }}
    .sb-profile {{ text-align:center; padding: 10px 0 18px; }}
    .sb-avatar {{
        width: 56px; height: 56px; border-radius: 50%; margin: 0 auto 10px;
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #9b7bff 100%);
        display:flex; align-items:center; justify-content:center; color:#fff;
        font-weight:800; font-size:20px; box-shadow: 0 8px 18px rgba(124,92,255,0.3);
    }}
    .sb-name {{ font-weight: 700; color: {COLORS['text_heading']}; font-size: 15px; }}
    .sb-role {{ font-size: 11.5px; color: {COLORS['text_muted']}; text-transform: uppercase; letter-spacing: 0.5px; }}

    /* Admin user table */
    .u-table {{
        background: {COLORS['bg_card']}; border: 1.5px solid {COLORS['border']};
        border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(30,27,52,0.05);
    }}
    .u-row {{
        display: flex; align-items: center; gap: 14px; padding: 14px 20px;
        border-bottom: 1px solid {COLORS['border']};
    }}
    .u-row:last-child {{ border-bottom: none; }}
    .u-row:hover {{ background: {COLORS['bg_card_alt']}; }}
    .u-avatar {{
        width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #9b7bff 100%);
        color: #fff; display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 13px;
    }}
    .u-name {{ font-weight: 700; color: {COLORS['text_heading']}; font-size: 14px; }}
    .u-email {{ font-size: 12.5px; color: {COLORS['text_muted']}; }}
    .u-joined {{
        margin-left: auto; font-size: 11px; color: {COLORS['accent']}; font-weight: 700;
        background: {COLORS['bg_card_alt']}; padding: 4px 10px; border-radius: 20px; white-space: nowrap;
    }}

    /* Account-details row list (user dashboard) */
    .d-row {{
        display: flex; align-items: center; gap: 12px; padding: 12px 0;
        border-bottom: 1px solid {COLORS['border']};
    }}
    .d-row:last-child {{ border-bottom: none; }}
    .d-row .ic {{
        width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
        background: {COLORS['bg_card_alt']}; display: flex; align-items: center;
        justify-content: center; font-size: 15px;
    }}
    .d-row .lb {{ font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }}
    .d-row .vl {{ font-size: 14px; color: {COLORS['text_heading']}; font-weight: 600; }}

    .stAlert {{ border-radius: 12px !important; }}
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
    "forgot_stage": "start", "otp_token": None, "dev_otp_preview": None,
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
    <div class="pn-hero">
        <div class="logo">⚡</div>
        <h1>Infosys Portal</h1>
        <p>{subtitle or "Secure. Simple. Yours."}</p>
    </div>
    <div class="pn-subtitle">{title}</div>
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
            uid = st.text_input("Username or Email", key="login_uid", placeholder="you@infosys.com")
            pwd = st.text_input("Password", type="password", key="login_pwd", placeholder="••••••••")
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

            st.write("")
            with st.container(key="secondary_login_actions"):
                c1, c2 = st.columns(2)
                if c1.button("Create Account", key="to_signup"):
                    goto("Signup")
                if c2.button("Forgot Password", key="to_forgot"):
                    goto("Forgot")

        with tab_admin:
            if os.environ.get("ADMIN_USERNAME") is None or os.environ.get("ADMIN_PASSWORD") is None:
                st.warning(
                    "⚠️ `ADMIN_USERNAME`/`ADMIN_PASSWORD` aren't set — using the "
                    "built-in defaults. Set both as Colab Secrets and pass them to "
                    "the app before this goes anywhere real."
                )
            a_user = st.text_input("Admin Username", key="admin_uid", placeholder="admin")
            a_pwd = st.text_input("Admin Password", type="password", key="admin_pwd", placeholder="••••••••")
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
        uname = st.text_input("Username", placeholder="jane_doe")
        email = st.text_input("Email address", placeholder="you@infosys.com")
        pwd = st.text_input("Password", type="password", placeholder="Min. 8 characters",
                             help="Min 8 chars, upper, lower, number, symbol")
        cpwd = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
        sq = st.selectbox("Security Question", SECURITY_QUESTIONS)
        sa = st.text_input("Security Answer", placeholder="Your answer")

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

        with st.container(key="ghost_back_signup"):
            if st.button("← Back to Sign In"):
                goto("Login")

    # ---------------- FORGOT PASSWORD ----------------
    elif st.session_state.page == "Forgot":
        header("Reset your password", "Choose a verification method")

        if st.session_state.forgot_stage == "start":
            if not st.session_state.forgot_method:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"""
                    <div class="pn-card" style="text-align:center;min-height:150px;">
                        <div style="font-size:30px;">🔑</div>
                        <b>Security Question</b>
                        <p style="color:{COLORS['text_muted']};font-size:13px;">Answer the question you set at signup</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Use Security Question", key="pick_sq"):
                        st.session_state.forgot_method = "sq"
                        st.rerun()
                with c2:
                    st.markdown(f"""
                    <div class="pn-card" style="text-align:center;min-height:150px;">
                        <div style="font-size:30px;">📧</div>
                        <b>Email OTP</b>
                        <p style="color:{COLORS['text_muted']};font-size:13px;">Get a 6-digit code sent to your inbox</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Use Email OTP", key="pick_otp"):
                        st.session_state.forgot_method = "otp"
                        st.rerun()

            elif st.session_state.forgot_method == "sq":
                uname = st.text_input("Username", placeholder="jane_doe")
                if st.button("Continue →"):
                    if not uname.strip():
                        st.error("⚠️ Username is required.")
                    else:
                        q = db.get_security_question(uname.strip())
                        if q:
                            st.session_state.forgot_username = uname.strip()
                            st.session_state.forgot_stage = "verify"
                            st.rerun()
                        else:
                            st.error("❌ No account found with that username.")
                with st.container(key="ghost_back_sq"):
                    if st.button("← Choose a different method", key="back_from_sq"):
                        st.session_state.forgot_method = None
                        st.rerun()

            else:  # otp
                email = st.text_input("Registered email address", placeholder="you@infosys.com")
                if st.button("Send OTP →"):
                    if not email.strip():
                        st.error("⚠️ Email is required.")
                    elif not validate_email(email):
                        st.error("❌ Enter a valid email address.")
                    elif not db.get_user_by_email(email.strip()):
                        st.error("❌ Email not registered.")
                    else:
                        otp = generate_otp()
                        st.session_state.forgot_email = email.strip().lower()
                        st.session_state.otp_token = make_otp_token(email.strip().lower(), otp)
                        st.session_state.forgot_stage = "verify"

                        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
                            # Email isn't configured yet — don't dead-end the test.
                            # Show the OTP directly so the flow can still be verified.
                            st.session_state.dev_otp_preview = otp
                            st.rerun()
                        else:
                            with st.spinner("Sending OTP..."):
                                ok, msg = send_otp_email(email.strip(), otp)
                            if ok:
                                st.session_state.dev_otp_preview = None
                                st.success("✅ OTP sent — check your inbox (and spam folder).")
                                time.sleep(1)
                                st.rerun()
                            else:
                                # Sending failed — still let them continue and test,
                                # but surface the OTP so they aren't stuck.
                                st.session_state.dev_otp_preview = otp
                                st.warning(f"⚠️ Couldn't email the OTP ({msg}). Showing it below so you can still test.")
                                time.sleep(1.5)
                                st.rerun()
                with st.container(key="ghost_back_otp"):
                    if st.button("← Choose a different method", key="back_from_otp"):
                        st.session_state.forgot_method = None
                        st.session_state.dev_otp_preview = None
                        st.rerun()

        elif st.session_state.forgot_stage == "verify":
            if st.session_state.forgot_method == "sq":
                q = db.get_security_question(st.session_state.forgot_username)
                st.info(f"❓ {q}")
                ans = st.text_input("Your answer", placeholder="Type your answer")
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
                if st.session_state.dev_otp_preview:
                    st.markdown(f"""
                    <div class="pn-card" style="text-align:center;border:1.5px dashed {COLORS['accent']};">
                        <div style="font-size:12px;color:{COLORS['text_muted']};font-weight:700;letter-spacing:0.5px;">
                            🧪 TESTING MODE — EMAIL NOT CONFIGURED, HERE'S YOUR CODE
                        </div>
                        <div style="font-size:28px;font-weight:800;letter-spacing:6px;color:{COLORS['accent']};margin-top:6px;">
                            {st.session_state.dev_otp_preview}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("")
                otp_in = st.text_input("6-digit OTP", max_chars=6, placeholder="e.g. 849201")
                if st.button("Verify →"):
                    if not otp_in.strip():
                        st.error("⚠️ OTP is required.")
                    else:
                        ok, msg = verify_otp_token(st.session_state.otp_token, otp_in.strip(), st.session_state.forgot_email)
                        if ok:
                            st.session_state.forgot_stage = "reset"
                            st.session_state.dev_otp_preview = None
                            st.rerun()
                        else:
                            st.error("❌ " + msg)

        elif st.session_state.forgot_stage == "reset":
            npw = st.text_input("New Password", type="password", placeholder="Min. 8 characters")
            cnpw = st.text_input("Confirm New Password", type="password", placeholder="Re-enter new password")
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

        with st.container(key="ghost_cancel"):
            if st.button("← Cancel"):
                st.session_state.forgot_stage = "start"
                st.session_state.forgot_method = None
                st.session_state.dev_otp_preview = None
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
    initials = "".join([w[0] for w in who.replace(".", " ").replace("_", " ").split()][:2]).upper() or who[:2].upper()

    with st.sidebar:
        st.markdown(f"""
        <div class="sb-profile">
            <div class="sb-avatar">{initials}</div>
            <div class="sb-name">{'Administrator' if role == 'admin' else who}</div>
            <div class="sb-role">{'Admin access' if role == 'admin' else 'Member'}</div>
        </div>
        <hr style="border-color:{COLORS['border']};margin:14px 0;">
        """, unsafe_allow_html=True)
        st.markdown("### ⚡ Infosys Portal")
        if st.button("Logout"):
            logout()

    if role == "admin":
        st.markdown(f"""
        <div class="dash-banner">
            <div>
                <h2>🛡️ Admin Dashboard</h2>
                <div class="sub">Everyone who has registered — passwords are never shown here</div>
            </div>
            <div class="dash-pill">
                <div class="dash-avatar">{initials}</div>
                <span>Administrator</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        users = db.list_all_users()
        c1, c2 = st.columns(2)
        c1.markdown(f"""<div class="stat-card">
            <div class="icon">👥</div>
            <div class="val">{len(users)}</div>
            <div class="lbl">REGISTERED USERS</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-card">
            <div class="icon">🟢</div>
            <div class="val">Active</div>
            <div class="lbl">SYSTEM STATUS</div>
        </div>""", unsafe_allow_html=True)

        st.write("")
        if users:
            search = st.text_input("Search users", placeholder="🔎 Search by username or email", label_visibility="collapsed")
            q = search.strip().lower()
            filtered = [
                (u, e, c) for u, e, c in users
                if not q or q in u.lower() or q in e.lower()
            ]

            rows_html = ""
            for u, e, c in filtered:
                ini = "".join([w[0] for w in u.replace(".", " ").replace("_", " ").split()][:2]).upper() or u[:2].upper()
                joined = c.split("T")[0] if "T" in c else c
                rows_html += f"""
                <div class="u-row">
                    <div class="u-avatar">{ini}</div>
                    <div>
                        <div class="u-name">{u}</div>
                        <div class="u-email">{e}</div>
                    </div>
                    <div class="u-joined">Joined {joined}</div>
                </div>"""

            if filtered:
                st.markdown(f'<div class="u-table">{rows_html}</div>', unsafe_allow_html=True)
            else:
                st.info("No users match that search.")
        else:
            st.info("No users have registered yet.")
    else:
        user_row = db.get_user_by_username(who)
        email = user_row[2] if user_row else "—"
        sec_q = user_row[4] if user_row else "—"

        st.markdown(f"""
        <div class="dash-banner">
            <div>
                <h2>👋 Welcome, {who}!</h2>
                <div class="sub">Here's your account overview</div>
            </div>
            <div class="dash-pill">
                <div class="dash-avatar">{initials}</div>
                <span>{who}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        for col, icon, label, value in [
            (c1, "🔐", "Session", "Active"),
            (c2, "⏱️", "Valid for", f"{SESSION_HOURS}h"),
            (c3, "🛡️", "Auth type", "JWT"),
        ]:
            col.markdown(f"""
            <div class="stat-card">
                <div class="icon">{icon}</div>
                <div class="val">{value}</div>
                <div class="lbl">{label.upper()}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown(f"""
        <div class="pn-card">
            <div style="font-weight:700;font-size:15px;margin-bottom:6px;">Account details</div>
            <div class="d-row">
                <div class="ic">👤</div>
                <div><div class="lb">Username</div><div class="vl">{who}</div></div>
            </div>
            <div class="d-row">
                <div class="ic">✉️</div>
                <div><div class="lb">Email</div><div class="vl">{email}</div></div>
            </div>
            <div class="d-row">
                <div class="ic">❓</div>
                <div><div class="lb">Security question</div><div class="vl">{sec_q}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        st.markdown(f"""
        <div class="pn-card">
            <p style="margin:0;">🔒 You're securely logged in via a signed JWT session token.
            Nothing about your password is stored anywhere except as a one-way hash.</p>
        </div>
        """, unsafe_allow_html=True)
