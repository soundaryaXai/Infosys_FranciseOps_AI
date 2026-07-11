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
import bcrypt
import streamlit as st

# ────────────────────────────────────────────────────────────────
# IN-MEMORY DATA STORE — no external database.
#
# @st.cache_resource makes this dict persist across Streamlit reruns
# (a plain module-level variable would get wiped every rerun, since
# Streamlit re-executes the script top-to-bottom on every interaction).
# It's shared for as long as this server process keeps running, and is
# reset if the process restarts — there is no file/db on disk.
# ────────────────────────────────────────────────────────────────
@st.cache_resource
def _store():
    return {"users": {}}  # username -> record dict


def _hash(text: str) -> str:
    return bcrypt.hashpw(text.encode(), bcrypt.gensalt()).decode()


def _check(text: str, hashed: str) -> bool:
    if not hashed or not text:
        return False
    try:
        return bcrypt.checkpw(text.encode(), hashed.encode())
    except ValueError:
        return False


def username_exists(username: str) -> bool:
    return username in _store()["users"]


def email_exists(email: str) -> bool:
    email = email.strip().lower()
    return any(rec["email"] == email for rec in _store()["users"].values())


def create_user(username, email, password, security_question, security_answer):
    username = username.strip()
    email = email.strip().lower()

    if username_exists(username):
        return False, "That username is already taken. Please choose another."
    if email_exists(email):
        return False, "That email is already registered. Try logging in instead."

    _store()["users"][username] = {
        "email": email,
        "password_hash": _hash(password),
        "security_question": security_question,
        "security_answer_hash": _hash(security_answer.strip().lower()),
        "created_at": datetime.datetime.utcnow().isoformat(timespec="seconds"),
    }
    return True, "Account created successfully."


def get_user_by_username(username: str):
    rec = _store()["users"].get(username)
    if not rec:
        return None
    return (username, rec["email"], rec["security_question"])


def get_user_by_email(email: str):
    email = email.strip().lower()
    for uname, rec in _store()["users"].items():
        if rec["email"] == email:
            return (uname, rec["email"], rec["security_question"])
    return None


def verify_login(identifier: str, password: str):
    identifier_l = identifier.strip().lower()
    for uname, rec in _store()["users"].items():
        if uname == identifier or rec["email"] == identifier_l:
            if _check(password, rec["password_hash"]):
                return True, uname, rec["email"]
    return False, None, None


def get_security_question(username: str):
    rec = _store()["users"].get(username)
    return rec["security_question"] if rec else None


def verify_security_answer(username: str, answer: str) -> bool:
    rec = _store()["users"].get(username)
    if not rec:
        return False
    return _check(answer.strip().lower(), rec["security_answer_hash"])


def reset_password_by_username(username: str, new_password: str):
    rec = _store()["users"].get(username)
    if rec:
        rec["password_hash"] = _hash(new_password)


def reset_password_by_email(email: str, new_password: str):
    email = email.strip().lower()
    for rec in _store()["users"].values():
        if rec["email"] == email:
            rec["password_hash"] = _hash(new_password)
            return


def list_all_users():
    """Admin-only. Never returns password data."""
    return [
        (uname, rec["email"], rec["created_at"])
        for uname, rec in _store()["users"].items()
    ]

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
APP_NAME = "Aegis Portal"
TAGLINE = "Secure identity, simplified."

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-fallback-secret-change-me")
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
OTP_EXPIRY_MINUTES = 5
SESSION_HOURS = 2

# Admin login is separate from the signup system (Step 11) — it is never
# a row in the users table. Credentials come from environment variables
# (set ADMIN_USERNAME / ADMIN_PASSWORD in Colab Secrets, same as the other
# secrets) so nothing sensitive is hardcoded here. The fallbacks below
# only exist so the app still runs during local testing.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
ADMIN_USES_FALLBACK = "ADMIN_USERNAME" not in os.environ or "ADMIN_PASSWORD" not in os.environ

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What was the name of your first school?",
]

# ────────────────────────────────────────────────────────────────
# THEME — forced light, so the UI is consistent regardless of the
# viewer's system/browser theme preference.
# ────────────────────────────────────────────────────────────────
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

st.set_page_config(page_title=APP_NAME, layout="centered")

COLORS = {
    "bg_main": "#f6f5ff", "bg_card": "#ffffff", "bg_card_alt": "#eee9ff",
    "text_main": "#1e1b34", "text_heading": "#1e1b34", "text_muted": "#6b6785",
    "accent": "#7c5cff", "accent_hover": "#6a4ce0", "accent_text": "#ffffff",
    "border": "#e2defa", "border_strong": "#7c5cff", "danger": "#e0455f",
    "success": "#1fae6e",
}

# ────────────────────────────────────────────────────────────────
# ICONS — hand-drawn inline SVGs (no emoji, anywhere)
# ────────────────────────────────────────────────────────────────
ICON_PATHS = {
    "shield": '<path d="M12 3l7 3v5c0 5-3.5 9-7 10-3.5-1-7-5-7-10V6l7-3z"/>',
    "user": '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5"/>',
    "users": '<circle cx="8.5" cy="9" r="3"/><circle cx="16" cy="10" r="2.5"/>'
             '<path d="M3 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/><path d="M14.2 14.3c2.6.2 4.8 2 4.8 4.7"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5L12 13l8.5-6.5"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="9" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M19 19l-4.3-4.3"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.3 9.3a2.7 2.7 0 1 1 3.6 2.5c-.8.4-1.2.9-1.2 1.7"/>'
            '<circle cx="12" cy="16.6" r="0.35" fill="currentColor" stroke="none"/>',
    "flask": '<path d="M9.5 3h5M10.2 3v6l-4.6 8.2A1.8 1.8 0 0 0 7.2 20h9.6a1.8 1.8 0 0 0 1.6-2.8L13.8 9V3"/>',
    "check": '<path d="M5 13l4.5 4.5L19 8"/>',
    "alert": '<path d="M12 8.5v5"/><circle cx="12" cy="16.3" r="0.35" fill="currentColor" stroke="none"/>'
             '<path d="M10.6 3.7 2.9 17.4A1.8 1.8 0 0 0 4.5 20h15a1.8 1.8 0 0 0 1.6-2.6L13.4 3.7a1.8 1.8 0 0 0-2.8 0Z"/>',
    "key": '<circle cx="8" cy="15" r="3.2"/><path d="M10.3 12.7 18 5l2 2-1.6 1.6 1.6 1.6-2 2-1.6-1.6L14 12.9"/>',
    "activity": '<path d="M3 12h4l2.5-7L13 19l2.5-7H21"/>',
}


def icon(name, size=18, color="currentColor", stroke=1.8):
    body = ICON_PATHS.get(name, "")
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">{body}</svg>'
    )


# ────────────────────────────────────────────────────────────────
# STYLES
# ────────────────────────────────────────────────────────────────
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

    label, label p, label span, .stMarkdown p {{
        color: {COLORS['text_heading']} !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }}

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
        box-shadow: 0 8px 20px rgba(124,92,255,0.35);
    }}
    .pn-hero h1 {{ font-size: 1.7rem !important; margin: 0; }}
    .pn-hero p {{ color: {COLORS['text_muted']}; font-size: 13px; margin: 4px 0 0; }}
    .pn-subtitle {{ text-align:center; font-weight:700; font-size:1.1rem; margin-bottom:18px; color:{COLORS['text_heading']}; }}

    .dash-banner {{
        background: linear-gradient(120deg, #1e1b34 0%, #3a2f6b 100%);
        border-radius: 20px; padding: 26px 32px;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 26px; box-shadow: 0 14px 34px rgba(30,27,52,0.25);
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

    .stat-card {{
        background: {COLORS['bg_card']}; border: 1.5px solid {COLORS['border']};
        border-radius: 16px; padding: 18px; text-align: center;
        box-shadow: 0 6px 18px rgba(30,27,52,0.05);
    }}
    .stat-card .icon-wrap {{
        width: 34px; height: 34px; border-radius: 10px; margin: 0 auto 8px;
        background: {COLORS['bg_card_alt']}; color: {COLORS['accent']};
        display: flex; align-items: center; justify-content: center;
    }}
    .stat-card .val {{ font-size: 20px; font-weight: 800; color: {COLORS['text_heading']}; }}
    .stat-card .lbl {{ font-size: 11px; color: {COLORS['text_muted']}; font-weight: 600; margin-top: 2px; letter-spacing: 0.3px; }}

    .status-dot {{
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: {COLORS['success']}; margin-right: 6px;
    }}

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
    .sb-brand {{ display:flex; align-items:center; gap:8px; font-weight:700; color:{COLORS['text_heading']}; font-size:14px; }}

    .u-table {{
        background: {COLORS['bg_card']}; border: 1.5px solid {COLORS['border']};
        border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(30,27,52,0.05);
    }}
    .u-row {{ display: flex; align-items: center; gap: 14px; padding: 14px 20px; border-bottom: 1px solid {COLORS['border']}; }}
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

    .d-row {{ display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid {COLORS['border']}; }}
    .d-row:last-child {{ border-bottom: none; }}
    .d-row .ic {{
        width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; color: {COLORS['accent']};
        background: {COLORS['bg_card_alt']}; display: flex; align-items: center; justify-content: center;
    }}
    .d-row .lb {{ font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }}
    .d-row .vl {{ font-size: 14px; color: {COLORS['text_heading']}; font-weight: 600; }}

    .card-title {{ display:flex; align-items:center; gap:8px; font-weight:700; font-size:15px; margin-bottom:10px; color:{COLORS['text_heading']}; }}
    .card-title .ic {{ color: {COLORS['accent']}; display:flex; }}

    .field-msg {{ font-size: 12.5px; margin: -6px 0 12px 2px; display:flex; align-items:center; gap:5px; }}
    .field-msg.err {{ color: {COLORS['danger']}; }}
    .field-msg.ok {{ color: {COLORS['success']}; }}
    .field-msg .ic {{ display:flex; flex-shrink:0; }}

    .method-card {{
        background: {COLORS['bg_card']}; border: 1.5px solid {COLORS['border']};
        border-radius: 16px; padding: 20px; text-align: center; margin-bottom: 10px;
    }}
    .method-card .ic-wrap {{
        width: 46px; height: 46px; border-radius: 12px; margin: 0 auto 10px;
        background: {COLORS['bg_card_alt']}; color: {COLORS['accent']};
        display: flex; align-items: center; justify-content: center;
    }}
    .method-card .t {{ font-weight: 700; font-size: 14px; color: {COLORS['text_heading']}; margin-bottom: 4px; }}
    .method-card .d {{ font-size: 12px; color: {COLORS['text_muted']}; }}

    .otp-preview {{
        text-align:center; border: 1.5px dashed {COLORS['accent']}; border-radius: 16px;
        padding: 16px; background: {COLORS['bg_card']}; margin-bottom: 6px;
    }}
    .otp-preview .lbl {{ font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; letter-spacing: 0.4px; }}
    .otp-preview .val {{ font-size: 28px; font-weight: 800; letter-spacing: 6px; color: {COLORS['accent']}; margin-top: 6px; }}

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
    return [name for name, val in fields.items() if not str(val).strip()]


def field_msg(key):
    """Render live validation feedback for a field, set via an on_change callback."""
    fb = st.session_state.get(key)
    if not fb:
        return
    level, msg = fb
    cls = "ok" if level == "ok" else "err"
    ic = icon("check", 13) if level == "ok" else icon("alert", 13)
    st.markdown(f'<div class="field-msg {cls}"><span class="ic">{ic}</span>{msg}</div>', unsafe_allow_html=True)


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
    otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    payload = {
        "sub": email,
        "otp_hash": otp_hash,
        "type": "password_reset_otp",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_otp_token(token: str, input_otp: str, email: str):
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
    msg["From"] = f"{APP_NAME} <{EMAIL_ADDRESS}>"
    msg["To"] = to_email
    msg["Subject"] = f"{APP_NAME} — Your Verification Code"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    text_body = (
        f"Your {APP_NAME} verification code is: {otp}\n"
        f"It expires in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you did not request this, you can ignore this email."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;border:2px solid #1e1b34;
                border-radius:12px;padding:28px;text-align:center;">
        <h2 style="color:#1e1b34;margin-top:0;">{APP_NAME} Verification</h2>
        <p style="color:#4a5568;">Use the code below to reset your password:</p>
        <div style="background:#7c5cff;color:#ffffff;font-size:26px;font-weight:700;letter-spacing:6px;
                    padding:14px;border-radius:8px;display:inline-block;">{otp}</div>
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
        <div class="logo">{icon('shield', 28, '#ffffff')}</div>
        <h1>{APP_NAME}</h1>
        <p>{subtitle or TAGLINE}</p>
    </div>
    <div class="pn-subtitle">{title}</div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
# LIVE FIELD VALIDATION — fires as each field is completed (on_change),
# not only when the form is submitted.
# ────────────────────────────────────────────────────────────────
def check_signup_username():
    v = st.session_state.get("signup_username", "").strip()
    if not v:
        st.session_state["fb_su_username"] = ("err", "Username is required.")
    elif username_exists(v):
        st.session_state["fb_su_username"] = ("err", "This username is already taken.")
    else:
        st.session_state["fb_su_username"] = ("ok", "Username is available.")


def check_signup_email():
    v = st.session_state.get("signup_email", "").strip()
    if not v:
        st.session_state["fb_su_email"] = ("err", "Email is required.")
    elif not validate_email(v):
        st.session_state["fb_su_email"] = ("err", "Enter a valid email, e.g. name@example.com")
    elif email_exists(v):
        st.session_state["fb_su_email"] = ("err", "This email is already registered.")
    else:
        st.session_state["fb_su_email"] = ("ok", "Email looks good.")


def check_signup_password():
    v = st.session_state.get("signup_password", "")
    problems = validate_password(v)
    if not v:
        st.session_state["fb_su_password"] = ("err", "Password is required.")
    elif problems:
        st.session_state["fb_su_password"] = ("err", "Needs " + ", ".join(problems) + ".")
    else:
        st.session_state["fb_su_password"] = ("ok", "Strong password.")
    check_signup_confirm()


def check_signup_confirm():
    v = st.session_state.get("signup_confirm", "")
    pwd = st.session_state.get("signup_password", "")
    if not v:
        st.session_state["fb_su_confirm"] = ("err", "Please confirm your password.")
    elif v != pwd:
        st.session_state["fb_su_confirm"] = ("err", "Passwords do not match.")
    else:
        st.session_state["fb_su_confirm"] = ("ok", "Passwords match.")


def check_signup_answer():
    v = st.session_state.get("signup_answer", "").strip()
    if not v:
        st.session_state["fb_su_answer"] = ("err", "Security answer is required.")
    else:
        st.session_state["fb_su_answer"] = ("ok", "Looks good.")


def check_reset_password():
    v = st.session_state.get("reset_npw", "")
    problems = validate_password(v)
    if not v:
        st.session_state["fb_rs_password"] = ("err", "Password is required.")
    elif problems:
        st.session_state["fb_rs_password"] = ("err", "Needs " + ", ".join(problems) + ".")
    else:
        st.session_state["fb_rs_password"] = ("ok", "Strong password.")
    check_reset_confirm()


def check_reset_confirm():
    v = st.session_state.get("reset_cnpw", "")
    pwd = st.session_state.get("reset_npw", "")
    if not v:
        st.session_state["fb_rs_confirm"] = ("err", "Please confirm your password.")
    elif v != pwd:
        st.session_state["fb_rs_confirm"] = ("err", "Passwords do not match.")
    else:
        st.session_state["fb_rs_confirm"] = ("ok", "Passwords match.")


# ════════════════════════════════════════════════════════════════
# LOGGED-OUT ROUTES
# ════════════════════════════════════════════════════════════════
if not st.session_state.token:

    if st.session_state.page not in ("Login", "Signup", "Forgot"):
        st.session_state.page = "Login"

    # ---------------- LOGIN (unified — one form for users and admin) ----------------
    if st.session_state.page == "Login":
        header("Sign in to your account")

        if ADMIN_USES_FALLBACK:
            st.markdown(f"""
            <div class="field-msg err" style="justify-content:center;margin-bottom:14px;">
                <span class="ic">{icon('alert', 13)}</span>
                Admin credentials are using local defaults — set ADMIN_USERNAME / ADMIN_PASSWORD before deploying.
            </div>
            """, unsafe_allow_html=True)

        uid = st.text_input("Username or Email", key="login_uid", placeholder="you@example.com")
        pwd = st.text_input("Password", type="password", key="login_pwd", placeholder="••••••••")

        if st.button("Sign In →", key="login_btn"):
            missing = require_fields(**{"Username/Email": uid, "Password": pwd})
            if missing:
                st.error(f"Required: {', '.join(missing)}")
            elif uid.strip() == ADMIN_USERNAME and pwd == ADMIN_PASSWORD:
                st.session_state.token = make_session_jwt(ADMIN_USERNAME, "admin")
                st.session_state.role = "admin"
                goto("Dashboard")
            else:
                ok, username, email = verify_login(uid.strip(), pwd)
                if ok:
                    st.session_state.token = make_session_jwt(username, "user")
                    st.session_state.role = "user"
                    goto("Dashboard")
                else:
                    # Deliberately generic — never reveal which field was wrong.
                    st.error("Invalid username/email or password.")

        st.write("")
        with st.container(key="secondary_login_actions"):
            c1, c2 = st.columns(2)
            if c1.button("Create Account", key="to_signup"):
                goto("Signup")
            if c2.button("Forgot Password", key="to_forgot"):
                goto("Forgot")

    # ---------------- SIGNUP (live per-field validation) ----------------
    elif st.session_state.page == "Signup":
        header("Create an account", f"Join {APP_NAME}")

        uname = st.text_input("Username", placeholder="jane_doe", key="signup_username", on_change=check_signup_username)
        field_msg("fb_su_username")

        email = st.text_input("Email address", placeholder="you@example.com", key="signup_email", on_change=check_signup_email)
        field_msg("fb_su_email")

        pwd = st.text_input("Password", type="password", placeholder="Min. 8 characters", key="signup_password",
                             on_change=check_signup_password,
                             help="Min 8 chars, upper, lower, number, symbol")
        field_msg("fb_su_password")

        cpwd = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="signup_confirm",
                              on_change=check_signup_confirm)
        field_msg("fb_su_confirm")

        sq = st.selectbox("Security Question", SECURITY_QUESTIONS)
        sa = st.text_input("Security Answer", placeholder="Your answer", key="signup_answer", on_change=check_signup_answer)
        field_msg("fb_su_answer")

        if st.button("Create Account →"):
            check_signup_username()
            check_signup_email()
            check_signup_password()
            check_signup_answer()
            all_ok = all(
                st.session_state.get(k, ("err", ""))[0] == "ok"
                for k in ("fb_su_username", "fb_su_email", "fb_su_password", "fb_su_confirm", "fb_su_answer")
            )
            if not all_ok:
                st.error("Please fix the highlighted fields before continuing.")
            else:
                ok, message = create_user(uname, email, pwd, sq, sa)
                if ok:
                    st.success(message + " Please log in.")
                    time.sleep(1.2)
                    goto("Login")
                else:
                    st.error(message)

        with st.container(key="ghost_back_signup"):
            if st.button("← Back to Sign In"):
                goto("Login")

    # ---------------- FORGOT PASSWORD ----------------
    elif st.session_state.page == "Forgot":
        header("Reset your password", "Choose a verification method")

        if st.session_state.forgot_stage == "start":
            if st.session_state.forgot_method is None:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"""
                    <div class="method-card">
                        <div class="ic-wrap">{icon('key', 22)}</div>
                        <div class="t">Security Question</div>
                        <div class="d">Answer the question you set at signup</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("Use Security Question", key="pick_sq"):
                        st.session_state.forgot_method = "sq"
                        st.rerun()
                with c2:
                    st.markdown(f"""
                    <div class="method-card">
                        <div class="ic-wrap">{icon('mail', 22)}</div>
                        <div class="t">Email OTP</div>
                        <div class="d">Get a 6-digit code sent to your email</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("Use Email OTP", key="pick_otp"):
                        st.session_state.forgot_method = "otp"
                        st.rerun()

            elif st.session_state.forgot_method == "sq":
                uname = st.text_input("Username", placeholder="jane_doe")
                if st.button("Continue →"):
                    if not uname.strip():
                        st.error("Username is required.")
                    else:
                        q = get_security_question(uname.strip())
                        if q:
                            st.session_state.forgot_username = uname.strip()
                            st.session_state.forgot_stage = "verify"
                            st.rerun()
                        else:
                            st.error("No account found with that username.")
                with st.container(key="ghost_back_sq"):
                    if st.button("← Choose a different method", key="back_from_sq"):
                        st.session_state.forgot_method = None
                        st.rerun()

            else:  # otp
                email = st.text_input("Registered email address", placeholder="you@example.com")
                if st.button("Send OTP →"):
                    if not email.strip():
                        st.error("Email is required.")
                    elif not validate_email(email):
                        st.error("Enter a valid email address.")
                    elif not get_user_by_email(email.strip()):
                        st.error("Email not registered.")
                    else:
                        otp = generate_otp()
                        st.session_state.forgot_email = email.strip().lower()
                        st.session_state.otp_token = make_otp_token(email.strip().lower(), otp)
                        st.session_state.forgot_stage = "verify"

                        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
                            st.session_state.dev_otp_preview = otp
                            st.rerun()
                        else:
                            with st.spinner("Sending OTP..."):
                                ok, msg = send_otp_email(email.strip(), otp)
                            if ok:
                                st.session_state.dev_otp_preview = None
                                st.success("OTP sent — check your inbox (and spam folder).")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.session_state.dev_otp_preview = otp
                                st.warning(f"Couldn't email the OTP ({msg}). Showing it below so you can still test.")
                                time.sleep(1.5)
                                st.rerun()
                with st.container(key="ghost_back_otp"):
                    if st.button("← Choose a different method", key="back_from_otp"):
                        st.session_state.forgot_method = None
                        st.session_state.dev_otp_preview = None
                        st.rerun()

        elif st.session_state.forgot_stage == "verify":
            if st.session_state.forgot_method == "sq":
                q = get_security_question(st.session_state.forgot_username)
                st.info(q)
                ans = st.text_input("Your answer", placeholder="Type your answer")
                if st.button("Verify →"):
                    if not ans.strip():
                        st.error("Answer is required.")
                    elif verify_security_answer(st.session_state.forgot_username, ans):
                        st.session_state.forgot_stage = "reset"
                        st.rerun()
                    else:
                        st.error("Incorrect answer.")
            else:
                st.info(f"Code sent to {st.session_state.forgot_email} (valid {OTP_EXPIRY_MINUTES} min).")
                if st.session_state.dev_otp_preview:
                    st.markdown(f"""
                    <div class="otp-preview">
                        <div class="lbl">TESTING MODE — EMAIL NOT CONFIGURED, HERE IS YOUR CODE</div>
                        <div class="val">{st.session_state.dev_otp_preview}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("")
                otp_in = st.text_input("6-digit OTP", max_chars=6, placeholder="e.g. 849201")
                if st.button("Verify →"):
                    if not otp_in.strip():
                        st.error("OTP is required.")
                    else:
                        ok, msg = verify_otp_token(st.session_state.otp_token, otp_in.strip(), st.session_state.forgot_email)
                        if ok:
                            st.session_state.forgot_stage = "reset"
                            st.session_state.dev_otp_preview = None
                            st.rerun()
                        else:
                            st.error(msg)
            st.write("")
            with st.container(key="ghost_verify_cancel"):
                if st.button("← Cancel", key="cancel_verify"):
                    st.session_state.forgot_stage = "start"
                    st.session_state.forgot_method = None
                    st.session_state.dev_otp_preview = None
                    goto("Login")

        elif st.session_state.forgot_stage == "reset":
            npw = st.text_input("New Password", type="password", placeholder="Min. 8 characters",
                                 key="reset_npw", on_change=check_reset_password)
            field_msg("fb_rs_password")
            cnpw = st.text_input("Confirm New Password", type="password", placeholder="Re-enter new password",
                                  key="reset_cnpw", on_change=check_reset_confirm)
            field_msg("fb_rs_confirm")

            if st.button("Update Password →"):
                check_reset_password()
                all_ok = all(
                    st.session_state.get(k, ("err", ""))[0] == "ok"
                    for k in ("fb_rs_password", "fb_rs_confirm")
                )
                if not all_ok:
                    st.error("Please fix the highlighted fields before continuing.")
                else:
                    if st.session_state.forgot_method == "sq":
                        reset_password_by_username(st.session_state.forgot_username, npw)
                    else:
                        reset_password_by_email(st.session_state.forgot_email, npw)
                    st.success("Password updated. Please log in.")
                    time.sleep(1.2)
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
    initials = "".join([w[0] for w in who.replace(".", " ").replace("_", " ").split()][:2]).upper() or who[:2].upper()

    with st.sidebar:
        st.markdown(f"""
        <div class="sb-profile">
            <div class="sb-avatar">{initials}</div>
            <div class="sb-name">{'Administrator' if role == 'admin' else who}</div>
            <div class="sb-role">{'Admin access' if role == 'admin' else 'Member'}</div>
        </div>
        <hr style="border-color:{COLORS['border']};margin:14px 0;">
        <div class="sb-brand">{icon('shield', 18, COLORS['accent'])} {APP_NAME}</div>
        <div style="height:14px;"></div>
        """, unsafe_allow_html=True)
        if st.button("Logout"):
            logout()

    if role == "admin":
        st.markdown(f"""
        <div class="dash-banner">
            <div>
                <h2>Admin Dashboard</h2>
                <div class="sub">Everyone who has registered — passwords are never shown here</div>
            </div>
            <div class="dash-pill">
                <div class="dash-avatar">{initials}</div>
                <span>Administrator</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        users = list_all_users()
        c1, c2 = st.columns(2)
        c1.markdown(f"""<div class="stat-card">
            <div class="icon-wrap">{icon('users', 18)}</div>
            <div class="val">{len(users)}</div>
            <div class="lbl">REGISTERED USERS</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-card">
            <div class="icon-wrap">{icon('activity', 18)}</div>
            <div class="val"><span class="status-dot"></span>Active</div>
            <div class="lbl">SYSTEM STATUS</div>
        </div>""", unsafe_allow_html=True)

        st.write("")
        if users:
            search = st.text_input("Search users", placeholder="Search by username or email", label_visibility="collapsed")
            q = search.strip().lower()
            filtered = [(u, e, c) for u, e, c in users if not q or q in u.lower() or q in e.lower()]

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
        user_row = get_user_by_username(who)
        email = user_row[1] if user_row else "—"
        sec_q = user_row[2] if user_row else "—"

        issued = datetime.datetime.utcfromtimestamp(payload["iat"]) if isinstance(payload.get("iat"), (int, float)) else None
        expires = datetime.datetime.utcfromtimestamp(payload["exp"]) if isinstance(payload.get("exp"), (int, float)) else None
        remaining = ""
        if expires:
            delta = expires - datetime.datetime.utcnow()
            mins = max(int(delta.total_seconds() // 60), 0)
            remaining = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"

        st.markdown(f"""
        <div class="dash-banner">
            <div>
                <h2>Welcome back, {who}</h2>
                <div class="sub">Here is your account overview</div>
            </div>
            <div class="dash-pill">
                <div class="dash-avatar">{initials}</div>
                <span>{who}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        stat_defs = [
            (c1, "lock", "Auth type", "JWT"),
            (c2, "clock", "Time left", remaining or "—"),
            (c3, "shield", "Session", "Active"),
        ]
        for col, ic_name, label, value in stat_defs:
            col.markdown(f"""
            <div class="stat-card">
                <div class="icon-wrap">{icon(ic_name, 18)}</div>
                <div class="val">{value}</div>
                <div class="lbl">{label.upper()}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown(f"""
        <div class="pn-card">
            <div class="card-title"><span class="ic">{icon('user', 18)}</span>Account details</div>
            <div class="d-row">
                <div class="ic">{icon('user', 16)}</div>
                <div><div class="lb">Username</div><div class="vl">{who}</div></div>
            </div>
            <div class="d-row">
                <div class="ic">{icon('mail', 16)}</div>
                <div><div class="lb">Email</div><div class="vl">{email}</div></div>
            </div>
            <div class="d-row">
                <div class="ic">{icon('help', 16)}</div>
                <div><div class="lb">Security question</div><div class="vl">{sec_q}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        issued_s = issued.strftime("%d %b %Y, %H:%M UTC") if issued else "—"
        expires_s = expires.strftime("%d %b %Y, %H:%M UTC") if expires else "—"
        st.markdown(f"""
        <div class="pn-card">
            <div class="card-title"><span class="ic">{icon('clock', 18)}</span>Session information</div>
            <div class="d-row">
                <div class="ic">{icon('lock', 16)}</div>
                <div><div class="lb">Signed in at</div><div class="vl">{issued_s}</div></div>
            </div>
            <div class="d-row">
                <div class="ic">{icon('clock', 16)}</div>
                <div><div class="lb">Session expires</div><div class="vl">{expires_s}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
