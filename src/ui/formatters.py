"""
Price, change, and market cap formatters for Crypto Tracker.

Provides:
- fmt_price: Format cryptocurrency prices with appropriate precision
- fmt_change: Format percentage changes with sign
- fmt_cap: Format market cap in billions/millions/trillions
- delta_color: Return Streamlit delta color based on change

Reference: Extracted from app.py Phase 2 refactoring.
"""

from __future__ import annotations

from typing import Literal


def fmt_price(price: float) -> str:
    """
    Format a price for display with appropriate decimal places.

    Args:
        price: The price value

    Returns:
        Formatted price string (e.g., "$1,234.56", "$0.0023", "$0.00000012")

    Examples:
        >>> fmt_price(1234.56)
        '$1,234.56'
        >>> fmt_price(0.0023)
        '$0.0023'
        >>> fmt_price(0.00000012)
        '$0.00000012'
    """
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def fmt_change(change: float) -> str:
    """
    Format a percentage change with sign prefix.

    Args:
        change: The percentage change (can be negative)

    Returns:
        Formatted percentage string (e.g., "+5.23%", "-2.10%")

    Examples:
        >>> fmt_change(5.23)
        '+5.23%'
        >>> fmt_change(-2.10)
        '-2.10%'
    """
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f}%"


def fmt_cap(value: float) -> str:
    """
    Format a market cap value in abbreviated form.

    Args:
        value: The market cap value

    Returns:
        Formatted market cap string (e.g., "$1.23T", "$456.78B", "$12.34M")

    Examples:
        >>> fmt_cap(1234567890123)
        '$1.23T'
        >>> fmt_cap(456789000000)
        '$456.79B'
        >>> fmt_cap(12345678)
        '$12.35M'
    """
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.0f}"


def delta_color(change: float) -> Literal["normal", "inverse"]:
    """
    Get the appropriate Streamlit delta color based on change value.

    Args:
        change: The percentage change

    Returns:
        "normal" for positive change (green up arrow),
        "inverse" for negative change (red down arrow)

    Examples:
        >>> delta_color(5.0)
        'normal'
        >>> delta_color(-3.0)
        'inverse'
    """
    return "normal" if change >= 0 else "inverse"


def fmt_volume(value: float) -> str:
    """
    Format a 24h trading volume value.

    Args:
        value: The volume value

    Returns:
        Formatted volume string (abbreviated like market cap)
    """
    return fmt_cap(value)


def fmt_supply(value: float) -> str:
    """
    Format a circulating supply value.

    Args:
        value: The supply value

    Returns:
        Formatted supply string with appropriate abbreviation
    """
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:,.0f}"