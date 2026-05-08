"""
Sidebar navigation component for Crypto Tracker.

Provides:
- render_sidebar: Main navigation rendering with pages, currency, theme
- page_options: List of available pages for the radio selector

Reference: Extracted from app.py Phase 2 refactoring.
"""

from __future__ import annotations

import streamlit as st

from src.ui.theme import detect_theme, set_theme, get_theme_vars

# Page options for navigation
PAGE_OPTIONS = [
    "⭐  Favoritos",
    "🔍  Precio",
    "🏆  Top Monedas",
    "🔎  Buscar",
    "💼  Portfolio",
    "🪙  Moneda",
]

# Currency options
CURRENCY_OPTIONS = ["usd", "eur", "ars", "gbp", "brl", "jpy", "cny"]

# Theme options
THEME_OPTIONS = ["dark", "light"]


def get_page() -> str:
    """
    Get the currently selected page from the sidebar.

    Returns:
        Page name string (e.g., "Favoritos", "Precio")
    """
    # Try to get from session_state first (for back-compat)
    if "current_page" in st.session_state:
        return st.session_state.current_page

    # Otherwise use st.radio in sidebar
    return _render_radio()


def _render_radio() -> str:
    """
    Render the navigation radio selector in the sidebar.

    Returns:
        Selected page name
    """
    with st.sidebar:
        st.markdown(
            "<h1 style='text-align: center; font-size: 2rem; margin-bottom: 0;'>📈</h1>"
            "<h2 style='text-align: center; margin-top: 0;'>Crypto Tracker</h2>",
            unsafe_allow_html=True,
        )

        st.divider()

        page = st.radio(
            "Navegación",
            PAGE_OPTIONS,
            label_visibility="collapsed",
        )

        st.divider()

        currency = st.selectbox(
            "Moneda",
            CURRENCY_OPTIONS,
            index=0,
            help="Moneda para mostrar los precios",
        )

        # Store currency in session state for access by pages
        if "currency" not in st.session_state or st.session_state.currency != currency:
            st.session_state.currency = currency

        st.divider()

        # Theme selector
        current_theme = detect_theme()
        theme_index = 0 if current_theme == "dark" else 1

        theme_choice = st.selectbox(
            "Tema",
            THEME_OPTIONS,
            index=theme_index,
            help="Cambiá el tema de la app (oscuro / claro)",
        )

        if theme_choice != current_theme:
            set_theme(theme_choice)

        st.markdown(
            "<p style='text-align: center; opacity: 0.4; font-size: 0.75rem;'>"
            "Datos: CoinGecko</p>",
            unsafe_allow_html=True,
        )

    # Store page selection in session state
    st.session_state.current_page = page
    return page


def render_sidebar() -> tuple[str, str]:
    """
    Render the complete sidebar with navigation, currency, and theme.

    Returns:
        Tuple of (page_name, currency)
    """
    page = _render_radio()
    currency = st.session_state.get("currency", "usd")
    return page, currency


# Quick access to common pages
def is_page(page_name: str) -> bool:
    """Check if the current page matches the given name."""
    current = st.session_state.get("current_page", "")
    return page_name in current