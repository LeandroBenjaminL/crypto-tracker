"""
Tests for the CLI commands using Click's CliRunner.

We mock PriceService to avoid network calls and test the CLI layer
in isolation: argument parsing, option handling, output formatting,
and error mapping.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from src.cli.commands import (
    cli,
    list_coins,
    price,
    search,
)
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.models import (
    CoinSearchResult,
    Cryptocurrency,
    PriceData,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_coin(
    coin_id: str = "bitcoin",
    symbol: str = "btc",
    name: str = "Bitcoin",
    rank: int = 1,
) -> Cryptocurrency:
    """Build a Cryptocurrency model for testing."""
    return Cryptocurrency(
        id=coin_id,
        symbol=symbol,
        name=name,
        rank=rank,
    )


def _make_price_data(
    coin_id: str = "bitcoin",
    price: float = 45_000.0,
    change_24h: float = 2.5,
    volume_24h: float = 1_000_000_000.0,
    market_cap: float = 900_000_000_000.0,
) -> PriceData:
    """Build a PriceData model for testing."""
    return PriceData(
        coin_id=coin_id,
        price=price,
        change_24h=change_24h,
        volume_24h=volume_24h,
        market_cap=market_cap,
    )


def _make_search_result(
    coin: Cryptocurrency | None = None,
    price_data: PriceData | None = None,
) -> CoinSearchResult:
    """Build a CoinSearchResult for testing."""
    return CoinSearchResult(
        coin=coin or _make_coin(),
        price_data=price_data,
    )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CliRunner for invoking commands."""
    return CliRunner()


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a mocked PriceService."""
    return MagicMock()


# ------------------------------------------------------------------
# Test groups
# ------------------------------------------------------------------


class TestCliVersion:
    """Tests for the top-level CLI group and version flag."""

    def test_cli_version_flag(self, runner: CliRunner):
        """--version should print the program name and version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "crypto-tracker" in result.output
        assert "0.1.0" in result.output

    def test_cli_help(self, runner: CliRunner):
        """The help text should mention available commands."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "price" in result.output
        assert "list-coins" in result.output
        assert "search" in result.output


class TestPriceCommand:
    """Tests for the `price` command."""

    def test_single_coin(self, runner: CliRunner, mock_service: MagicMock):
        """price btc should display the coin name, price and 24h change."""
        mock_service.get_price.return_value = _make_search_result(
            coin=_make_coin(),
            price_data=_make_price_data(),
        )

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "btc"])

        assert result.exit_code == 0
        assert "Bitcoin" in result.output
        assert "BTC" in result.output
        assert "45,000.00" in result.output or "$45,000.00" in result.output
        assert "2.50%" in result.output or "2.5" in result.output

    def test_multiple_coins(self, runner: CliRunner, mock_service: MagicMock):
        """price btc eth should display both coins."""
        mock_service.get_prices.return_value = [
            _make_search_result(
                coin=_make_coin(coin_id="bitcoin", symbol="btc", name="Bitcoin"),
                price_data=_make_price_data(coin_id="bitcoin"),
            ),
            _make_search_result(
                coin=_make_coin(coin_id="ethereum", symbol="eth", name="Ethereum", rank=2),
                price_data=_make_price_data(
                    coin_id="ethereum",
                    price=3_000.0,
                    change_24h=-1.2,
                ),
            ),
        ]

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "btc", "eth"])

        assert result.exit_code == 0
        assert "Bitcoin" in result.output
        assert "Ethereum" in result.output
        assert "BTC" in result.output
        assert "ETH" in result.output

    def test_with_currency_option(self, runner: CliRunner, mock_service: MagicMock):
        """price btc --currency eur should pass the currency to the service."""
        mock_service.get_price.return_value = _make_search_result(
            coin=_make_coin(),
            price_data=_make_price_data(price=42_000.0),
        )

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "btc", "--currency", "eur"])

        assert result.exit_code == 0
        mock_service.get_price.assert_called_once_with("btc", currency="eur")

    def test_coin_not_found(self, runner: CliRunner, mock_service: MagicMock):
        """A missing coin should print a friendly message to stderr."""
        mock_service.get_price.side_effect = CoinNotFoundError("fakecoin123")

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "fakecoin123"])

        assert result.exit_code == 0
        assert "Coin not found" in result.output

    def test_network_error(self, runner: CliRunner, mock_service: MagicMock):
        """A network error should print a network message to stderr."""
        mock_service.get_price.side_effect = NetworkError()

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "btc"])

        assert result.exit_code == 0
        assert "Network error" in result.output

    def test_rate_limit_error(self, runner: CliRunner, mock_service: MagicMock):
        """A rate limit error should print a wait-and-retry message to stderr."""
        mock_service.get_price.side_effect = RateLimitError(retry_after=60)

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["price", "btc"])

        assert result.exit_code == 0
        assert "rate limit" in result.output.lower()


class TestListCoinsCommand:
    """Tests for the `list-coins` command."""

    def test_default_limit(self, runner: CliRunner, mock_service: MagicMock):
        """list-coins with no options should show 10 coins by default."""
        mock_service.list_top.return_value = [
            _make_search_result(
                coin=_make_coin(rank=i),
                price_data=_make_price_data(),
            )
            for i in range(1, 11)
        ]

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["list-coins"])

        assert result.exit_code == 0
        mock_service.list_top.assert_called_once_with(limit=10, currency="usd")
        assert "Top 10 Cryptocurrencies" in result.output

    def test_custom_limit(self, runner: CliRunner, mock_service: MagicMock):
        """list-coins --limit 25 should pass limit=25 to the service."""
        mock_service.list_top.return_value = []

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["list-coins", "--limit", "25"])

        assert result.exit_code == 0
        mock_service.list_top.assert_called_once_with(limit=25, currency="usd")
        assert "Top 25 Cryptocurrencies" in result.output

    def test_with_currency_option(self, runner: CliRunner, mock_service: MagicMock):
        """list-coins --currency eur should pass the currency to the service."""
        mock_service.list_top.return_value = [
            _make_search_result(
                coin=_make_coin(),
                price_data=_make_price_data(),
            ),
        ]

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["list-coins", "--currency", "eur"])

        assert result.exit_code == 0
        mock_service.list_top.assert_called_once_with(limit=10, currency="eur")

    def test_empty_result(self, runner: CliRunner, mock_service: MagicMock):
        """An empty list from the service should still succeed."""
        mock_service.list_top.return_value = []

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["list-coins"])

        assert result.exit_code == 0
        assert "Top 10 Cryptocurrencies" in result.output

    def test_api_error(self, runner: CliRunner, mock_service: MagicMock):
        """An API error should be caught and printed to stderr."""
        mock_service.list_top.side_effect = APIError("server exploded", status_code=500)

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["list-coins"])

        assert result.exit_code == 0
        assert "API error" in result.output


class TestSearchCommand:
    """Tests for the `search` command."""

    def test_found_results(self, runner: CliRunner, mock_service: MagicMock):
        """search with a matching query should display results."""
        mock_service.search.return_value = [
            _make_coin(coin_id="bitcoin", symbol="btc", name="Bitcoin", rank=1),
            _make_coin(coin_id="bitcoin-cash", symbol="bch", name="Bitcoin Cash", rank=15),
        ]

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["search", "bitcoin"])

        assert result.exit_code == 0
        assert "Search results for 'bitcoin'" in result.output
        assert "Bitcoin" in result.output
        assert "Bitcoin Cash" in result.output
        assert "BTC" in result.output
        assert "BCH" in result.output

    def test_no_results(self, runner: CliRunner, mock_service: MagicMock):
        """search with no matches should display a friendly no-results message."""
        mock_service.search.return_value = []

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["search", "zzzzzzz"])

        assert result.exit_code == 0
        assert "No coins found matching 'zzzzzzz'" in result.output

    def test_error_handling(self, runner: CliRunner, mock_service: MagicMock):
        """A network error during search should be caught and printed to stderr."""
        mock_service.search.side_effect = NetworkError()

        with patch("src.cli.commands._build_service", return_value=mock_service):
            result = runner.invoke(cli, ["search", "bitcoin"])

        assert result.exit_code == 0
        assert "Network error" in result.output

    def test_search_calls_service_with_query(self, runner: CliRunner, mock_service: MagicMock):
        """The search command should pass the query argument to the service."""
        mock_service.search.return_value = []

        with patch("src.cli.commands._build_service", return_value=mock_service):
            runner.invoke(cli, ["search", "ethereum"])

        mock_service.search.assert_called_once_with("ethereum")
