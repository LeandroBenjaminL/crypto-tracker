"""
Streamlit cache wrappers for API calls.

Provides cached versions of API functions to reduce network calls
and improve UI responsiveness. TTL is kept short since the API
already handles its own caching.

Reference: Extracted from app.py Phase 2 refactoring.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# Cache TTL constants
CACHE_TTL_SHORT = 120  # 2 minutes - for price data
CACHE_TTL_MEDIUM = 300  # 5 minutes - for historical data
CACHE_TTL_LONG = 600  # 10 minutes - for search results

# Import the API client
from src.api import client as api_client


# =============================================================================
# Cache Decorators (using st.cache_resource pattern)
# =============================================================================


@st.cache_resource(ttl=CACHE_TTL_SHORT)
def fetch_price(query: str, currency: str) -> Any:
    """
    Fetch single coin price from API with caching.

    Args:
        query: Coin ID, symbol, or name to search for
        currency: Target currency (usd, eur, ars, etc.)

    Returns:
        Coin data dict with price, change_24h, market_cap, etc.
    """
    return api_client.get_price(query, currency=currency)


@st.cache_resource(ttl=CACHE_TTL_SHORT)
def fetch_prices(queries: tuple[str, ...], currency: str) -> Any:
    """
    Fetch multiple coin prices in a single batch request.

    Args:
        queries: Tuple of coin symbols to fetch
        currency: Target currency

    Returns:
        List of coin data dicts
    """
    return api_client.get_prices(list(queries), currency=currency)


@st.cache_resource(ttl=CACHE_TTL_SHORT)
def fetch_top(limit: int, currency: str) -> Any:
    """
    Fetch top N cryptocurrencies by market cap.

    Args:
        limit: Number of coins to return (5-50)
        currency: Target currency

    Returns:
        List of coin data dicts sorted by market cap
    """
    return api_client.get_top(limit=limit, currency=currency)


@st.cache_resource(ttl=CACHE_TTL_MEDIUM)
def fetch_history(query: str, days: int, currency: str) -> Any:
    """
    Fetch historical price data for a coin.

    Args:
        query: Coin ID, symbol, or name
        days: Number of days of history (7, 30, 90, 365)
        currency: Target currency

    Returns:
        List of dicts with 'timestamp' and 'price' keys
    """
    return api_client.get_history(query, days=days, currency=currency)


@st.cache_resource(ttl=CACHE_TTL_LONG)
def fetch_search(query: str) -> Any:
    """
    Search for coins by name or symbol.

    Args:
        query: Search query string

    Returns:
        List of matching coin data dicts
    """
    return api_client.search(query)


# =============================================================================
# Cache Management
# =============================================================================


def clear_cache() -> None:
    """Clear all cached API data (useful for force refresh)."""
    fetch_price.clear()
    fetch_prices.clear()
    fetch_top.clear()
    fetch_history.clear()
    fetch_search.clear()


def cache_stats() -> dict[str, Any]:
    """
    Get cache statistics for debugging.

    Returns:
        Dict with cache function info (hits, misses, etc.)
    """
    # Note: Streamlit's cache API doesn't expose detailed stats easily
    # This is a placeholder for future implementation
    return {
        "ttl_short": CACHE_TTL_SHORT,
        "ttl_medium": CACHE_TTL_MEDIUM,
        "ttl_long": CACHE_TTL_LONG,
    }