"""
ui_theme.py — FreightQuote AI shared styling.

Redesigned from the mentor's neo-brutalist look (thick black borders,
hard offset shadows, bright yellow) around an earthy sage/cream/tan
palette, with softer shadows, rounded corners, and calmer interaction
states — a look that fits a logistics/freight platform better than the
loud neo-brutalist starting point.

Palette (Color Hunt): #8FA28A sage green · #C7D3C0 light sage ·
#F7F4ED cream · #C8A96B tan/gold
"""
import streamlit as st

COLORS = {
    "bg_main":       "#F7F4ED",   # cream — app background
    "bg_card":       "#FFFEFB",   # warm near-white — card surfaces
    "bg_alt":        "#C7D3C0",   # light sage — secondary surfaces / hover
    "text_heading":  "#3A4238",   # dark sage-charcoal
    "text_body":     "#454F42",
    "text_main":     "#454F42",
    "text_muted":    "#7C8577",   # muted sage-gray
    "border":        "#DED6C3",   # soft tan-cream border
    "accent":        "#C8A96B",   # tan/gold — primary CTA
    "accent_hover":  "#B8955A",
    "accent_subtle": "#E8DAB9",
    "accent_text":   "#3A4238",
    "sage":          "#8FA28A",   # secondary accent
    "cyan":          "#C7D3C0",   # (kept for backward-compat call sites)
    "pink":          "#EFE6D8",
    "green":         "#7A9471",
    "yellow":        "#C9A15A",
    "red":           "#C0705A",
}

THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {COLORS["text_body"]};
    background-color: {COLORS["bg_main"]};
}}
.stApp {{ background: {COLORS["bg_main"]}; }}

h1, h2, h3, h4, h5, h6 {{
    font-family: 'Space Grotesk', sans-serif;
    color: {COLORS["text_heading"]};
    font-weight: 700;
}}
label, label p {{ color: {COLORS["text_heading"]} !important; font-weight: 600 !important; }}

.pn-card {{
    background: {COLORS["bg_card"]};
    border: 1.5px solid {COLORS["border"]};
    border-radius: 18px;
    padding: 22px 24px;
    margin-bottom: 18px;
    box-shadow: 0 6px 20px rgba(58, 66, 56, 0.06);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.pn-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(58, 66, 56, 0.10);
}}
.pn-card-alt {{
    background: {COLORS["bg_alt"]};
    border: 1.5px solid {COLORS["border"]};
    border-radius: 18px;
    padding: 22px 24px;
    margin-bottom: 18px;
    box-shadow: 0 6px 20px rgba(58, 66, 56, 0.06);
}}

.pn-badge {{
    display: inline-block;
    padding: 4px 13px;
    border-radius: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 12px;
    color: {COLORS["bg_card"]};
    letter-spacing: 0.3px;
}}
.agent-badge {{
    display: inline-block;
    padding: 5px 16px;
    background: {COLORS["accent_subtle"]};
    color: {COLORS["text_heading"]};
    border-radius: 20px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 13px;
}}

/* Buttons */
div.stButton > button {{
    background: {COLORS["accent"]} !important;
    color: {COLORS["accent_text"]} !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 22px !important;
    box-shadow: 0 4px 14px rgba(200, 169, 107, 0.35) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease !important;
}}
div.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(200, 169, 107, 0.45) !important;
    filter: brightness(1.03) !important;
    background: {COLORS["accent_hover"]} !important;
}}
div.stButton > button:active {{
    transform: translateY(0) scale(0.98) !important;
}}

/* Inputs & selects */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {{
    background: {COLORS["bg_card"]} !important;
    border: 1.5px solid {COLORS["border"]} !important;
    border-radius: 12px !important;
    box-shadow: none !important;
}}
div[data-baseweb="input"]:focus-within > div, div[data-baseweb="select"]:focus-within > div {{
    border-color: {COLORS["accent"]} !important;
    box-shadow: 0 0 0 3px rgba(200, 169, 107, 0.18) !important;
}}
input {{ color: {COLORS["text_heading"]} !important; -webkit-text-fill-color: {COLORS["text_heading"]} !important; }}
input::placeholder {{ color: {COLORS["text_muted"]} !important; opacity: 1 !important; }}

/* Tabs */
button[data-baseweb="tab"] {{
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    color: {COLORS["text_muted"]} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {COLORS["text_heading"]} !important;
    border-bottom: 3px solid {COLORS["accent"]} !important;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: {COLORS["bg_card"]} !important;
    border-right: 1px solid {COLORS["border"]} !important;
}}

.stAlert {{ border-radius: 12px !important; }}
</style>
"""

def inject_css():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

def apply_theme():
    inject_css()

def render_header(title, subtitle="", icon="🚛"):
    inject_css()
    st.markdown(f"""
    <div style="background:{COLORS['bg_card']};border:1.5px solid {COLORS['border']};border-radius:20px;
                padding:22px 28px;margin-bottom:22px;box-shadow:0 6px 20px rgba(58,66,56,0.06);">
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="font-size:38px;line-height:1;">{icon}</div>
            <div>
                <h1 style="margin:0;font-size:24px;letter-spacing:-0.3px;">{title}</h1>
                <p style="margin:4px 0 0;color:{COLORS['text_muted']};font-size:13.5px;">{subtitle}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_card(content, alt=False):
    c_class = "pn-card-alt" if alt else "pn-card"
    st.markdown(f'<div class="{c_class}">{content}</div>', unsafe_allow_html=True)

def risk_badge(text, level="Low"):
    color_map = {"Low": COLORS["green"], "Medium": COLORS["yellow"], "High": COLORS["red"], "Critical": COLORS["red"]}
    c = color_map.get(level, COLORS["sage"])
    return f'<span class="pn-badge" style="background:{c};">{text}</span>'
