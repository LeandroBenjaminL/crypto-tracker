"""
Crypto Tracker — panel web en Streamlit.

Consume la API REST en vez de importar los services directo
(la API arranca sola en un thread cuando abrís la app).
Esto hace que los rerenders sean más livianos y el caché se
comparta entre sesiones.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Config: API_BASE_URL desde secrets de Streamlit Cloud o env var
# ---------------------------------------------------------------------------
import os
from typing import Any, Literal

import pandas as pd
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

if not os.getenv("API_BASE_URL"):
    try:
        api_url = st.secrets.get("API_BASE_URL")
        if api_url:
            os.environ["API_BASE_URL"] = api_url
    except Exception:
        pass  # no hay secrets (desarrollo local)

from src.api import client as api  # cliente HTTP contra nuestra propia API
from src.core.exceptions import (
    CoinNotFoundError,
    CryptoTrackerError,
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
# Custom CSS — clean, modern cards and typography (theme-aware)
# ---------------------------------------------------------------------------

_DARK_VARS = """
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

_LIGHT_VARS = """
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

# Inyectamos las variables según el tema actual
_theme_vars = _DARK_VARS if st.session_state.get("theme", "dark") == "dark" else _LIGHT_VARS

st.markdown("""
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
""".replace("{THEME_VARS}", _theme_vars), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Detección de tema (dark / light)
#
# Streamlit guarda el tema en localStorage. Detectamos con JS y lo
# guardamos en session_state para usarlo en Plotly y Pandas.
# ---------------------------------------------------------------------------

def _detect_theme() -> str:
    """Detecta el tema según la selección del sidebar."""
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    return st.session_state.theme


# ---------------------------------------------------------------------------
# Colores adaptativos según el tema
# ---------------------------------------------------------------------------

def _theme_colors() -> dict[str, str]:
    """Devuelve paleta de colores según el tema actual."""
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

    theme = _detect_theme()
    return light if theme == "light" else dark


# ---------------------------------------------------------------------------
# Conexión con la API
#
# FastAPI corre como proceso aparte. Si no está levantada, mostramos
# instrucciones claras para arrancarla.
# ---------------------------------------------------------------------------

_API_PORT = 8000


def _check_api() -> bool:
    """Verifica si la API responde."""
    try:
        return api.health().get("status") == "ok"
    except Exception:
        return False


if not _check_api():
    st.error(
        "La API no está corriendo. Abrí otra terminal y ejecutá:\n\n"
        "```\nuvicorn src.api.server:app --reload\n```\n\n"
        "Después recargá esta página."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Cache wrappers de Streamlit (TTL largo porque la API ya cachea por su cuenta)
# ---------------------------------------------------------------------------

_CACHE_TTL = 120  # 2 min — la API ya tiene su propio TTL, esto es extra


@st.cache_resource(ttl=_CACHE_TTL)
def _fetch_price(query: str, currency: str) -> Any:
    """Precio desde la API."""
    return api.get_price(query, currency=currency)


@st.cache_resource(ttl=_CACHE_TTL)
def _fetch_prices(queries: tuple[str, ...], currency: str) -> Any:
    """Precios batch desde la API."""
    return api.get_prices(list(queries), currency=currency)


@st.cache_resource(ttl=_CACHE_TTL)
def _fetch_top(limit: int, currency: str) -> Any:
    """Top N desde la API."""
    return api.get_top(limit=limit, currency=currency)


@st.cache_resource(ttl=300)  # 5 min, datos históricos
def _fetch_history(query: str, days: int, currency: str) -> Any:
    """Histórico desde la API."""
    return api.get_history(query, days=days, currency=currency)


@st.cache_resource(ttl=_CACHE_TTL)
def _fetch_search(query: str) -> Any:
    """Búsqueda desde la API."""
    return api.search(query)

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

    st.divider()

    # Tema — cambia colores de gráficos y tablas al instante
    theme_choice = st.selectbox(
        "Tema",
        ["dark", "light"],
        index=0 if st.session_state.get("theme", "dark") == "dark" else 1,
        help="Cambiá el tema de la app (oscuro / claro)",
    )
    if theme_choice != st.session_state.get("theme"):
        st.session_state.theme = theme_choice
        st.rerun()

    st.markdown(
        "<p style='text-align: center; opacity: 0.4; font-size: 0.75rem;'>"
        "Datos: CoinGecko</p>",
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
    """Muestra el error al usuario sin darle botones raros de cache."""
    if isinstance(e, RateLimitError):
        if e.retry_after:
            st.error(
                f"⏳ Límite de API alcanzado. Esperá {e.retry_after}s "
                "y volvé a intentar, o configurá una API key en .env."
            )
        else:
            st.error(
                "⏳ Límite de API alcanzado. Esperá un minuto "
                "o configurá una API key gratuita en .env para más calls."
            )
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

    fav_list = api.list_favorites()

    if not fav_list:
        st.markdown(
            "<p style='opacity: 0.6;'>"
            "Todavía no tenés favoritos. Buscá una moneda y agregala "
            "desde la página de Precio.</p>",
            unsafe_allow_html=True,
        )
        st.stop()

    # Build a list of symbols
    fav_symbols = [f["symbol"] for f in fav_list]

    with st.spinner("Cargando..."):
        try:
            results = _fetch_prices(tuple(fav_symbols), currency=currency)
        except CryptoTrackerError as e:
            show_error(e)
            st.stop()

    for r in results:
        col_info, col_action = st.columns([4, 1])
        with col_info:
            if r.get("price") is not None:
                is_up = r["change_24h"] >= 0 if r.get("change_24h") else True
                arrow = "▲" if is_up else "▼"
                color = "green" if is_up else "red"
                st.markdown(
                    f"<div style='padding: 0.5rem 0;'>"
                    f"<strong>{r['name']}</strong> "
                    f"<span style='opacity: 0.5;'>{r['symbol'].upper()}</span><br>"
                    f"<span class='{color}'>{r.get('price_formatted', '')}  "
                    f"{arrow} {fmt_change(r.get('change_24h', 0))}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='padding: 0.5rem 0;'>"
                    f"<strong>{r['name']}</strong> "
                    f"<span style='opacity: 0.6;'>Sin datos</span></div>",
                    unsafe_allow_html=True,
                )
        with col_action:
            if st.button("✕", key=f"del_{r['symbol']}", help=f"Quitar {r['symbol'].upper()}"):
                api.remove_favorite(r["symbol"])
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
            key="price_query_input",
        )

    if query:
        with st.spinner("Consultando..."):
            try:
                coin = _fetch_price(query.strip(), currency=currency)
            except CryptoTrackerError as e:
                show_error(e)
                st.stop()

        has_price = coin.get("price") is not None
        if has_price:
            is_up = (coin.get("change_24h") or 0) >= 0
            color_class = "green" if is_up else "red"
            arrow = "▲" if is_up else "▼"
            coin_price = coin.get("price", 0) or 0
            coin_change = coin.get("change_24h", 0) or 0

            # Header
            st.markdown(
                f"<h2 style='margin-bottom: 0;'>{coin['name']} "
                f"<span style='opacity: 0.5; font-weight: 400;'>"
                f"{coin['symbol'].upper()}</span></h2>",
                unsafe_allow_html=True,
            )

            # Main price card
            st.markdown(
                f"<div class='card'>"
                f"<h3>Precio Actual</h3>"
                f"<div class='value {color_class}'>{fmt_price(coin_price)}</div>"
                f"<div class='sub'>{arrow} {fmt_change(coin_change)} (24h)</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Metric columns
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Precio",
                    fmt_price(coin_price),
                    delta=fmt_change(coin_change),
                    delta_color=delta_color(coin_change),
                )
            with col2:
                st.metric("Cambio 24h", fmt_change(coin_change))
            with col3:
                vol = coin.get("volume_24h")
                st.metric("Volumen 24h", fmt_cap(vol) if vol else "—")
            with col4:
                cap = coin.get("market_cap")
                st.metric("Market Cap", fmt_cap(cap) if cap else "—")

            # Add/remove favorites button
            coin_symbol = coin["symbol"].lower()
            favs = api.list_favorites()
            is_fav = any(f["symbol"] == coin_symbol for f in favs)
            if is_fav:
                if st.button("⭐ Quitar de favoritos", key=f"fav_del_{coin_symbol}"):
                    api.remove_favorite(coin_symbol)
                    st.rerun()
            else:
                if st.button("☆ Agregar a favoritos", key=f"fav_add_{coin_symbol}"):
                    api.add_favorite(coin_symbol)
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

            # El history se pide aparte del precio para no trabar la página.
            # TODO: el container con key evita el bug 'removeChild' de Streamlit
            #       al reemplazar el gráfico entre renders.
            chart_key = f"chart_{query.strip()}_{days}"
            chart_zone = st.container(key=chart_key)
            history: list[dict[str, float]] = []
            with chart_zone:
                with st.spinner("Cargando historial..."):
                    try:
                        history = _fetch_history(
                            query.strip(), days=days, currency=currency
                        )
                    except RateLimitError:
                        st.caption("⏳ Esperá un toque y cambá de período de nuevo.")
                    except CryptoTrackerError:
                        st.caption("No se pudo cargar el histórico ahora.")

                if history:
                    df_hist = pd.DataFrame(history)
                    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], unit="ms")
                    start_price = df_hist["price"].iloc[0]
                    end_price = df_hist["price"].iloc[-1]
                    hist_change = ((end_price - start_price) / start_price) * 100

                    tc = _theme_colors()
                    line_color = tc["green"] if hist_change >= 0 else tc["red"]
                    fill_color = tc["fill_green"] if hist_change >= 0 else tc["fill_red"]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df_hist["timestamp"],
                        y=df_hist["price"],
                        mode="lines",
                        name="Precio",
                        line=dict(color=line_color, width=2),
                        fill="tozeroy",
                        fillcolor=fill_color,
                    ))
                    fig.update_layout(
                        height=350,
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(
                            showgrid=False,
                            color=tc["text_secondary"],
                            showspikes=True,
                            spikethickness=1,
                            spikedash="dot",
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor=tc["grid"],
                            color=tc["text_secondary"],
                            tickprefix="$",
                        ),
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"hist_{query}_{days}")

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
            results = _fetch_top(limit, currency=currency)
        except CryptoTrackerError as e:
            show_error(e)
            st.stop()

    # Build DataFrame — la API devuelve dicts, fácil
    rows = []
    for r in results:
        rows.append({
            "#": r.get("rank", 0),
            "Nombre": r.get("name", ""),
            "Símbolo": r.get("symbol", "").upper(),
            "Precio": r.get("price", 0) or 0,
            "Cambio 24h": r.get("change_24h", 0) or 0,
            "Market Cap": r.get("market_cap", 0) or 0,
            "Volumen 24h": r.get("volume_24h", 0) or 0,
        })

    df = pd.DataFrame(rows)

    tc = _theme_colors()

    # Color the change column
    def color_change(val: float) -> str:
        if val > 0:
            return f"color: {tc['green']}"
        elif val < 0:
            return f"color: {tc['red']}"
        return f"color: {tc['text_secondary']}"

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
            "background-color": tc["bg_table"],
            "color": tc["bg_table_text"],
            "border-color": tc["bg_table_border"],
            "font-size": "14px",
        })
        .set_table_styles([
            {"selector": "th", "props": [
                ("background-color", tc["bg_table_header"]),
                ("color", tc["bg_table_header_text"]),
                ("font-weight", "600"),
                ("border-bottom", f"2px solid {tc['bg_table_border']}"),
                ("text-transform", "uppercase"),
                ("font-size", "12px"),
                ("letter-spacing", "1px"),
            ]},
            {"selector": "td", "props": [
                ("border-bottom", f"1px solid {tc['bg_table_border']}"),
            ]},
            {"selector": "tr:hover", "props": [
                ("background-color", tc["bg_table_hover"]),
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
            color_continuous_scale=[tc["red"], tc["treemap_mid"], tc["green"]],
            color_continuous_midpoint=0,
            title="Distribución por Market Cap",
        )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=tc["text"], size=12),
        )
        fig.update_traces(textinfo="label+value")
        st.plotly_chart(fig, use_container_width=True, key="treemap_top")

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
                coins = _fetch_search(search_q.strip())
            except CryptoTrackerError as e:
                show_error(e)
                st.stop()

        if not coins:
            st.warning(f"No se encontraron monedas para '{search_q}'")
        else:
            rows = []
            for c in coins[:20]:
                rows.append({
                    "Nombre": c["name"],
                    "Símbolo": c["symbol"].upper(),
                    "ID (CoinGecko)": c["id"],
                    "Rank": f"#{c['rank']}" if c.get("rank") else "—",
                })
            df = pd.DataFrame(rows)

            tc = _theme_colors()

            styled = (
                df.style
                .set_properties(**{  # type: ignore[arg-type]
                    "background-color": tc["bg_table"],
                    "color": tc["bg_table_text"],
                    "border-color": tc["bg_table_border"],
                    "font-size": "14px",
                })
                .set_table_styles([
                    {"selector": "th", "props": [
                        ("background-color", tc["bg_table_header"]),
                        ("color", tc["bg_table_header_text"]),
                        ("font-weight", "600"),
                        ("border-bottom", f"2px solid {tc['bg_table_border']}"),
                        ("text-transform", "uppercase"),
                        ("font-size", "12px"),
                        ("letter-spacing", "1px"),
                    ]},
                    {"selector": "td", "props": [
                        ("border-bottom", f"1px solid {tc['bg_table_border']}"),
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
