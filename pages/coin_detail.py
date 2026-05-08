"""
Coin detail page - Detailed view of a single cryptocurrency.

Shows:
- Price, market cap, volume, supply data
- Historical price chart (interactive)
- Key statistics and metrics
- Add to portfolio option

Reference: Phase 2 task 2.8 - coin_detail stub (basic version)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

from src.ui import theme, formatters, api_cache
from src.api import client as api
from src.core.exceptions import CoinNotFoundError, CryptoTrackerError


# =============================================================================
# Page Entry Point
# =============================================================================

def render_page() -> None:
    """Render the coin detail page."""
    st.markdown("<h1>🪙  Detalle de Moneda</h1>", unsafe_allow_html=True)

    # Get parameters from URL query or session state
    query = st.query_params.get("coin", "") or st.session_state.get("detail_coin", "")

    if not query:
        st.markdown(
            "<p style='opacity: 0.6; margin-top: -0.5rem;'>"
            "Consultá el detalle de cualquier criptomoneda</p>",
            unsafe_allow_html=True,
        )

        # Allow manual entry
        col_input, _ = st.columns([1, 2])
        with col_input:
            query = st.text_input(
                "Moneda",
                placeholder="Ej: btc, ethereum, SOL...",
                label_visibility="collapsed",
                key="detail_query_input",
            )

        if not query:
            st.info("Ingresá el símbolo o nombre de una moneda para ver su detalle.")
            return

    # Store in session state
    st.session_state.detail_coin = query.strip()

    # Get currency
    currency = st.session_state.get("currency", "usd")

    # Fetch coin data
    with st.spinner(f"Cargando {query}..."):
        try:
            coin = api_cache.fetch_price(query.strip(), currency=currency)
        except CryptoTrackerError as e:
            st.error(f"Error al cargar datos: {e}")
            return

    if not coin or coin.get("price") is None:
        st.warning(f"No se encontraron datos para '{query}'")
        return

    # =============================================================================
    # Header - Name and Basic Info
    # =============================================================================

    is_up = (coin.get("change_24h") or 0) >= 0
    color_class = "green" if is_up else "red"
    arrow = "▲" if is_up else "▼"

    coin_name = coin.get("name", query)
    coin_symbol = coin.get("symbol", "").upper()
    coin_price = coin.get("price", 0) or 0
    coin_change = coin.get("change_24h", 0) or 0

    st.markdown(
        f"<h2 style='margin-bottom: 0;'>{coin_name} "
        f"<span style='opacity: 0.5; font-weight: 400;'>{coin_symbol}</span></h2>",
        unsafe_allow_html=True,
    )

    # Price card
    st.markdown(
        f"<div class='card'>"
        f"<h3>Precio Actual</h3>"
        f"<div class='value {color_class}'>{formatters.fmt_price(coin_price)}</div>"
        f"<div class='sub'>{arrow} {formatters.fmt_change(coin_change)} (24h)</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # =============================================================================
    # Key Metrics
    # =============================================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cap = coin.get("market_cap")
        st.metric("Market Cap", formatters.fmt_cap(cap) if cap else "—")

    with col2:
        vol = coin.get("volume_24h")
        st.metric("Volumen 24h", formatters.fmt_cap(vol) if vol else "—")

    with col3:
        high_24h = coin.get("high_24h")
        st.metric("Máximo 24h", formatters.fmt_price(high_24h) if high_24h else "—")

    with col4:
        low_24h = coin.get("low_24h")
        st.metric("Mínimo 24h", formatters.fmt_price(low_24h) if low_24h else "—")

    # Additional metrics row
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        supply = coin.get("circulating_supply")
        st.metric("Supply Circulante", formatters.fmt_supply(supply) if supply else "—")

    with col6:
        total_supply = coin.get("total_supply")
        st.metric("Supply Total", formatters.fmt_supply(total_supply) if total_supply else "—")

    with col7:
        ath = coin.get("ath")
        st.metric(" ATH", formatters.fmt_price(ath) if ath else "—")

    with col8:
        atl = coin.get("atl")
        st.metric(" ATL", formatters.fmt_price(atl) if atl else "—")

    # =============================================================================
    # Historical Chart
    # =============================================================================

    st.divider()

    # Period selector
    col_days, col_refresh = st.columns([1, 4])
    with col_days:
        days = st.selectbox(
            "Período",
            options=[("7 días", 7), ("30 días", 30), ("90 días", 90), ("1 año", 365)],
            format_func=lambda x: x[0],
            label_visibility="collapsed",
            key="detail_days",
        )[1]

    with col_refresh:
        if st.button("🔄 Actualizar", key="refresh_detail"):
            # Clear cache for this coin
            st.cache_data.clear()
            st.rerun()

    # Fetch history
    with st.spinner("Cargando historial..."):
        try:
            history = api_cache.fetch_history(query.strip(), days=days, currency=currency)
        except CryptoTrackerError:
            history = []

    if history:
        df_hist = pd.DataFrame(history)
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"], unit="ms")

        # Calculate stats
        start_price = df_hist["price"].iloc[0]
        end_price = df_hist["price"].iloc[-1]
        period_change = ((end_price - start_price) / start_price) * 100

        tc = theme.theme_colors()
        line_color = tc["green"] if period_change >= 0 else tc["red"]
        fill_color = tc["fill_green"] if period_change >= 0 else tc["fill_red"]

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
            height=400,
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

        st.plotly_chart(fig, use_container_width=True, key=f"detail_chart_{query}_{days}")

        st.markdown(
            f"<p style='opacity: 0.5; font-size: 0.8rem; text-align: center;'>"
            f"Variación en el período: "
            f"<span class='{'green' if period_change >= 0 else 'red'}'>"
            f"{'▲' if period_change >= 0 else '▼'} {abs(period_change):.2f}%</span></p>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No hay datos históricos disponibles.")

    # =============================================================================
    # Add to Portfolio (Quick Action)
    # =============================================================================

    st.divider()

    col_add, col_back = st.columns([1, 4])

    with col_add:
        if st.button("➕ Agregar al Portfolio", use_container_width=True):
            # Store the selected coin for the portfolio page to handle
            st.session_state.add_to_portfolio = query.strip()
            st.toast(f"Moneda {coin_symbol} seleccionada. Ve a Portfolio para agregarla.")

    with col_back:
        # Link back to price page
        if st.button("🔍 Ver Precio", use_container_width=True):
            st.session_state.current_page = "🔍  Precio"
            st.query_params["coin"] = query.strip()
            st.rerun()


# Page entry point
if __name__ == "__main__":
    render_page()