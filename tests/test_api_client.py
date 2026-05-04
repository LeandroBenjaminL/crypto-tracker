"""
Tests for the CoinGecko API client.

We mock requests.Session to avoid hitting the real API.
This keeps tests fast, deterministic, and offline-friendly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest
import requests

from src.adapters.api_client import CoinGeckoClient, RateLimiter
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock requests.Session with a .get() method."""
    session = create_autospec(requests.Session, instance=True)
    session.get.return_value = MagicMock(spec=requests.Response)
    return session


@pytest.fixture
def client(mock_session: MagicMock) -> CoinGeckoClient:
    """Create a CoinGeckoClient with a mocked session."""
    c = CoinGeckoClient(rate_limiter=RateLimiter(max_calls=1000))
    c._session = mock_session  # swap in the mock
    return c


def _mock_response(
    json_data: object,
    status_code: int = 200,
    headers: dict | None = None,
) -> MagicMock:
    """Helper to build a mock Response with the expected interface."""
    resp = MagicMock(spec=requests.Response)
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = headers or {}
    return resp


class TestCoinGeckoClient:
    """Tests for the CoinGecko API client."""

    # ------------------------------------------------------------------
    # get_price
    # ------------------------------------------------------------------

    def test_get_price_success(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Fetch price for a single coin."""
        mock_session.get.return_value = _mock_response({
            "bitcoin": {
                "usd": 45000.50,
                "usd_24h_change": 2.5,
                "usd_24h_vol": 25000000000,
                "usd_market_cap": 850000000000,
            },
        })

        result = client.get_price(["bitcoin"])

        assert "bitcoin" in result
        assert result["bitcoin"]["usd"] == 45000.50

    def test_get_price_multiple_coins(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Fetch prices for multiple coins at once."""
        mock_session.get.return_value = _mock_response({
            "bitcoin": {"usd": 45000.50, "usd_24h_change": 2.5},
            "ethereum": {"usd": 3200.00, "usd_24h_change": -1.2},
        })

        result = client.get_price(["bitcoin", "ethereum"])

        assert len(result) == 2
        assert result["bitcoin"]["usd"] == 45000.50
        assert result["ethereum"]["usd"] == 3200.00

    def test_get_price_coin_not_found(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise CoinNotFoundError when coin doesn't exist."""
        mock_session.get.return_value = _mock_response({
            "nonexistentcoin": {},
        })

        with pytest.raises(CoinNotFoundError) as exc:
            client.get_price(["nonexistentcoin"])

        assert "nonexistentcoin" in str(exc.value)

    def test_get_price_partial_not_found(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise error if one of several coins is missing."""
        mock_session.get.return_value = _mock_response({
            "bitcoin": {"usd": 45000.50},
            "fakecoin": {},
        })

        with pytest.raises(CoinNotFoundError) as exc:
            client.get_price(["bitcoin", "fakecoin"])

        assert "fakecoin" in str(exc.value)

    # ------------------------------------------------------------------
    # get_top_coins
    # ------------------------------------------------------------------

    def test_get_top_coins_success(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Fetch top coins list."""
        mock_session.get.return_value = _mock_response([
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 45000.50,
                "market_cap": 850000000000,
                "price_change_percentage_24h": 2.5,
            },
            {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "current_price": 3200.00,
                "market_cap": 380000000000,
                "price_change_percentage_24h": -1.2,
            },
        ])

        result = client.get_top_coins(limit=2)

        assert len(result) == 2
        assert result[0]["id"] == "bitcoin"
        assert result[1]["id"] == "ethereum"

    def test_get_top_coins_custom_limit(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Verify limit parameter is passed to the API."""
        mock_session.get.return_value = _mock_response([])

        client.get_top_coins(limit=5)

        # Check that per_page=5 was sent
        _call_args = mock_session.get.call_args
        params = _call_args[1].get("params", {})
        assert params["per_page"] == 5

    # ------------------------------------------------------------------
    # search_coin
    # ------------------------------------------------------------------

    def test_search_coin_found(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Search for a coin by name."""
        mock_session.get.return_value = _mock_response({
            "coins": [
                {"id": "bitcoin", "name": "Bitcoin", "symbol": "BTC"},
                {"id": "bitcoin-cash", "name": "Bitcoin Cash", "symbol": "BCH"},
            ],
        })

        result = client.search_coin("bitcoin")

        assert len(result) == 2
        assert result[0]["id"] == "bitcoin"

    def test_search_coin_no_results(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Search returns empty list when no matches."""
        mock_session.get.return_value = _mock_response({"coins": []})

        result = client.search_coin("nonexistent12345")

        assert result == []

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_rate_limit_error(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise RateLimitError on HTTP 429."""
        mock_session.get.return_value = _mock_response(
            {"error": "rate limited"},
            status_code=429,
            headers={"Retry-After": "30"},
        )

        with pytest.raises(RateLimitError) as exc:
            client.get_price(["bitcoin"])

        assert "30" in str(exc.value)

    def test_rate_limit_error_no_retry_header(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Handle 429 without Retry-After header gracefully."""
        mock_session.get.return_value = _mock_response(
            {"error": "rate limited"},
            status_code=429,
        )

        with pytest.raises(RateLimitError):
            client.get_price(["bitcoin"])

    def test_api_error_404(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise APIError on 404 (endpoint not found)."""
        mock_session.get.return_value = _mock_response(
            {"error": "not found"},
            status_code=404,
        )

        with pytest.raises(APIError) as exc:
            client.get_price(["bitcoin"])

        assert exc.value.status_code == 404

    def test_api_error_500(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise APIError on server error."""
        mock_session.get.return_value = _mock_response(
            {"error": "server error"},
            status_code=500,
        )

        with pytest.raises(APIError) as exc:
            client.get_price(["bitcoin"])

        assert exc.value.status_code == 500

    def test_network_error_connection(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Wrap ConnectionError in our NetworkError."""
        mock_session.get.side_effect = requests.ConnectionError("connection refused")

        with pytest.raises(NetworkError) as exc:
            client.get_price(["bitcoin"])

        assert "NetworkError" in type(exc.value).__name__

    def test_network_error_timeout(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Wrap Timeout in our NetworkError."""
        mock_session.get.side_effect = requests.Timeout("timed out")

        with pytest.raises(NetworkError):
            client.get_price(["bitcoin"])


    # ------------------------------------------------------------------
    # get_coin_history
    # ------------------------------------------------------------------

    def test_get_coin_history_success(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Fetch historical prices for a coin."""
        mock_session.get.return_value = _mock_response({
            "prices": [
                [1700000000000, 45000.0],
                [1700086400000, 46000.0],
                [1700172800000, 45500.0],
            ],
            "market_caps": [],
            "total_volumes": [],
        })

        result = client.get_coin_history("bitcoin", days=7)

        assert "prices" in result
        assert len(result["prices"]) == 3

    def test_get_coin_history_bad_response(self, client: CoinGeckoClient, mock_session: MagicMock):
        """Raise APIError when response has no 'prices' key."""
        mock_session.get.return_value = _mock_response({"error": "not found"})

        with pytest.raises(APIError):
            client.get_coin_history("invalidcoin", days=7)


class TestRateLimiter:
    """Tests for the RateLimiter."""

    def test_no_wait_under_limit(self):
        """RateLimiter doesn't block when under the limit."""
        limiter = RateLimiter(max_calls=5, window_seconds=60.0)
        for _ in range(5):
            limiter.wait_if_needed()

        # All 5 calls went through — no exception expected
        assert len(limiter._timestamps) == 5

    def test_cleans_old_timestamps(self):
        """RateLimiter drops timestamps outside the window."""
        limiter = RateLimiter(max_calls=5, window_seconds=1.0)

        # Make some calls with a tiny delay
        import time
        for _ in range(3):
            limiter.wait_if_needed()
            time.sleep(0.01)

        assert len(limiter._timestamps) == 3
