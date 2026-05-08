"""
Portfolio page - Holdings table with P&L metrics.

Shows:
- Holdings table with coin, amount, price, value, P&L
- Total portfolio value and 24h change
- Pie chart for allocation breakdown
- Add/remove holdings functionality

Reference: Phase 2 task 2.6 - portfolio page with holdings table + P&L metrics
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

from src.ui import theme, formatters, api_cache
from src.api import client as api


# =============================================================================
# Portfolio Data Management (simulated - replace with DB later)
# =============================================================================

def get_holdings() -> list[dict]:
    """
    Get user's portfolio holdings.

    Returns:
        List of dicts with keys: symbol, amount, avg_buy_price
    """
    # TODO: Replace with actual database query
    if "portfolio_holdings" not in st.session_state:
        st.session_state.portfolio_holdings = [
            {"symbol": "btc", "amount": 0.5, "avg_buy_price": 45000},
            {"symbol": "eth", "amount": 5.0, "avg_buy_price": 2800},
            {"symbol": "sol", "amount": 100.0, "avg_buy_price": 120},
            {"symbol": "dot", "amount": 200.0, "avg_buy_price": 7.5},
        ]
    return st.session_state.portfolio_holdings


def add_holding(symbol: str, amount: float, avg_price: float) -> None:
    """Add or update a holding in the portfolio."""
    holdings = get_holdings()
    for h in holdings:
        if h["symbol"] == symbol.lower():
            # Update existing: calculate new average
            total_old = h["amount"] * h["avg_buy_price"]
            total_new = amount * avg_price
            h["amount"] += amount
            h["avg_buy_price"] = (total_old + total_new) / h["amount"]
            st.session_state.portfolio_holdings = holdings
            return
    # Add new
    holdings.append({"symbol": symbol.lower(), "amount": amount, "avg_buy_price": avg_price})
    st.session_state.portfolio_holdings = holdings


def remove_holding(symbol: str) -> None:
    """Remove a holding from the portfolio."""
    holdings = get_holdings()
    st.session_state.portfolio_holdings = [h for h in holdings if h["symbol"] != symbol.lower()]


# =============================================================================
# Main Portfolio Page
# =============================================================================

def render_page() -> None:
    """Render the portfolio page."""
    st.markdown("<h1>💼  Portfolio</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='opacity: 0.6; margin-top: -0.5rem;'>"
        "Seguimiento de tus holdings y métricas P&L</p>",
        unsafe_allow_html=True,
    )

    # Get current currency
    currency = st.session_state.get("currency", "usd")

    # Get holdings
    holdings = get_holdings()

    if not holdings:
        st.markdown(
            "<p style='opacity: 0.6;'>"
            "No tenés holdings en tu portfolio. "
            "Agregá una moneda para empezar a trackear.</p>",
            unsafe_allow_html=True,
        )
        _render_add_holding_form(currency)
        return

    # Fetch current prices
    symbols = tuple(h["symbol"] for h in holdings)

    with st.spinner("Cargando precios..."):
        try:
            prices = api_cache.fetch_prices(symbols, currency=currency)
        except Exception as e:
            st.error(f"Error al cargar precios: {e}")
            return

    # Build portfolio data
    rows = []
    total_value = 0.0
    total_cost = 0.0

    price_map = {p["symbol"]: p for p in prices}

    for h in holdings:
        symbol = h["symbol"]
        amount = h["amount"]
        avg_price = h["avg_buy_price"]

        coin_data = price_map.get(symbol, {})
        current_price = coin_data.get("price", 0) or 0
        change_24h = coin_data.get("change_24h", 0) or 0

        current_value = amount * current_price
        cost_basis = amount * avg_price
        pnl = current_value - cost_basis
        pnl_pct = ((current_value - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0

        total_value += current_value
        total_cost += cost_basis

        rows.append({
            "Símbolo": symbol.upper(),
            "Nombre": coin_data.get("name", symbol.upper()),
            "Cantidad": amount,
            "Precio Actual": current_price,
            "Valor": current_value,
            "Costo Promedio": avg_price,
            "Costo Total": cost_basis,
            "P&L ($)": pnl,
            "P&L (%)": pnl_pct,
            "Cambio 24h": change_24h,
        })

    df = pd.DataFrame(rows)

    # Calculate totals
    total_pnl = total_value - total_cost
    total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

    # =============================================================================
    # Summary Metrics
    # =============================================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Valor Total",
            formatters.fmt_price(total_value),
            delta=formatters.fmt_change(total_pnl_pct),
            delta_color=formatters.delta_color(total_pnl),
        )

    with col2:
        st.metric(
            "Costo Total",
            formatters.fmt_price(total_cost),
        )

    with col3:
        st.metric(
            "P&L Total",
            formatters.fmt_price(total_pnl),
            delta=formatters.fmt_change(total_pnl_pct),
            delta_color=formatters.delta_color(total_pnl),
        )

    with col4:
        st.metric(
            "Cambio 24h",
            formatters.fmt_change(df["Cambio 24h"].mean() if len(df) > 0 else 0),
        )

    st.divider()

    # =============================================================================
    # Holdings Table
    # =============================================================================

    tc = theme.theme_colors()

    def color_pnl(val: float) -> str:
        if val > 0:
            return f"color: {tc['green']}"
        elif val < 0:
            return f"color: {tc['red']}"
        return f"color: {tc['text_secondary']}"

    styled = (
        df.style
        .format({
            "Cantidad": "{:,.4f}",
            "Precio Actual": lambda x: formatters.fmt_price(float(x)),
            "Valor": lambda x: formatters.fmt_price(float(x)),
            "Costo Promedio": lambda x: formatters.fmt_price(float(x)),
            "Costo Total": lambda x: formatters.fmt_price(float(x)),
            "P&L ($)": lambda x: formatters.fmt_price(float(x)),
            "P&L (%)": lambda x: formatters.fmt_change(float(x)),
            "Cambio 24h": lambda x: formatters.fmt_change(float(x)),
        })
        .map(color_pnl, subset=["P&L ($)", "P&L (%)"])
        .set_properties(**{
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

    # =============================================================================
    # Pie Chart - Allocation
    # =============================================================================

    st.divider()

    col_chart, col_form = st.columns([2, 1])

    with col_chart:
        st.markdown("#### Asignación del Portfolio")
        if len(df) > 0 and total_value > 0:
            fig = px.pie(
                df,
                values="Valor",
                names="Símbolo",
                title=None,
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=tc["text"]),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.1,
                    xanchor="center",
                    x=0.5,
                ),
            )
            # Add percentage labels
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )
            st.plotly_chart(fig, use_container_width=True, key="pie_allocation")
        else:
            st.caption("No hay datos suficientes para el gráfico.")

    with col_form:
        st.markdown("#### Agregar Holding")
        _render_add_holding_form(currency)

    # =============================================================================
    # Remove Holding
    # =============================================================================

    st.divider()
    st.markdown("#### Gestionar Holdings")

    col_remove = st.columns(3)
    for i, h in enumerate(holdings):
        with col_remove[i % 3]:
            if st.button(
                f"❌ {h['symbol'].upper()}",
                key=f"remove_{h['symbol']}",
                help=f"Quitar {h['symbol'].upper()} del portfolio",
            ):
                remove_holding(h["symbol"])
                st.rerun()


def _render_add_holding_form(currency: str) -> None:
    """Render form to add a new holding."""
    with st.form("add_holding"):
        col1, col2 = st.columns(2)
        with col1:
            symbol = st.text_input("Símbolo", placeholder="btc, eth, sol...", key="add_symbol")
        with col2:
            amount = st.number_input("Cantidad", min_value=0.0, step=0.01, key="add_amount")

        avg_price = st.number_input(
            f"Precio promedio ({currency.upper()})",
            min_value=0.0,
            step=0.01,
            key="add_price",
        )

        submitted = st.form_submit_button("➕ Agregar", use_container_width=True)

        if submitted:
            if symbol and amount > 0 and avg_price > 0:
                add_holding(symbol.strip(), amount, avg_price)
                st.success(f"✅ Agregado: {symbol.upper()}")
                st.rerun()
            else:
                st.warning("Completá todos los campos")


# Page entry point
if __name__ == "__main__":
    render_page()