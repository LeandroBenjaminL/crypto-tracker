"""
Tests for the PriceService business logic.

We mock the API client to test the service in isolation.
This lets us verify every business rule without hitting the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

from src.core.models import (
    CoinSearchResult,
    Cryptocurrency,
    PriceData,
)
from src.core.exceptions import ValidationError
from src.core.price_service import (
    PriceService,
    _normalize_query,
    _try_resolve_id,
    SYMBOL_TO_ID,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mocked API client."""
    return MagicMock()


@pytest.fixture
def service(mock_client: MagicMock) -> PriceService:
    """Create a PriceService with a mocked client."""
    return PriceService(api_client=mock_client)


class TestSymbolResolution:
    """Tests for the local symbol → id resolution."""

    def test_known_symbol_resolved(self):
        """BTC resolves to bitcoin."""
        assert _try_resolve_id("btc") == "bitcoin"

    def test_known_symbol_case_insensitive(self):
        """Symbol resolution is case-insensitive."""
        assert _try_resolve_id("BTC") == "bitcoin"
        assert _try_resolve_id("Btc") == "bitcoin"

    def test_unknown_symbol_returns_none(self):
        """Unknown symbols return None."""
        assert _try_resolve_id("unknowncoin123") is None

    def test_all_symbols_resolve(self):
        """Every entry in SYMBOL_TO_ID resolves correctly."""
        for symbol, expected_id in SYMBOL_TO_ID.items():
            assert _try_resolve_id(symbol) == expected_id


class TestNormalizeQuery:
    """Tests for query normalization."""

    def test_lowercases(self):
        assert _normalize_query("BTC") == "btc"

    def test_strips_whitespace(self):
        assert _normalize_query("  bitcoin  ") == "bitcoin"

    def test_raises_on_empty(self):
        with pytest.raises(ValidationError):
            _normalize_query("")

    def test_raises_on_whitespace_only(self):
        with pytest.raises(ValidationError):
            _normalize_query("   ")


class TestPriceService:
    """Tests for PriceService business logic."""

    # ------------------------------------------------------------------
    # get_price
    # ------------------------------------------------------------------

    def test_get_price_by_id(self, service: PriceService, mock_client: MagicMock):
        """Fetch price using a CoinGecko ID directly."""
        mock_client.search_coin.return_value = []  # not in local map → use as-is
        mock_client.get_price.return_value = {
            "bitcoin": {
                "usd": 45000.50,
                "usd_24h_change": 2.5,
                "usd_24h_vol": 25000000000,
                "usd_market_cap": 850000000000,
            },
        }

        result = service.get_price("bitcoin")

        assert result.coin.id == "bitcoin"
        assert result.has_price() is True
        assert result.price_data is not None
        assert result.price_data.price == 45000.50
        assert result.price_data.change_24h == 2.5

    def test_get_price_by_symbol(self, service: PriceService, mock_client: MagicMock):
        """Fetch price using a symbol (BTC → bitcoin)."""
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50, "usd_24h_change": 2.5},
        }

        result = service.get_price("btc")

        # Should have resolved btc → bitcoin via the local map
        assert result.coin.id == "bitcoin"

    def test_get_price_by_symbol_uppercase(self, service: PriceService, mock_client: MagicMock):
        """Symbol resolution is case-insensitive."""
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50},
        }

        result = service.get_price("BTC")

        assert result.coin.id == "bitcoin"

    def test_get_price_no_price_data(self, service: PriceService, mock_client: MagicMock):
        """Handle coin found but no price data returned."""
        mock_client.get_price.return_value = {
            "bitcoin": {},
        }

        result = service.get_price("bitcoin")

        assert result.has_price() is False
        assert result.price_data is None

    # ------------------------------------------------------------------
    # get_prices (batch)
    # ------------------------------------------------------------------

    def test_get_prices_multiple(self, service: PriceService, mock_client: MagicMock):
        """Fetch prices for multiple coins."""
        mock_client.search_coin.return_value = []  # not in local map → use as-is
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50, "usd_24h_change": 2.5},
            "ethereum": {"usd": 3200.00, "usd_24h_change": -1.2},
        }

        results = service.get_prices(["bitcoin", "ethereum"])

        assert len(results) == 2
        assert results[0].coin.id == "bitcoin"
        assert results[0].price_data is not None
        assert results[0].price_data.price == 45000.50
        assert results[1].coin.id == "ethereum"
        assert results[1].price_data.price == 3200.00

    def test_get_prices_batches_symbols(self, service: PriceService, mock_client: MagicMock):
        """Batch resolves symbols to IDs."""
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50},
            "ethereum": {"usd": 3200.00},
        }

        results = service.get_prices(["btc", "eth"])

        assert len(results) == 2

    def test_get_prices_empty_list(self, service: PriceService, mock_client: MagicMock):
        """Empty query list raises ValidationError."""
        with pytest.raises(ValidationError):
            service.get_prices([])

    def test_get_prices_handles_missing_coin(self, service: PriceService, mock_client: MagicMock):
        """Missing coin returns result without price_data."""
        mock_client.search_coin.return_value = []  # prevent MagicMock chain
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50},
            # "fakecoin" is missing from response
        }

        results = service.get_prices(["bitcoin", "fakecoin"])

        assert len(results) == 2
        assert results[0].has_price() is True
        assert results[1].has_price() is False

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def test_search_finds_coins(self, service: PriceService, mock_client: MagicMock):
        """Search returns Cryptocurrency objects."""
        mock_client.search_coin.return_value = [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1},
        ]

        results = service.search("bitcoin")

        assert len(results) == 1
        assert isinstance(results[0], Cryptocurrency)
        assert results[0].id == "bitcoin"
        assert results[0].symbol == "btc"
        assert results[0].rank == 1

    def test_search_no_results(self, service: PriceService, mock_client: MagicMock):
        """Search returns empty list when nothing found."""
        mock_client.search_coin.return_value = []

        results = service.search("nonexistent123")

        assert results == []

    def test_search_empty_query(self, service: PriceService, mock_client: MagicMock):
        """Empty query raises ValidationError."""
        with pytest.raises(ValidationError):
            service.search("")

    # ------------------------------------------------------------------
    # list_top
    # ------------------------------------------------------------------

    def test_list_top_default_limit(self, service: PriceService, mock_client: MagicMock):
        """Default limit is 10."""
        mock_client.get_top_coins.return_value = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 45000.50,
                "market_cap": 850000000000,
                "market_cap_rank": 1,
                "price_change_percentage_24h": 2.5,
                "total_volume": 25000000000,
            },
        ]

        results = service.list_top()

        assert len(results) == 1
        assert results[0].coin.rank == 1
        assert results[0].price_data is not None
        assert results[0].price_data.price == 45000.50
        assert results[0].price_data.change_24h == 2.5

    def test_list_top_custom_limit(self, service: PriceService, mock_client: MagicMock):
        """Custom limit is passed to client."""
        mock_client.get_top_coins.return_value = []

        service.list_top(limit=25)

        mock_client.get_top_coins.assert_called_once_with(limit=25, currency="usd")

    def test_list_top_invalid_limit_zero(self, service: PriceService, mock_client: MagicMock):
        """Limit of 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            service.list_top(limit=0)

    def test_list_top_invalid_limit_too_high(self, service: PriceService, mock_client: MagicMock):
        """Limit > 250 raises ValidationError."""
        with pytest.raises(ValidationError):
            service.list_top(limit=300)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_unknown_symbol_falls_back_to_api_search(
        self,
        service: PriceService,
        mock_client: MagicMock,
    ):
        """Unknown symbol tries API search before using as-is."""
        mock_client.search_coin.return_value = [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        ]
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 45000.50},
        }

        # "btc" IS in the local map, so let's test with something unknown
        # that might still be found via API search
        result = service.get_price("bitcoin")

        assert result.coin.id == "bitcoin"

    def test_get_price_invalid_query_raises(self, service: PriceService, mock_client: MagicMock):
        """Empty query raises ValidationError."""
        with pytest.raises(ValidationError):
            service.get_price("")

    # ------------------------------------------------------------------
    # get_history
    # ------------------------------------------------------------------

    def test_get_history_success(self, service: PriceService, mock_client: MagicMock):
        """Fetch historical prices."""
        mock_client.search_coin.return_value = []
        mock_client.get_coin_history.return_value = {
            "prices": [[1700000000000, 45000.0], [1700086400000, 46000.0]],
        }

        result = service.get_history("bitcoin", days=7)

        assert len(result) == 2
        assert result[0]["timestamp"] == 1700000000000
        assert result[0]["price"] == 45000.0

    def test_get_history_resolves_symbol(self, service: PriceService, mock_client: MagicMock):
        """Symbols are resolved before fetching history."""
        mock_client.get_coin_history.return_value = {"prices": []}

        service.get_history("btc", days=7)

        # Should have resolved btc → bitcoin before calling the client
        mock_client.get_coin_history.assert_called_once_with(
            "bitcoin", days=7, currency="usd",
        )
