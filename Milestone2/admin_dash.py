"""
admin_dash.py — FreightQuote AI Admin Dashboard.
Adapted from the mentor's shared FreightQuote/FranchiseOps template.
Adds the two lifecycle controls Section 9 requires that the base
template didn't have: Add User and Unlock Account (it only had Delete).
"""
import subprocess
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

from db import get_conn, get_champion_metrics, get_recent_notifications
from ui_theme import render_card, COLORS
import auth

_APP_START = datetime.datetime.now()
ROLES = ["Admin", "Logistics Manager", "Shipper", "Analyst"]


def _smi(query):
    try:
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3)
        return r.stdout.strip()
    except Exception:
        return "N/A"


def render_admin_dashboard():
    render_card('<h3 style="margin:0;">Admin Dashboard — System Intelligence</h3>')

    # ── 1. System Health ─────────────────────────────────────────
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};margin:16px 0 8px;">System Health</h4>',
                unsafe_allow_html=True)
    gpu_mem = _smi("memory.used")
    gpu_tot = _smi("memory.total")
    gpu_util = _smi("utilization.gpu")
    uptime = str(datetime.datetime.now() - _APP_START).split(".")[0]
    h1, h2, h3, h4 = st.columns(4)
    for col, label, val in [
        (h1, "GPU VRAM Used", f"{gpu_mem} / {gpu_tot} MB"),
        (h2, "GPU Utilization", f"{gpu_util}%"),
        (h3, "App Uptime", uptime),
        (h4, "LLM Status", "Active" if gpu_mem != "N/A" else "Standby"),
    ]:
        col.markdown(
            f'<div class="pn-card" style="text-align:center;padding:14px;">'
            f'<h3 style="margin:6px 0 2px;font-size:1.1rem;">{val}</h3>'
            f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:12px;">{label}</p>'
            f'</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── 2. User Management (list + delete + unlock) ────────────────
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};margin:0 0 8px;">User Management</h4>',
                unsafe_allow_html=True)
    with get_conn() as conn:
        try:
            users_df = pd.read_sql(
                "SELECT id, username, role, email, failed_attempts, account_status, "
                "created_at FROM users ORDER BY id DESC", conn)
        except Exception:
            users_df = pd.DataFrame(columns=["id", "username", "role", "email",
                                              "failed_attempts", "account_status", "created_at"])

    if users_df.empty:
        st.info("No users registered yet.")
    else:
        for _, row in users_df.iterrows():
            is_locked = row["account_status"] == "locked" or row["failed_attempts"] >= 3
            uc1, uc2, uc3, uc4, uc5 = st.columns([2, 1.6, 2, 1.3, 1])
            uc1.markdown(f"**{row['username']}**  \n<span style='font-size:12px;color:{COLORS['text_muted']};'>{row['email']}</span>",
                         unsafe_allow_html=True)
            uc2.markdown(f'<span style="color:#0066cc;font-weight:600;">[{row["role"]}]</span>',
                         unsafe_allow_html=True)
            status_color = COLORS["red"] if row["account_status"] == "locked" else (
                COLORS["yellow"] if row["failed_attempts"] > 0 else COLORS["green"])
            uc3.markdown(
                f'<span class="pn-badge" style="background:{status_color};">{row["account_status"]}</span> '
                f'<span style="font-size:11px;color:{COLORS["text_muted"]};">{row["failed_attempts"]} failed</span>',
                unsafe_allow_html=True,
            )
            with uc4:
                if is_locked:
                    if st.button("Unlock", key=f"unlock_{row['id']}", help=f"Unlock {row['username']}"):
                        with get_conn() as c:
                            c.execute(
                                "UPDATE users SET failed_attempts=0, lock_until=NULL, "
                                "account_status='active' WHERE id=?", (row["id"],))
                            c.commit()
                        st.success(f"{row['username']} unlocked successfully.")
                        st.rerun()
            with uc5:
                if st.button("Delete", key=f"del_user_{row['id']}", help=f"Delete {row['username']}"):
                    with get_conn() as c:
                        c.execute("DELETE FROM users WHERE id=?", (row["id"],))
                        c.commit()
                    st.success(f"Deleted {row['username']}")
                    st.rerun()

    st.markdown("###### Add User")
    with st.form("add_user_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)
        new_username = fc1.text_input("Username")
        new_email = fc2.text_input("Email")
        fc3, fc4 = st.columns(2)
        new_password = fc3.text_input("Initial Password", type="password")
        new_role = fc4.selectbox("Role", ROLES)
        submitted = st.form_submit_button("Add User")
        if submitted:
            if not (new_username and new_email and new_password):
                st.warning("Please fill out all fields.")
            elif auth.check_password_strength(new_password)[4]:
                st.error(auth.check_password_strength(new_password)[3])
            else:
                try:
                    with get_conn() as conn:
                        conn.execute(
                            "INSERT INTO users (username, email, password_hash, role, account_status) "
                            "VALUES (?,?,?,?,'active')",
                            (new_username, new_email, auth.hash_txt(new_password), new_role),
                        )
                        conn.commit()
                    st.success(f"User '{new_username}' created with role [{new_role}].")
                    st.rerun()
                except Exception:
                    st.error("Could not create user — email or username may already exist.")

    st.markdown("---")

    # ── 3. LLM Activity Monitor ──────────────────────────────────
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};margin:0 0 8px;">LLM Activity Monitor</h4>',
                unsafe_allow_html=True)
    with get_conn() as conn:
        try:
            chat_df = pd.read_sql(
                "SELECT username, count(*) as queries FROM chat_history "
                "WHERE role='user' GROUP BY username ORDER BY queries DESC", conn)
            total_q = int(chat_df["queries"].sum()) if not chat_df.empty else 0
        except Exception:
            chat_df = pd.DataFrame(columns=["username", "queries"])
            total_q = 0

    mc1, mc2 = st.columns([1, 1.6])
    with mc1:
        st.metric("Total Copilot Queries", total_q)
        st.dataframe(chat_df, width='stretch', hide_index=True)
    with mc2:
        if not chat_df.empty:
            fig = px.pie(chat_df, names="username", values="queries",
                         title="Queries per User", hole=0.4,
                         color_discrete_sequence=px.colors.sequential.Teal)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              height=250, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width='stretch')

    st.markdown("---")

    # ── 4. ML Model Card (champion metrics per agent) ─────────────
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};margin:0 0 8px;">ML Model Card</h4>',
                unsafe_allow_html=True)
    champions = get_champion_metrics()
    if not champions:
        st.info("No champion models logged yet. Run training from train_ml_freight.py.")
    else:
        mcols = st.columns(len(champions))
        for col, c in zip(mcols, champions):
            metric_label, metric_val = None, None
            for key, label in [("r2_score", "R²"), ("rmse", "RMSE"), ("roc_auc", "ROC-AUC"), ("accuracy", "Accuracy")]:
                if c.get(key) is not None:
                    metric_label, metric_val = label, c[key]
                    break
            col.markdown(
                f'<div class="pn-card" style="text-align:center;">'
                f'<div class="agent-badge">{c["agent_name"]}</div>'
                f'<h3 style="margin:10px 0 2px;">{metric_val:.3f}</h3>'
                f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:12px;">{metric_label} · {c["model_name"]}</p>'
                f'<p style="margin:4px 0 0;color:{COLORS["text_muted"]};font-size:11px;">{c["training_rows"]} rows</p>'
                f'</div>', unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── 5. Live Alert Log ────────────────────────────────────────
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};margin:0 0 8px;">Live Alert Log</h4>',
                unsafe_allow_html=True)
    filt = st.selectbox("Filter by channel", ["All", "Email", "In-App"], key="admin_alert_filt")
    alerts = get_recent_notifications(50)
    if not alerts:
        st.info("No alerts logged yet.")
    for a in alerts:
        _id, channel, recipient, subject, created_at = a
        if filt != "All" and channel.lower() != filt.lower():
            continue
        badge = {"email": COLORS["accent"], "in-app": COLORS["green"]}.get(channel.lower(), COLORS["cyan"])
        st.markdown(
            f'<div style="border-left:4px solid {badge};padding:4px 10px;margin:3px 0;font-size:13px;">'
            f'<b>[{channel.upper()}]</b> {subject} → {recipient} '
            f'<span style="color:{COLORS["text_muted"]};float:right;">{created_at}</span></div>',
            unsafe_allow_html=True,
        )
