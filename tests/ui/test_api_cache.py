"""
Tests for the UI API cache wrappers.

Mocks st.cache_resource and the api_client module to test
cached fetch functions and cache management.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.ui.api_cache import (
    CACHE_TTL_LONG,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_SHORT,
    cache_stats,
    clear_cache,
    fetch_history,
    fetch_price,
    fetch_prices,
    fetch_search,
    fetch_top,
)


class TestCacheConstants:
    """Test TTL constant values."""

    def test_ttl_short(self) -> None:
        assert CACHE_TTL_SHORT == 120

    def test_ttl_medium(self) -> None:
        assert CACHE_TTL_MEDIUM == 300

    def test_ttl_long(self) -> None:
        assert CACHE_TTL_LONG == 600


class TestFetchFunctions:
    """Tests for cached API fetch functions."""

    @patch("src.ui.api_cache.api_client")
    def test_fetch_price(self, mock_client: MagicMock) -> None:
        """fetch_price delegates to api_client.get_price."""
        fetch_price("bitcoin", "usd")
        mock_client.get_price.assert_called_once_with("bitcoin", currency="usd")

    @patch("src.ui.api_cache.api_client")
    def test_fetch_prices(self, mock_client: MagicMock) -> None:
        """fetch_prices delegates to api_client.get_prices."""
        fetch_prices(("btc", "eth"), "usd")
        mock_client.get_prices.assert_called_once_with(["btc", "eth"], currency="usd")

    @patch("src.ui.api_cache.api_client")
    def test_fetch_top(self, mock_client: MagicMock) -> None:
        """fetch_top delegates to api_client.get_top."""
        fetch_top(10, "usd")
        mock_client.get_top.assert_called_once_with(limit=10, currency="usd")

    @patch("src.ui.api_cache.api_client")
    def test_fetch_history(self, mock_client: MagicMock) -> None:
        """fetch_history delegates to api_client.get_history."""
        fetch_history("bitcoin", 30, "usd")
        mock_client.get_history.assert_called_once_with("bitcoin", days=30, currency="usd")

    @patch("src.ui.api_cache.api_client")
    def test_fetch_search(self, mock_client: MagicMock) -> None:
        """fetch_search delegates to api_client.search."""
        fetch_search("bitcoin")
        mock_client.search.assert_called_once_with("bitcoin")


class TestCacheManagement:
    """Tests for clear_cache and cache_stats."""

    @patch("src.ui.api_cache.fetch_price")
    @patch("src.ui.api_cache.fetch_prices")
    @patch("src.ui.api_cache.fetch_top")
    @patch("src.ui.api_cache.fetch_history")
    @patch("src.ui.api_cache.fetch_search")
    def test_clear_cache_clears_all(
        self,
        mock_search: MagicMock,
        mock_history: MagicMock,
        mock_top: MagicMock,
        mock_prices: MagicMock,
        mock_price: MagicMock,
    ) -> None:
        """clear_cache calls .clear() on every cached function."""
        clear_cache()
        mock_price.clear.assert_called_once()
        mock_prices.clear.assert_called_once()
        mock_top.clear.assert_called_once()
        mock_history.clear.assert_called_once()
        mock_search.clear.assert_called_once()

    def test_cache_stats_returns_ttls(self) -> None:
        """cache_stats returns the expected TTL dict."""
        stats = cache_stats()
        assert stats == {
            "ttl_short": 120,
            "ttl_medium": 300,
            "ttl_long": 600,
        }
