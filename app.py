"""
Crypto Tracker — Streamlit App.

Visual interface for the crypto-tracker engine.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.adapters.api_client import CoinGeckoClient
from src.core.price_service import PriceService
from src.core.exceptions import (
    CryptoTrackerError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Page config (MUST be first Streamlit command)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Crypto Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — clean, modern cards and typography
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .main > div { padding: 0 1rem; }
    .stApp { background-color: #0E1117; }
    
    .card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #2a2a4a;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        margin-bottom: 1rem;
    }
    .card h3 {
        color: #e0e0e0;
        margin: 0 0 0.5rem 0;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.7;
    }
    .card .value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .card .sub {
        font-size: 0.9rem;
        opacity: 0.6;
        margin-top: 0.25rem;
    }
    .green { color: #00d4aa; }
    .red { color: #ff6b6b; }
    .white { color: #f0f0f0; }

    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.9rem !important;
    }
    .st-bw { background-color: transparent !important; }

    h1, h2, h3 { color: #f0f0f0 !important; }
    .stSelectbox label, .stRadio label, .stSlider label {
        color: #aaa !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Service singleton (cached so we don't rebuild on every rerun)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_service() -> PriceService:
    client = CoinGeckoClient()
    return PriceService(api_client=client)


service = get_service()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        "<h1 style='text-align: center; font-size: 2rem; margin-bottom: 0;'>📈</h1>"
        "<h2 style='text-align: center; margin-top: 0;'>Crypto Tracker</h2>",
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "Navegación",
        ["🔍  Precio", "🏆  Top Monedas", "🔎  Buscar"],
        label_visibility="collapsed",
    )

    st.divider()

    currency = st.selectbox(
        "Moneda",
        ["usd", "eur", "ars", "gbp", "brl", "jpy", "cny"],
        index=0,
        help="Moneda para mostrar los precios",
    )

    st.divider()
    st.markdown(
        "<p style='text-align: center; opacity: 0.4; font-size: 0.75rem;'>"
        "Powered by CoinGecko</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Helper: format price for display
# ---------------------------------------------------------------------------

def fmt_price(price: float) -> str:
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def fmt_change(change: float) -> str:
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f}%"


def fmt_cap(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.0f}"


def delta_color(change: float) -> str:
    return "normal" if change >= 0 else "inverse"


# ---------------------------------------------------------------------------
# Error display
# ---------------------------------------------------------------------------

def show_error(e: CryptoTrackerError) -> None:
    msg = {
        CoinNotFoundError: "Moneda no encontrada. Revisá el símbolo o nombre.",
        NetworkError: "Error de conexión. Revisá tu internet.",
        RateLimitError: "Límite de API alcanzado. Esperá unos segundos.",
    }
    default = f"Error: {e}"
    for exc_type, friendly in msg.items():
        if isinstance(e, exc_type):
            st.error(friendly)
            return
    st.error(default)


# ===================================================================
# PAGE 1 — PRICE
# ===================================================================

if "Precio" in page:

    st.markdown("<h1>🔍  Precio</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='opacity: 0.6; margin-top: -0.5rem;'>"
        "Consultá el precio de cualquier criptomoneda</p>",
        unsafe_allow_html=True,
    )

    col_input, _ = st.columns([1, 2])
    with col_input:
        query = st.text_input(
            "Moneda",
            placeholder="Ej: btc, ethereum, SOL, doge...",
            label_visibility="collapsed",
        )

    if query:
        with st.spinner("Consultando..."):
            try:
                result = service.get_price(query.strip(), currency=currency)
            except CryptoTrackerError as e:
                show_error(e)
                st.stop()

        if result.has_price() and result.price_data:
            pd = result.price_data
            coin = result.coin
            is_up = pd.change_24h >= 0
            color_class = "green" if is_up else "red"
            arrow = "▲" if is_up else "▼"

            # Header
            st.markdown(
                f"<h2 style='margin-bottom: 0;'>{coin.name} "
                f"<span style='opacity: 0.5; font-weight: 400;'>"
                f"{coin.symbol.upper()}</span></h2>",
                unsafe_allow_html=True,
            )

            # Main price card
            st.markdown(
                f"<div class='card'>"
                f"<h3>Precio Actual</h3>"
                f"<div class='value {color_class}'>{fmt_price(pd.price)}</div>"
                f"<div class='sub'>{arrow} {fmt_change(pd.change_24h)} (24h)</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Metric columns
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Precio",
                    fmt_price(pd.price),
                    delta=fmt_change(pd.change_24h),
                    delta_color=delta_color(pd.change_24h),
                )
            with col2:
                st.metric("Cambio 24h", fmt_change(pd.change_24h))
            with col3:
                st.metric("Volumen 24h", fmt_cap(pd.volume_24h) if pd.volume_24h else "—")
            with col4:
                st.metric("Market Cap", fmt_cap(pd.market_cap) if pd.market_cap else "—")

            # Mini bar chart: positive/negative visual
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Cambio 24h"],
                y=[pd.change_24h],
                marker_color="#00d4aa" if is_up else "#ff6b6b",
                showlegend=False,
                width=[0.4],
            ))
            fig.update_layout(
                height=120,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, visible=False),
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning("No hay datos de precio para esta moneda.")

# ===================================================================
# PAGE 2 — TOP COINS
# ===================================================================

elif "Top Monedas" in page:

    st.markdown("<h1>🏆  Top Monedas</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='opacity: 0.6; margin-top: -0.5rem;'>"
        "Las criptomonedas con mayor capitalización de mercado</p>",
        unsafe_allow_html=True,
    )

    col_slider, _ = st.columns([1, 2])
    with col_slider:
        limit = st.slider("Cantidad", min_value=5, max_value=50, value=10, step=5)

    with st.spinner("Cargando..."):
        try:
            results = service.list_top(limit=limit, currency=currency)
        except CryptoTrackerError as e:
            show_error(e)
            st.stop()

    # Build DataFrame
    rows = []
    for r in results:
        pd_data = r.price_data
        rows.append({
            "#": r.coin.rank,
            "Nombre": r.coin.name,
            "Símbolo": r.coin.symbol.upper(),
            "Precio": pd_data.price if pd_data else 0,
            "Cambio 24h": pd_data.change_24h if pd_data else 0,
            "Market Cap": pd_data.market_cap if pd_data else 0,
            "Volumen 24h": pd_data.volume_24h if pd_data else 0,
        })

    df = pd.DataFrame(rows)

    # Color the change column
    def color_change(val: float) -> str:
        if val > 0:
            return "color: #00d4aa"
        elif val < 0:
            return "color: #ff6b6b"
        return "color: #aaa"

    styled = (
        df.style
        .format({
            "Precio": lambda x: fmt_price(x),
            "Cambio 24h": lambda x: fmt_change(x),
            "Market Cap": lambda x: fmt_cap(x),
            "Volumen 24h": lambda x: fmt_cap(x),
        })
        .applymap(color_change, subset=["Cambio 24h"])
        .set_properties(**{
            "background-color": "#1a1a2e",
            "color": "#f0f0f0",
            "border-color": "#2a2a4a",
            "font-size": "14px",
        })
        .set_table_styles([
            {"selector": "th", "props": [
                ("background-color", "#16213e"),
                ("color", "#e0e0e0"),
                ("font-weight", "600"),
                ("border-bottom", "2px solid #2a2a4a"),
                ("text-transform", "uppercase"),
                ("font-size", "12px"),
                ("letter-spacing", "1px"),
            ]},
            {"selector": "td", "props": [
                ("border-bottom", "1px solid #2a2a4a"),
            ]},
            {"selector": "tr:hover", "props": [
                ("background-color", "#1e2a4a"),
            ]},
        ])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Mini treemap of market cap distribution
    if len(df) > 0:
        fig = px.treemap(
            df.head(20),
            path=["Nombre"],
            values="Market Cap",
            color="Cambio 24h",
            color_continuous_scale=["#ff6b6b", "#ffffff", "#00d4aa"],
            color_continuous_midpoint=0,
            title="Distribución por Market Cap",
        )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f0f0f0", size=12),
        )
        fig.update_traces(textinfo="label+value")
        st.plotly_chart(fig, use_container_width=True)

# ===================================================================
# PAGE 3 — SEARCH
# ===================================================================

elif "Buscar" in page:

    st.markdown("<h1>🔎  Buscar</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='opacity: 0.6; margin-top: -0.5rem;'>"
        "Encontrá criptomonedas por nombre o símbolo</p>",
        unsafe_allow_html=True,
    )

    col_input, _ = st.columns([1, 2])
    with col_input:
        search_q = st.text_input(
            "Buscar",
            placeholder="Ej: bitcoin, sol, cardano...",
            label_visibility="collapsed",
        )

    if search_q:
        with st.spinner("Buscando..."):
            try:
                coins = service.search(search_q.strip())
            except CryptoTrackerError as e:
                show_error(e)
                st.stop()

        if not coins:
            st.warning(f"No se encontraron monedas para '{search_q}'")
        else:
            rows = []
            for c in coins[:20]:
                rows.append({
                    "Nombre": c.name,
                    "Símbolo": c.symbol.upper(),
                    "ID (CoinGecko)": c.id,
                    "Rank": f"#{c.rank}" if c.rank else "—",
                })
            df = pd.DataFrame(rows)

            styled = (
                df.style
                .set_properties(**{
                    "background-color": "#1a1a2e",
                    "color": "#f0f0f0",
                    "border-color": "#2a2a4a",
                    "font-size": "14px",
                })
                .set_table_styles([
                    {"selector": "th", "props": [
                        ("background-color", "#16213e"),
                        ("color", "#e0e0e0"),
                        ("font-weight", "600"),
                        ("border-bottom", "2px solid #2a2a4a"),
                        ("text-transform", "uppercase"),
                        ("font-size", "12px"),
                        ("letter-spacing", "1px"),
                    ]},
                    {"selector": "td", "props": [
                        ("border-bottom", "1px solid #2a2a4a"),
                    ]},
                ])
            )

            st.markdown(
                f"<p style='opacity: 0.6;'>"
                f"Se encontraron {len(coins)} resultado(s). "
                f"Mostrando las primeras 20.</p>",
                unsafe_allow_html=True,
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
