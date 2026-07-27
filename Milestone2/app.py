"""
app.py — FreightQuote AI (Lean Orchestrator)
Adapted from the mentor's FranchiseOps app.py structure. Heavy tab logic
lives in the modular files (agents_freight.py, admin_dash.py); this file
gates access via auth.py, wires up the sidebar, and routes to each tab.

One addition over the mentor template: a Home/KPI page (Section 10.1
explicitly requires "Home page shows a KPI overview" — the base template
went straight to the Copilot tab with no landing page).
"""
import os
import subprocess
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

from config import PORTS
from ui_theme import apply_theme, render_header, render_card, COLORS
from auth import render_auth_portal
from db import get_conn, load_chat_history, save_chat_message, clear_chat_history, get_champion_metrics
from llm_engine_freight import (orchestrate_3_agents_query, generate_debate_and_synthesis,
                                 generate_audit_action, warmup_llm, is_llm_loaded,
                                 start_background_warmup)
from agents_freight import (render_agent1_pricing, render_agent2_route_delay,
                             render_agent3_carrier_compliance)
from admin_dash import render_admin_dashboard

st.set_page_config(page_title="FreightQuote AI", page_icon="🚛", layout="wide",
                   initial_sidebar_state="expanded")
apply_theme()
start_background_warmup()

if not st.session_state.get("token"):
    render_auth_portal()
    st.stop()

username = st.session_state.get("username", "guest")
user_role = st.session_state.get("role", "Shipper")
is_admin = user_role.lower() == "admin"

with st.sidebar:
    st.markdown(f'<div style="text-align:center;padding:10px 0;font-weight:700;font-size:18px;'
                f'color:{COLORS["text_heading"]};">🚛 FreightQuote AI</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center;font-size:13px;color:{COLORS["text_muted"]};'
                f'margin-bottom:12px;">User: <b>{username}</b><br>'
                f'<span style="color:#0066cc;font-weight:600;">[{user_role}]</span></div>',
                unsafe_allow_html=True)

    tabs = ["Home", "AI Copilot", "Agent 1: Pricing", "Agent 2: Route Delay",
            "Agent 3: Carrier Compliance", "Analytics & Retrain"]
    icons = ["house-fill", "chat-dots-fill", "cash-coin", "signpost-split-fill",
             "shield-check", "bar-chart-fill"]
    if is_admin:
        tabs.append("Admin Dashboard")
        icons.append("shield-lock-fill")
    tabs.append("Sign Out")
    icons.append("box-arrow-right")

    selected_tab = option_menu(
        menu_title=None, options=tabs, icons=icons, default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "nav-link": {"font-size": "13px", "text-align": "left", "margin": "3px 0",
                         "border-radius": "10px", "color": COLORS["text_main"], "font-weight": "600"},
            "nav-link-selected": {"background-color": COLORS["accent"], "color": COLORS["accent_text"],
                                   "border": f"2px solid {COLORS['border']}"},
        },
    )

if selected_tab == "Sign Out":
    st.session_state["token"] = None
    st.rerun()

render_header("FreightQuote AI", f"Module: {selected_tab}")

# ── LLM status banner (shown on every page) ─────────────────────
b1, b2 = st.columns([4, 1.2])
with b1:
    if is_llm_loaded():
        st.markdown('<div style="background:#d1fae5;border:2px solid #34d399;border-radius:10px;'
                    'padding:8px 16px;font-weight:600;color:#065f46;font-size:13px;">'
                    'LLM Engine: Active — Qwen2.5-3B (4-bit) Ready</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#bae8e8;border:2px solid #272343;border-radius:10px;'
                    'padding:8px 16px;font-weight:600;color:#272343;font-size:13px;">'
                    'LLM Engine: Standby — warm up before use, or continue with rule-based answers</div>',
                    unsafe_allow_html=True)
with b2:
    if not is_llm_loaded():
        if st.button("Warm Up LLM", key="warmup_btn", width="stretch"):
            with st.spinner("Loading Qwen2.5-3B..."):
                warmup_llm()
            st.rerun()


def _agent_ctx():
    return (st.session_state.get("a1_ctx", {}), st.session_state.get("a2_ctx", {}),
            st.session_state.get("a3_ctx", {}))


# ─────────────────────────────────────────────────────────────────
# TAB: HOME — KPI overview (Section 10.1)
# ─────────────────────────────────────────────────────────────────
if selected_tab == "Home":
    render_card('<h3 style="margin:0;">Platform Overview</h3>'
                f'<p style="margin:4px 0 0;color:{COLORS["text_muted"]};font-size:13px;">'
                'Multi-Agent Freight Intelligence — Pricing, Route Delay & Carrier Compliance</p>')

    with get_conn() as conn:
        try:
            n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except Exception:
            n_users = 0
        try:
            n_queries = conn.execute("SELECT COUNT(*) FROM chat_history WHERE role='user'").fetchone()[0]
        except Exception:
            n_queries = 0

    champions = get_champion_metrics()
    k1, k2, k3, k4 = st.columns(4)
    for col, label, val in [
        (k1, "Registered Users", n_users),
        (k2, "Trained Agents", f"{len(champions)}/3"),
        (k3, "Copilot Queries", n_queries),
        (k4, "LLM Status", "Active" if is_llm_loaded() else "Standby"),
    ]:
        col.markdown(f'<div class="pn-card" style="text-align:center;padding:16px;">'
                     f'<h2 style="margin:4px 0;">{val}</h2>'
                     f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:12px;">{label}</p>'
                     f'</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};">Champion Model Performance</h4>',
                unsafe_allow_html=True)
    if champions:
        acols = st.columns(len(champions))
        for col, c in zip(acols, champions):
            metric_label, metric_val = "—", 0
            for key, label in [("r2_score", "R²"), ("roc_auc", "ROC-AUC")]:
                if c.get(key) is not None:
                    metric_label, metric_val = label, c[key]
                    break
            col.markdown(f'<div class="pn-card" style="text-align:center;">'
                         f'<span class="agent-badge">{c["agent_name"]}</span>'
                         f'<h3 style="margin:8px 0 2px;">{metric_val:.3f}</h3>'
                         f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:12px;">{metric_label} · {c["model_name"]}</p>'
                         f'</div>', unsafe_allow_html=True)
    else:
        st.info("No agents trained yet — run train_ml_freight.py, or use Analytics & Retrain below.")

    st.markdown("---")
    st.markdown(f'<h4 style="color:{COLORS["text_heading"]};">Indian Port Coverage</h4>', unsafe_allow_html=True)
    port_df = pd.DataFrame([{"Code": k, "Port": v} for k, v in PORTS.items()])
    st.dataframe(port_df, width="stretch", hide_index=True)

# ─────────────────────────────────────────────────────────────────
# TAB: AI COPILOT
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "AI Copilot":
    render_card('<h3 style="margin:0 0 6px;">Unified AI Copilot — Freight Intelligence</h3>'
                f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:13px;">'
                'Ask about pricing, route delay risk, or carrier compliance. '
                'Answers synthesize all 3 agents\' latest outputs.</p>')

    if "copilot_history" not in st.session_state:
        hist = load_chat_history(username)
        if not hist:
            msg = "Welcome to FreightQuote AI Copilot! Ask about shipment cost, delay risk, or carrier compliance."
            save_chat_message(username, "assistant", msg)
            hist = [{"role": "assistant", "content": msg}]
        st.session_state["copilot_history"] = hist

    for m in st.session_state["copilot_history"]:
        bg = "#e3f6f5" if m["role"] == "user" else "white"
        label = "You" if m["role"] == "user" else "Copilot"
        st.markdown(f'<div class="pn-card" style="background:{bg};border-left:5px solid '
                    f'{COLORS["accent"] if m["role"]=="user" else COLORS["border"]};">'
                    f'<b>{label}:</b><br>{m["content"]}</div>', unsafe_allow_html=True)

    inp_col, clr_col = st.columns([8, 1])
    with inp_col:
        with st.form("copilot_form", clear_on_submit=True):
            user_q = st.text_input("Your question", placeholder="e.g. 'Should we proceed with this shipment?'",
                                    label_visibility="collapsed")
            fa, fb, fc = st.columns([2, 2, 2])
            with fa:
                submit = st.form_submit_button("Ask Copilot")
            with fb:
                debate = st.form_submit_button("Debate View")
            with fc:
                audit = st.form_submit_button("Audit Action (JSON)")
    with clr_col:
        if st.button("Clear", help="Clear history"):
            clear_chat_history(username)
            st.session_state["copilot_history"] = []
            st.rerun()

    a1_ctx, a2_ctx, a3_ctx = _agent_ctx()

    if (submit or debate or audit) and (user_q.strip() or audit):
        query_text = user_q.strip() or "Generate a shipment audit action."
        save_chat_message(username, "user", query_text)
        st.session_state["copilot_history"].append({"role": "user", "content": query_text})

        if debate:
            with st.spinner("Running multi-agent debate..."):
                res = generate_debate_and_synthesis(query_text, a1_ctx, a2_ctx, a3_ctx)
            dc1, dc2, dc3 = st.columns(3)
            for col, key, label, color in [
                (dc1, "agent1", "Dynamic Pricing", COLORS["accent"]),
                (dc2, "agent2", "Route Delay", "#34d399"),
                (dc3, "agent3", "Carrier Compliance", "#f87171"),
            ]:
                col.markdown(f'<div class="pn-card" style="border-top:4px solid {color};">'
                             f'<span class="agent-badge">{label}</span><br><br>{res[key]}</div>',
                             unsafe_allow_html=True)
            ans = f"**Executive Synthesis:** {res['synthesis']}"
        elif audit:
            with st.spinner("Synthesizing audit action..."):
                action = generate_audit_action(a1_ctx, a2_ctx, a3_ctx)
            st.json(action)
            ans = f"**Audit Action:** {action.get('recommended_action', 'N/A')} (risk: {action.get('risk_level', 'N/A')})"
        else:
            with st.spinner("Generating answer..."):
                ans = orchestrate_3_agents_query(query_text, a1_ctx, a2_ctx, a3_ctx)

        save_chat_message(username, "assistant", ans)
        st.session_state["copilot_history"].append({"role": "assistant", "content": ans})
        st.rerun()

# ─────────────────────────────────────────────────────────────────
# TAB: AGENT 1 — DYNAMIC PRICING
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "Agent 1: Pricing":
    render_agent1_pricing()

# ─────────────────────────────────────────────────────────────────
# TAB: AGENT 2 — ROUTE DELAY
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "Agent 2: Route Delay":
    render_agent2_route_delay()

# ─────────────────────────────────────────────────────────────────
# TAB: AGENT 3 — CARRIER COMPLIANCE
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "Agent 3: Carrier Compliance":
    render_agent3_carrier_compliance()

# ─────────────────────────────────────────────────────────────────
# TAB: ANALYTICS & RETRAIN
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "Analytics & Retrain":
    render_card('<h3 style="margin:0;">Analytics & Model Management</h3>')
    with get_conn() as conn:
        try:
            n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except Exception:
            n_users = 0
        try:
            n_alerts = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        except Exception:
            n_alerts = 0
    champions = get_champion_metrics()
    kc = st.columns(3)
    for col, label, val in [(kc[0], "Users", n_users), (kc[1], "Trained Agents", f"{len(champions)}/3"),
                             (kc[2], "Alerts Logged", n_alerts)]:
        col.markdown(f'<div class="pn-card" style="text-align:center;padding:14px;">'
                     f'<h2 style="margin:4px 0;">{val}</h2>'
                     f'<p style="margin:0;color:{COLORS["text_muted"]};font-size:12px;">{label}</p>'
                     f'</div>', unsafe_allow_html=True)

    st.markdown("---")
    mc1, mc2 = st.columns([1, 1.5])
    with mc1:
        render_card('<h4 style="margin:0 0 8px;">Retrain All Agents</h4>')
        if st.button("Retrain Now"):
            with st.spinner("Training all 3 agents..."):
                res = subprocess.run(["python", "train_ml_freight.py"], capture_output=True, text=True, timeout=600)
            (st.success if res.returncode == 0 else st.error)(
                "All agents retrained." if res.returncode == 0 else "Training failed.")
            st.code((res.stdout if res.returncode == 0 else res.stderr)[-1500:])
    with mc2:
        with get_conn() as conn:
            try:
                ml_df = pd.read_sql(
                    "SELECT agent_name, model_name, r2_score, roc_auc, accuracy, training_rows, "
                    "is_champion, created_at FROM ml_models ORDER BY id DESC", conn)
                st.dataframe(ml_df, width="stretch", hide_index=True)
            except Exception:
                st.info("No model history yet.")

# ─────────────────────────────────────────────────────────────────
# TAB: ADMIN DASHBOARD
# ─────────────────────────────────────────────────────────────────
elif selected_tab == "Admin Dashboard":
    if not is_admin:
        st.error("Admin access required.")
    else:
        render_admin_dashboard()
