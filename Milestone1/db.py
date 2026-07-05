"""
db.py — SQLite data layer for the Infosys Springboard Milestone 1
User Authentication Module.

Stores: username, email, bcrypt password hash, security question,
bcrypt-hashed security answer. No plaintext secrets are ever stored.
"""

import sqlite3
import bcrypt
import datetime

DB_NAME = "portal.db"


def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            security_question TEXT NOT NULL,
            security_answer_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


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
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row is not None


def email_exists(email: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row is not None


def create_user(username, email, password, security_question, security_answer):
    """Returns (success: bool, message: str)."""
    username = username.strip()
    email = email.strip().lower()

    if username_exists(username):
        return False, "That username is already taken. Please choose another."
    if email_exists(email):
        return False, "That email is already registered. Try logging in instead."

    conn = get_conn()
    conn.execute(
        """INSERT INTO users
           (username, email, password_hash, security_question, security_answer_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            username,
            email,
            _hash(password),
            security_question,
            _hash(security_answer.strip().lower()),
            datetime.datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return True, "Account created successfully."


def get_user_by_username(username: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, email, password_hash, security_question, security_answer_hash "
        "FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return row


def get_user_by_email(email: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, email, password_hash, security_question, security_answer_hash "
        "FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    return row


def verify_login(identifier: str, password: str):
    """identifier can be username OR email. Returns (ok, username, email)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT username, email, password_hash FROM users WHERE username = ? OR email = ?",
        (identifier, identifier.strip().lower()),
    ).fetchone()
    conn.close()
    if row and _check(password, row[2]):
        return True, row[0], row[1]
    return False, None, None


def get_security_question(username: str):
    row = get_user_by_username(username)
    return row[4] if row else None


def verify_security_answer(username: str, answer: str) -> bool:
    row = get_user_by_username(username)
    if not row:
        return False
    return _check(answer, row[5])


def reset_password_by_username(username: str, new_password: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (_hash(new_password), username),
    )
    conn.commit()
    conn.close()


def reset_password_by_email(email: str, new_password: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE email = ?",
        (_hash(new_password), email.strip().lower()),
    )
    conn.commit()
    conn.close()


def list_all_users():
    """Admin-only. Never returns password data."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, email, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return rows
