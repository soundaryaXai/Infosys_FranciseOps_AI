"""
Shared ui_theme.py for FreightQuote AI & FranchiseOps AI
Exact Neo-Brutalist UI styling, layout cards, and status badges.
"""
import streamlit as st

COLORS = {
    "bg_main":       "#fffffe",
    "bg_card":       "#fffffe",
    "bg_alt":        "#f2f4f6",
    "text_heading":  "#272343",
    "text_body":     "#2d334a",
    "text_main":     "#2d334a",
    "text_muted":    "#626880",
    "border":        "#272343",
    "accent":        "#ffd803",
    "accent_subtle": "#ffe866",
    "accent_text":   "#272343",
    "cyan":          "#e3f6f5",
    "pink":          "#ffd3e2",
    "green":         "#34d399",
    "yellow":        "#fbbf24",
    "red":           "#f87171",
}

NEO_BRUTALIST_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {COLORS["text_body"]};
    background-color: {COLORS["bg_main"]};
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: 'Space Grotesk', sans-serif;
    color: {COLORS["text_heading"]};
    font-weight: 700;
}}

.pn-card {{
    background: {COLORS["bg_card"]};
    border: 3px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 6px 6px 0px {COLORS["border"]};
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.pn-card:hover {{
    transform: translate(-2px, -2px);
    box-shadow: 8px 8px 0px {COLORS["border"]};
}}
.pn-card-alt {{
    background: {COLORS["cyan"]};
    border: 3px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 6px 6px 0px {COLORS["border"]};
}}

.pn-badge {{
    display: inline-block;
    padding: 4px 12px;
    border: 2px solid {COLORS["border"]};
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 13px;
    box-shadow: 2px 2px 0px {COLORS["border"]};
    text-transform: uppercase;
}}
.agent-badge {{
    display: inline-block;
    padding: 4px 14px;
    background: {COLORS["accent"]};
    color: {COLORS["text_heading"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 14px;
    box-shadow: 3px 3px 0px {COLORS["border"]};
}}

/* Streamlit Buttons Matching Login Portal */
div.stButton > button {{
    background: #ffd803 !important;
    color: #272343 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    border: 3px solid #272343 !important;
    border-radius: 10px !important;
    padding: 10px 22px !important;
    box-shadow: 4px 4px 0px #272343 !important;
    transition: all 0.15s ease !important;
}}
div.stButton > button:hover {{
    transform: translate(-2px, -2px) !important;
    box-shadow: 6px 6px 0px #272343 !important;
    background: #ffe866 !important;
}}

/* Streamlit Inputs & Selectboxes Matching Login Portal */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {{
    background: #fffffe !important;
    border: 3px solid #272343 !important;
    border-radius: 8px !important;
    box-shadow: 3px 3px 0px #272343 !important;
}}

/* Streamlit Tabs Matching Login Portal */
button[data-baseweb="tab"] {{
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    color: #2d334a !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: #272343 !important;
    border-bottom: 3px solid #ffd803 !important;
}}
</style>
"""

def inject_css():
    st.markdown(NEO_BRUTALIST_CSS, unsafe_allow_html=True)

def apply_theme():
    inject_css()

def render_header(title, subtitle="", icon="⚡"):
    inject_css()
    st.markdown(f"""
    <div style="background:{COLORS['bg_card']};border:3px solid {COLORS['border']};border-radius:14px;padding:22px 28px;margin-bottom:24px;box-shadow:6px 6px 0px {COLORS['border']};">
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="font-size:42px;line-height:1;">{icon}</div>
            <div>
                <h1 style="margin:0;font-size:26px;letter-spacing:-0.5px;">{title}</h1>
                <p style="margin:4px 0 0;color:{COLORS['text_muted']};font-size:14px;">{subtitle}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_card(content, alt=False):
    c_class = "pn-card-alt" if alt else "pn-card"
    st.markdown(f'<div class="{c_class}">{content}</div>', unsafe_allow_html=True)

def risk_badge(text, level="Low"):
    color_map = {"Low": COLORS["green"], "Medium": COLORS["yellow"], "High": COLORS["red"], "Critical": COLORS["red"]}
    c = color_map.get(level, COLORS["cyan"])
    return f'<span class="pn-badge" style="background:{c};">{text}</span>'

