"""
UI utilities for Crypto Tracker - Streamlit frontend.

Modules:
- theme: Theme constants and color palettes (dark/light)
- formatters: Price, change, market cap formatters
- api_cache: Streamlit cache wrappers for API calls
- navigation: Sidebar navigation component

Usage:
    from src.ui import theme, formatters, api_cache, navigation
"""

from src.ui.theme import theme_colors, detect_theme, THEME_CSS
from src.ui.formatters import fmt_price, fmt_change, fmt_cap, delta_color
from src.ui.api_cache import (
    fetch_price,
    fetch_prices,
    fetch_top,
    fetch_history,
    fetch_search,
)

__all__ = [
    "theme_colors",
    "detect_theme",
    "THEME_CSS",
    "fmt_price",
    "fmt_change",
    "fmt_cap",
    "delta_color",
    "fetch_price",
    "fetch_prices",
    "fetch_top",
    "fetch_history",
    "fetch_search",
]