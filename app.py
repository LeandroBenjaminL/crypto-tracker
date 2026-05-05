"""
Crypto Tracker — Streamlit App.

Visual interface for the crypto-tracker engine.
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from src.config import settings
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

from src.adapters.api_client import CoinGeckoClient
from src.core.exceptions import (
    CoinNotFoundError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
)
from src.core.favorites import FavoritesManager
from src.core.price_service import PriceService

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

_CACHE_TTL = 60  # seconds — how long before re-fetching API data


@st.cache_resource
def get_service() -> PriceService:
    client = CoinGeckoClient(cache_ttl=30.0)
    return PriceService(api_client=client)


service = get_service()


@st.cache_resource
def get_favorites() -> FavoritesManager:
    return FavoritesManager()


favorites = get_favorites()


# ---------------------------------------------------------------------------
# Streamlit cache layer — prevents re-fetching on every rerun
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_CACHE_TTL)
def _cached_price(query: str, currency: str) -> Any:
    """Cached wrapper around service.get_price()."""
    return service.get_price(query, currency=currency)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_prices(queries: tuple[str, ...], currency: str) -> Any:
    """Cached wrapper around service.get_prices()."""
    return service.get_prices(list(queries), currency=currency)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_top(limit: int, currency: str) -> Any:
    """Cached wrapper around service.list_top()."""
    return service.list_top(limit=limit, currency=currency)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_history(query: str, days: int, currency: str) -> Any:
    """Cached wrapper around service.get_history()."""
    return service.get_history(query, days=days, currency=currency)


@st.cache_data(ttl=_CACHE_TTL)
def _cached_search(query: str) -> Any:
    """Cached wrapper around service.search()."""
    return service.search(query)

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
        ["⭐  Favoritos", "🔍  Precio", "🏆  Top Monedas", "🔎  Buscar"],
        label_visibility="collapsed",
    )

    st.divider()

    currency = st.selectbox(
        "Moneda",
        ["usd", "eur", "ars", "gbp", "brl", "jpy", "cny"],
        index=0,
        help="Moneda para mostrar los precios",
    )

    # Refresh button
    col_r1, col_r2 = st.columns([3, 1])
    with col_r1:
        if st.button("🔄 Refrescar datos", use_container_width=True, type="secondary"):
            st.cache_data.clear()
            st.rerun()
    with col_r2:
        if st.button("🗑 Cache", help="Limpiar cache y recargar"):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # API key status
    has_key = bool(settings.coingecko_api_key)
    if has_key:
        st.markdown(
            "<p style='font-size:0.75rem; color:#56d4a0; text-align:center;'>"
            "🔑 API key conectada &nbsp;·&nbsp; 50 calls/min</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='font-size:0.75rem; color:#f0c060; text-align:center;'>"
            "⚠️ Sin API key &nbsp;·&nbsp; <a href='https://www.coingecko.com/en/api' "
            "target='_blank' style='color:#5e9bff;'>Conseguí una gratis</a></p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p style='text-align: center; opacity: 0.4; font-size: 0.7rem;'>"
        "Powered by CoinGecko · Cache 60s</p>",
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


def delta_color(change: float) -> Literal["normal", "inverse"]:
    return "normal" if change >= 0 else "inverse"


# ---------------------------------------------------------------------------
# Error display
# ---------------------------------------------------------------------------

def show_error(e: CryptoTrackerError) -> None:
    if isinstance(e, RateLimitError):
        if e.retry_after:
            st.error(
                f"⏳ Límite de API alcanzado. Esperá {e.retry_after}s "
                "o usá una API key gratuita en .env para más calls."
            )
        else:
            st.error(
                "⏳ Límite de API alcanzado. Esperá un minuto "
                "o usá una API key gratuita en .env para más calls."
            )
        if st.button("🔄 Reintentar ahora", key="retry_btn"):
            st.cache_data.clear()
            st.rerun()
        return

    msg = {
        CoinNotFoundError: "Moneda no encontrada. Revisá el símbolo o nombre.",
        NetworkError: "Error de conexión. Revisá tu internet.",
    }
    default = f"Error: {e}"
    for exc_type, friendly in msg.items():
        if isinstance(e, exc_type):
            st.error(friendly)
            return
    st.error(default)


# ===================================================================
# PAGE 1 — FAVORITES
# ===================================================================

if "Favoritos" in page:

    st.markdown("<h1>⭐  Favoritos</h1>", unsafe_allow_html=True)

    fav_list = favorites.list_all()

    if not fav_list:
        st.markdown(
            "<p style='opacity: 0.6;'>"
            "Todavía no tenés favoritos. Buscá una moneda y agregala "
            "desde la página de Precio.</p>",
            unsafe_allow_html=True,
        )
        st.stop()

    # Build a list of symbols
    fav_symbols = [f.symbol for f in fav_list]

    with st.spinner("Cargando..."):
        try:
            results = _cached_prices(tuple(fav_symbols), currency=currency)
        except CryptoTrackerError as e:
            show_error(e)
            st.stop()

    for result in results:
        coin = result.coin
        pd_data = result.price_data

        col_info, col_action = st.columns([4, 1])
        with col_info:
            if pd_data:
                is_up = pd_data.change_24h >= 0
                arrow = "▲" if is_up else "▼"
                color = "green" if is_up else "red"
                st.markdown(
                    f"<div style='padding: 0.5rem 0;'>"
                    f"<strong>{coin.name}</strong> "
                    f"<span style='opacity: 0.5;'>{coin.symbol.upper()}</span><br>"
                    f"<span class='{color}'>{fmt_price(pd_data.price)}  "
                    f"{arrow} {fmt_change(pd_data.change_24h)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='padding: 0.5rem 0;'>"
                    f"<strong>{coin.name}</strong> "
                    f"<span style='opacity: 0.6;'>Sin datos</span></div>",
                    unsafe_allow_html=True,
                )
        with col_action:
            if st.button("✕", key=f"del_{coin.symbol}", help=f"Quitar {coin.symbol.upper()}"):
                favorites.remove(coin.symbol)
                st.rerun()

# ===================================================================
# PAGE 2 — PRICE
# ===================================================================

elif "Precio" in page:

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
                result = _cached_price(query.strip(), currency=currency)
            except CryptoTrackerError as e:
                show_error(e)
                st.stop()

        if result.has_price() and result.price_data:
            price_d = result.price_data
            coin = result.coin
            is_up = price_d.change_24h >= 0
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
                f"<div class='value {color_class}'>{fmt_price(price_d.price)}</div>"
                f"<div class='sub'>{arrow} {fmt_change(price_d.change_24h)} (24h)</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Metric columns
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Precio",
                    fmt_price(price_d.price),
                    delta=fmt_change(price_d.change_24h),
                    delta_color=delta_color(price_d.change_24h),
                )
            with col2:
                st.metric("Cambio 24h", fmt_change(price_d.change_24h))
            with col3:
                st.metric("Volumen 24h", fmt_cap(price_d.volume_24h) if price_d.volume_24h else "—")
            with col4:
                st.metric("Market Cap", fmt_cap(price_d.market_cap) if price_d.market_cap else "—")

            # Add/remove favorites button
            coin_symbol = coin.symbol.lower()
            is_fav = favorites.is_favorite(coin_symbol)
            if is_fav:
                if st.button("⭐ Quitar de favoritos", key=f"fav_del_{coin_symbol}"):
                    favorites.remove(coin_symbol)
                    st.rerun()
            else:
                if st.button("☆ Agregar a favoritos", key=f"fav_add_{coin_symbol}"):
                    favorites.add(coin_symbol)
                    st.rerun()

            # Historical chart
            col_days, _ = st.columns([1, 2])
            with col_days:
                days = st.selectbox(
                    "Período",
                    options=[("7 días", 7), ("30 días", 30), ("90 días", 90), ("1 año", 365)],
                    format_func=lambda x: x[0],
                    label_visibility="collapsed",
                )[1]

            with st.spinner("Cargando historial..."):
                try:
                    history = _cached_history(
                        query.strip(), days=days, currency=currency
                    )
                except CryptoTrackerError:
                    history = []

            if history:
                df_hist = pd.DataFrame(history)
                df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], unit="ms")
                start_price = df_hist["price"].iloc[0]
                end_price = df_hist["price"].iloc[-1]
                hist_change = ((end_price - start_price) / start_price) * 100

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_hist["timestamp"],
                    y=df_hist["price"],
                    mode="lines",
                    name="Precio",
                    line=dict(
                        color="#00d4aa" if hist_change >= 0 else "#ff6b6b",
                        width=2,
                    ),
                    fill="tozeroy",
                    fillcolor=("rgba(0,212,170,0.08)" if hist_change >= 0
                               else "rgba(255,107,107,0.08)"),
                ))
                fig.update_layout(
                    height=350,
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        showgrid=False,
                        color="#666",
                        showspikes=True,
                        spikethickness=1,
                        spikedash="dot",
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#2a2a4a",
                        color="#666",
                        tickprefix="$",
                    ),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown(
                    f"<p style='opacity: 0.5; font-size: 0.8rem; text-align: center;'>"
                    f"Variación en el período: "
                    f"<span class='{'green' if hist_change >= 0 else 'red'}'>"
                    f"{'▲' if hist_change >= 0 else '▼'} {abs(hist_change):.2f}%</span></p>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No hay datos históricos disponibles.")

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
            results = _cached_top(limit, currency=currency)
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
            "Precio": lambda x: fmt_price(float(x)),  # type: ignore[arg-type]
            "Cambio 24h": lambda x: fmt_change(float(x)),  # type: ignore[arg-type]
            "Market Cap": lambda x: fmt_cap(float(x)),  # type: ignore[arg-type]
            "Volumen 24h": lambda x: fmt_cap(float(x)),  # type: ignore[arg-type]
        })
        .map(color_change, subset=["Cambio 24h"])  # type: ignore[arg-type]
        .set_properties(**{  # type: ignore[arg-type]
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

    col_csv, _ = st.columns([1, 4])
    with col_csv:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_bytes,
            file_name=f"top_{limit}_crypto_{currency}.csv",
            mime="text/csv",
            help="Descargar los datos como archivo CSV",
        )

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
                coins = _cached_search(search_q.strip())
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
                .set_properties(**{  # type: ignore[arg-type]
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
