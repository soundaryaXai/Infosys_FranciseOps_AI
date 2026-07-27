"""
db.py — FreightQuote AI data layer (adapted from the shared mentor template).

Extends the mentor's `users` table with the columns Section 5 requires
for progressive lockout (failed_attempts, lock_until, account_status),
plus a role column for the Admin Dashboard. Domain-specific tables for
the three agents (shipments/routes/carrier records) are added in
train_ml_freight.py once the Kaggle data shape is known, so this file
doesn't guess at a schema prematurely.
"""
import sqlite3
from config import DB_PATH


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            security_question TEXT,
            security_answer_hash TEXT,
            role TEXT DEFAULT 'User',
            failed_attempts INTEGER DEFAULT 0,
            lock_until TIMESTAMP DEFAULT NULL,
            account_status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        # Additive migrations — safe to re-run against an existing DB
        # (e.g. one created by an earlier, unhardened version of this file).
        for stmt in [
            "ALTER TABLE users ADD COLUMN security_question TEXT",
            "ALTER TABLE users ADD COLUMN security_answer_hash TEXT",
            "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'User'",
            "ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN lock_until TIMESTAMP DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'active'",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        conn.execute("""CREATE TABLE IF NOT EXISTS ml_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT, model_name TEXT, r2_score REAL,
            rmse REAL, roc_auc REAL, accuracy REAL, training_rows INTEGER,
            is_champion INTEGER DEFAULT 0, file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT, recipient TEXT, subject TEXT, message TEXT,
            status TEXT DEFAULT 'Sent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        conn.commit()


# ── ML model metrics (Admin Panel -> ML Model Card tab) ────────
def save_ml_metrics(agent_name, model_name, metric_name, metric_value,
                     training_rows, path, is_champion=False):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ml_models "
            "(agent_name, model_name, r2_score, rmse, roc_auc, accuracy, "
            " training_rows, is_champion, file_path) VALUES (?,?,?,?,?,?,?,?,?)",
            (agent_name, model_name,
             metric_value if metric_name == "r2" else None,
             metric_value if metric_name == "rmse" else None,
             metric_value if metric_name == "roc_auc" else None,
             metric_value if metric_name == "accuracy" else None,
             training_rows, int(is_champion), path),
        )
        conn.commit()


def get_champion_metrics():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT agent_name, model_name, r2_score, rmse, roc_auc, accuracy, "
            "training_rows, created_at FROM ml_models WHERE is_champion=1 "
            "ORDER BY agent_name"
        ).fetchall()
    cols = ["agent_name", "model_name", "r2_score", "rmse", "roc_auc",
            "accuracy", "training_rows", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


# ── Chat history (LLM Copilot memory) ───────────────────────────
def load_chat_history(username, limit=60):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_history WHERE username=? "
            "ORDER BY id DESC LIMIT ?", (username, limit)).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def save_chat_message(username, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_history (username, role, content) VALUES (?,?,?)",
            (username, role, content))
        conn.commit()


def clear_chat_history(username):
    with get_conn() as conn:
        conn.execute("DELETE FROM chat_history WHERE username=?", (username,))
        conn.commit()


# ── Notifications (lockout / OTP alerts logged for the admin panel) ──
def log_notification(channel, recipient, subject, message, status="Sent"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notifications (channel, recipient, subject, message, status) "
            "VALUES (?,?,?,?,?)",
            (channel, recipient, subject, message, status))
        conn.commit()


def get_recent_notifications(limit=50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, channel, recipient, subject, created_at FROM notifications "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return rows
