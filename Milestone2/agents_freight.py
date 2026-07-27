"""
agents_freight.py — FreightQuote AI agent UI layer.

Three render functions, one per agent, following the mentor template's
pattern (agent2_franchise.py / agent3_franchise.py): each loads its
trained champion model (train_ml_freight.py), presents an input form,
runs a prediction, and stores the result in st.session_state under a
shared key so llm_engine_freight.py's orchestrator can synthesize all
three agents' outputs into one Copilot response (Phase 3, Section 8).

If a champion model hasn't been trained yet, each agent falls back to a
simple rule-based estimate rather than crashing — consistent with the
"still works without it" philosophy used elsewhere in this project.
"""
import os
import joblib
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from ui_theme import render_card, COLORS
from config import AGENT1_MODEL_PATH, AGENT2_MODEL_PATH, AGENT3_MODEL_PATH, PORTS


@st.cache_resource
def _load_model(path):
    if os.path.exists(path):
        try:
            return joblib.load(path)
        except Exception:
            return None
    return None


def _gauge(value, title, max_val=1.0, good_is_low=True):
    color = COLORS["green"] if (value < max_val * 0.4) == good_is_low else (
        COLORS["yellow"] if value < max_val * 0.7 else COLORS["red"])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text": title, "font": {"size": 13}},
        gauge={"axis": {"range": [0, max_val]}, "bar": {"color": color},
               "bgcolor": COLORS.get("bg_card_alt", "#eee")},
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=200,
                       margin=dict(l=10, r=10, t=40, b=10))
    return fig


# ────────────────────────────────────────────────────────────────
# Agent 1: Dynamic Pricing (Regression)
# ────────────────────────────────────────────────────────────────
def render_agent1_pricing():
    render_card('<h3 style="margin:0;">Agent 1 — Dynamic Pricing</h3>')
    model = _load_model(AGENT1_MODEL_PATH)
    if model is None:
        st.info("No trained champion model found yet — using a rule-based estimate. Run train_ml_freight.py first for real predictions.")

    c1, c2 = st.columns(2)
    with c1:
        origin_port = st.selectbox("Origin Port", list(PORTS.keys()), format_func=lambda k: PORTS[k])
        weight = st.number_input("Weight (kg)", 10.0, 25000.0, 500.0, step=10.0)
        quantity = st.number_input("Quantity (units)", 1, 5000, 50)
    with c2:
        distance = st.number_input("Distance (km)", 10.0, 5000.0, 800.0, step=10.0)
        congestion = st.slider("Port Congestion Index", 0.0, 1.0, 0.3)
        insurance = st.number_input("Insurance (USD)", 0.0, 5000.0, weight * 0.02, step=5.0)

    if st.button("Predict Freight Cost", key="btn_agent1_predict"):
        X = pd.DataFrame([{
            "weight_kg": weight, "insurance_usd": insurance, "quantity": quantity,
            "distance_km": distance, "congestion_index": congestion,
        }])
        if model is not None:
            cost = float(model.predict(X)[0])
        else:
            cost = weight * 0.08 + distance * 1.4 + congestion * 400 + quantity * 0.5

        st.session_state["a1_ctx"] = {
            "origin_port": PORTS[origin_port], "weight_kg": weight, "distance_km": distance,
            "congestion_index": congestion, "predicted_cost_usd": round(cost, 2),
        }
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.markdown(
                f'<div class="pn-card" style="text-align:center;">'
                f'<h2 style="margin:6px 0;">${cost:,.2f}</h2>'
                f'<p style="margin:0;color:{COLORS["text_muted"]};">Predicted Freight Cost</p>'
                f'</div>', unsafe_allow_html=True)
        with cc2:
            st.plotly_chart(_gauge(congestion, "Port Congestion", 1.0), width="stretch")

    return st.session_state.get("a1_ctx", {})


# ────────────────────────────────────────────────────────────────
# Agent 2: Route Delay Classifier
# ────────────────────────────────────────────────────────────────
def render_agent2_route_delay():
    render_card('<h3 style="margin:0;">Agent 2 — Route Delay Classifier</h3>')
    model = _load_model(AGENT2_MODEL_PATH)
    if model is None:
        st.info("No trained champion model found yet — using a rule-based estimate. Run train_ml_freight.py first for real predictions.")

    c1, c2 = st.columns(2)
    with c1:
        planned = st.number_input("Planned Transit Time (days)", 1.0, 30.0, 6.0)
        actual = st.number_input("Actual/Estimated Transit Time (days)", 1.0, 40.0, 7.5)
        congestion = st.slider("Port Congestion", 0.0, 1.0, 0.3, key="a2_congestion")
    with c2:
        weather = st.slider("Weather Risk", 0.0, 1.0, 0.2)
        reliability = st.slider("Carrier Reliability Score", 0.5, 1.0, 0.85)

    if st.button("Predict Delay Risk", key="btn_agent2_predict"):
        X = pd.DataFrame([{
            "planned_transit_days": planned, "actual_transit_days": actual,
            "port_congestion": congestion, "weather_risk": weather,
            "carrier_reliability_score": reliability,
        }])
        if model is not None and hasattr(model, "predict_proba"):
            prob = float(model.predict_proba(X)[0][1])
        else:
            prob = min(1.0, max(0.0,
                (actual - planned) / 10 * 0.4 + congestion * 0.3 + weather * 0.2 + (1 - reliability) * 0.1))

        label = "High Risk" if prob > 0.6 else ("Moderate Risk" if prob > 0.35 else "On-Time Likely")
        st.session_state["a2_ctx"] = {
            "planned_days": planned, "actual_days": actual, "port_congestion": congestion,
            "weather_risk": weather, "delay_probability": round(prob, 3), "risk_label": label,
        }
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            badge_color = COLORS["red"] if prob > 0.6 else (COLORS["yellow"] if prob > 0.35 else COLORS["green"])
            st.markdown(
                f'<div class="pn-card" style="text-align:center;">'
                f'<span class="pn-badge" style="background:{badge_color};font-size:14px;">{label}</span>'
                f'<h2 style="margin:8px 0 0;">{prob*100:.1f}%</h2>'
                f'<p style="margin:0;color:{COLORS["text_muted"]};">Delay Probability</p>'
                f'</div>', unsafe_allow_html=True)
        with cc2:
            st.plotly_chart(_gauge(prob, "Delay Risk", 1.0), width="stretch")

    return st.session_state.get("a2_ctx", {})


# ────────────────────────────────────────────────────────────────
# Agent 3: Carrier Compliance Sentinel
# ────────────────────────────────────────────────────────────────
def render_agent3_carrier_compliance():
    render_card('<h3 style="margin:0;">Agent 3 — Carrier Compliance Sentinel</h3>')
    model = _load_model(AGENT3_MODEL_PATH)
    if model is None:
        st.info("No trained champion model found yet — using a rule-based estimate. Run train_ml_freight.py first for real predictions.")

    c1, c2 = st.columns(2)
    with c1:
        on_time = st.slider("On-Time Delivery Rate", 0.5, 1.0, 0.9)
        damage = st.slider("Damage Incident Rate", 0.0, 0.3, 0.03)
        docs = st.slider("Documentation Score", 0.4, 1.0, 0.85)
    with c2:
        years = st.number_input("Years in Operation", 1, 40, 8)
        violations = st.number_input("Safety Violations (last 12mo)", 0, 15, 1)

    if st.button("Assess Compliance Risk", key="btn_agent3_predict"):
        X = pd.DataFrame([{
            "on_time_rate": on_time, "damage_incident_rate": damage,
            "documentation_score": docs, "years_in_operation": years,
            "safety_violations": violations,
        }])
        if model is not None and hasattr(model, "predict_proba"):
            risk = float(model.predict_proba(X)[0][1])
        else:
            risk = min(1.0, max(0.0,
                (1 - on_time) * 0.35 + damage * 0.35 + (1 - docs) * 0.15 + (violations / 8) * 0.15))

        label = "Non-Compliant Risk" if risk > 0.5 else "Compliant"
        st.session_state["a3_ctx"] = {
            "on_time_rate": on_time, "damage_rate": damage, "documentation_score": docs,
            "safety_violations": violations, "risk_score": round(risk, 3), "status": label,
        }
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            badge_color = COLORS["red"] if risk > 0.5 else COLORS["green"]
            st.markdown(
                f'<div class="pn-card" style="text-align:center;">'
                f'<span class="pn-badge" style="background:{badge_color};font-size:14px;">{label}</span>'
                f'<h2 style="margin:8px 0 0;">{risk*100:.1f}%</h2>'
                f'<p style="margin:0;color:{COLORS["text_muted"]};">Non-Compliance Risk</p>'
                f'</div>', unsafe_allow_html=True)
        with cc2:
            st.plotly_chart(_gauge(risk, "Compliance Risk", 1.0), width="stretch")

    return st.session_state.get("a3_ctx", {})
