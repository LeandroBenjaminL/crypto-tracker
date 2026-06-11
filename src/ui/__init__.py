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

from src.ui.api_cache import (
    fetch_history,
    fetch_price,
    fetch_prices,
    fetch_search,
    fetch_top,
)
from src.ui.formatters import delta_color, fmt_cap, fmt_change, fmt_price
from src.ui.theme import THEME_CSS, detect_theme, theme_colors

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
