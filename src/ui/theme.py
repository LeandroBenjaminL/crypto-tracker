"""
Theme constants and color utilities for Crypto Tracker.

Provides:
- Dark/Light theme CSS variables
- Theme detection (from Streamlit session state)
- Color palette dictionary for charts and tables

Reference: Extracted from app.py Phase 2 refactoring.
"""

from __future__ import annotations

import streamlit as st

# =============================================================================
# CSS Theme Variables (injected into Streamlit)
# =============================================================================

DARK_VARS = """
    --bg-primary: #0a0e1a;
    --bg-secondary: #0f1525;
    --bg-card: rgba(26, 26, 46, 0.7);
    --bg-card-hover: rgba(30, 30, 54, 0.8);
    --border-card: rgba(255, 255, 255, 0.06);
    --border-divider: rgba(255, 255, 255, 0.06);
    --text-primary: #f0f0f0;
    --text-secondary: #aaa;
    --text-muted: rgba(255, 255, 255, 0.4);
    --text-label: #aaa;
    --color-green: #00d4aa;
    --color-red: #ff6b6b;
    --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.3);
    --shadow-card-hover: 0 12px 40px rgba(0, 0, 0, 0.4);
    --shadow-button: 0 4px 12px rgba(0, 0, 0, 0.3);
    --bg-table: #1a1a2e;
    --bg-table-header: #16213e;
    --bg-table-border: #2a2a4a;
    --bg-table-hover: #1e2a4a;
    --bg-table-text: #f0f0f0;
    --bg-table-header-text: #e0e0e0;
    --bg-sidebar: linear-gradient(180deg, #0f1525 0%, #0a0e1a 100%);
    --bg-nav-hover: rgba(255, 255, 255, 0.05);
    --bg-nav-active: rgba(0, 212, 170, 0.1);
    --border-nav-active: rgba(0, 212, 170, 0.2);
    --grid-color: #2a2a4a;
"""

LIGHT_VARS = """
    --bg-primary: #f5f7fa;
    --bg-secondary: #ffffff;
    --bg-card: rgba(255, 255, 255, 0.9);
    --bg-card-hover: rgba(255, 255, 255, 0.95);
    --border-card: rgba(0, 0, 0, 0.08);
    --border-divider: rgba(0, 0, 0, 0.08);
    --text-primary: #1a1a2e;
    --text-secondary: #666;
    --text-muted: rgba(0, 0, 0, 0.4);
    --text-label: #666;
    --color-green: #00a676;
    --color-red: #e53e3e;
    --shadow-card: 0 4px 16px rgba(0, 0, 0, 0.08);
    --shadow-card-hover: 0 8px 24px rgba(0, 0, 0, 0.12);
    --shadow-button: 0 2px 8px rgba(0, 0, 0, 0.1);
    --bg-table: #ffffff;
    --bg-table-header: #f0f2f5;
    --bg-table-border: #e2e8f0;
    --bg-table-hover: #f7fafc;
    --bg-table-text: #1a1a2e;
    --bg-table-header-text: #4a5568;
    --bg-sidebar: linear-gradient(180deg, #ffffff 0%, #f5f7fa 100%);
    --bg-nav-hover: rgba(0, 0, 0, 0.04);
    --bg-nav-active: rgba(0, 166, 118, 0.08);
    --border-nav-active: rgba(0, 166, 118, 0.2);
    --grid-color: #e2e8f0;
"""

# Full CSS with shared styles
_THEME_BASE = """
<style>
    :root {THEME_VARS}

    /* ═══════════════════════════════════════════════
       ESTILOS GENERALES (compartidos por ambos temas)
       ═══════════════════════════════════════════════ */

    /* Fondo general — degradé sutil */
    .stApp {
        background: linear-gradient(160deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-primary) 100%);
    }
    .main > div { padding: 0 1rem; }

    /* Tarjetas con efecto glassmorphism */
    div[data-testid="stMetric"],
    .element-container:has(.card) {
        background: var(--bg-card);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border-radius: 16px;
        border: 1px solid var(--border-card);
        box-shadow: var(--shadow-card);
        padding: 0.5rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover,
    .element-container:has(.card):hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-card-hover);
    }

    /* Card personalizada */
    .card {
        padding: 1rem;
    }
    .card h3 {
        color: var(--text-primary);
        margin: 0 0 0.5rem 0;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        opacity: 0.6;
    }
    .card .value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .card .sub {
        font-size: 0.85rem;
        opacity: 0.5;
        margin-top: 0.25rem;
    }

    /* Colores de cambio */
    .green { color: var(--color-green); }
    .red { color: var(--color-red); }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: var(--bg-sidebar);
        border-right: 1px solid var(--border-card);
    }
    section[data-testid="stSidebar"] .stRadio label {
        padding: 0.5rem 0.75rem;
        border-radius: 10px;
        transition: background 0.15s ease;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: var(--bg-nav-hover);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
        background: var(--bg-nav-active);
        border: 1px solid var(--border-nav-active);
        border-radius: 10px;
    }

    /* Métricas */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.85rem !important;
    }
    .st-bw { background-color: transparent !important; }

    /* Tipografía general */
    h1, h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.4rem !important; }

    /* Selects y sliders */
    .stSelectbox label, .stRadio label, .stSlider label {
        color: var(--text-label) !important;
        font-size: 0.8rem !important;
    }

    /* Botones */
    .stButton button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-button);
    }

    /* DataFrame */
    .stDataFrame [data-testid="stTable"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Divisor */
    hr {
        border-color: var(--border-divider) !important;
        margin: 1.5rem 0 !important;
    }
</style>
"""


def get_theme_vars() -> str:
    """Get the CSS variables for the current theme."""
    theme = detect_theme()
    return DARK_VARS if theme == "dark" else LIGHT_VARS


def inject_theme_css() -> None:
    """Inject theme CSS into Streamlit (call once at app start)."""
    theme_vars = get_theme_vars()
    st.markdown(_THEME_BASE.replace("{THEME_VARS}", theme_vars), unsafe_allow_html=True)


# =============================================================================
# Theme Detection
# =============================================================================

def detect_theme() -> str:
    """
    Detect the current theme from Streamlit session state.

    Returns:
        "dark" or "light"
    """
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    return st.session_state.theme


def set_theme(theme: str) -> None:
    """
    Set the application theme and rerun.

    Args:
        theme: "dark" or "light"
    """
    if theme != st.session_state.get("theme"):
        st.session_state.theme = theme
        st.rerun()


# =============================================================================
# Theme Colors for Charts/Tables (Python dict)
# =============================================================================

def theme_colors() -> dict[str, str]:
    """
    Return a dictionary of colors adapted to the current theme.

    Use this for Plotly charts and Pandas styling.

    Returns:
        Dict with keys: green, red, text, text_secondary, grid,
                       bg_table, bg_table_header, bg_table_border,
                       bg_table_text, bg_table_header_text, bg_table_hover,
                       treemap_mid, fill_green, fill_red
    """
    dark = {
        "green": "#00d4aa",
        "red": "#ff6b6b",
        "text": "#f0f0f0",
        "text_secondary": "#666",
        "grid": "#2a2a4a",
        "bg_table": "#1a1a2e",
        "bg_table_header": "#16213e",
        "bg_table_border": "#2a2a4a",
        "bg_table_text": "#f0f0f0",
        "bg_table_header_text": "#e0e0e0",
        "bg_table_hover": "#1e2a4a",
        "treemap_mid": "#ffffff",
        "fill_green": "rgba(0,212,170,0.08)",
        "fill_red": "rgba(255,107,107,0.08)",
    }
    light = {
        "green": "#00a676",
        "red": "#e53e3e",
        "text": "#1a1a2e",
        "text_secondary": "#666",
        "grid": "#e2e8f0",
        "bg_table": "#ffffff",
        "bg_table_header": "#f0f2f5",
        "bg_table_border": "#e2e8f0",
        "bg_table_text": "#1a1a2e",
        "bg_table_header_text": "#4a5568",
        "bg_table_hover": "#f7fafc",
        "treemap_mid": "#f0f2f5",
        "fill_green": "rgba(0,166,118,0.08)",
        "fill_red": "rgba(229,62,62,0.08)",
    }

    theme = detect_theme()
    return light if theme == "light" else dark


# Alias for backwards compatibility
THEME_CSS = inject_theme_css
