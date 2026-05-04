"""
Tests for core models.

These tests validate that our data models work correctly.
No external dependencies are mocked - we test pure Python behavior.
"""

from datetime import datetime, timezone

from src.core.models import (
    Cryptocurrency,
    PriceData,
    CoinSearchResult,
    FavoriteCoin,
    PriceAlert,
)
from src.core.exceptions import (
    CoinNotFoundError,
    ValidationError,
)


class TestCryptocurrency:
    """Tests for Cryptocurrency dataclass."""

    def test_create_cryptocurrency(self):
        """Test basic cryptocurrency creation."""
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1)

        assert btc.id == "bitcoin"
        assert btc.symbol == "btc"
        assert btc.name == "Bitcoin"
        assert btc.rank == 1

    def test_cryptocurrency_str(self):
        """Test string representation."""
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")

        assert str(btc) == "Bitcoin (BTC)"

    def test_cryptocurrency_default_rank(self):
        """Test that rank defaults to 0."""
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")

        assert btc.rank == 0

    def test_cryptocurrency_equality(self):
        """Test that cryptocurrencies with same id are equal."""
        btc1 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1)
        btc2 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=2)

        # They should be equal because they have the same id
        assert btc1 == btc2


class TestPriceData:
    """Tests for PriceData dataclass."""

    def test_create_price_data(self):
        """Test basic price data creation."""
        price = PriceData(
            coin_id="bitcoin",
            price=45000.50,
            change_24h=2.5,
            volume_24h=25000000000,
            market_cap=850000000000
        )

        assert price.coin_id == "bitcoin"
        assert price.price == 45000.50
        assert price.change_24h == 2.5

    def test_price_formatted_high_price(self):
        """Test price formatting for high values (> $1)."""
        price = PriceData(coin_id="bitcoin", price=45000.50)

        assert price.price_formatted == "$45,000.50"

    def test_price_formatted_low_price(self):
        """Test price formatting for low values (>$0.01, <$1)."""
        price = PriceData(coin_id="bitcoin", price=0.0234)

        assert price.price_formatted == "$0.0234"

    def test_price_formatted_very_low_price(self):
        """Test price formatting for very low values (<$0.01)."""
        price = PriceData(coin_id="bitcoin", price=0.00001234)

        assert price.price_formatted == "$0.00001234"

    def test_change_indicator_positive(self):
        """Test change indicator for positive change."""
        price = PriceData(coin_id="bitcoin", price=100, change_24h=5.0)

        assert price.change_indicator == "▲"

    def test_change_indicator_negative(self):
        """Test change indicator for negative change."""
        price = PriceData(coin_id="bitcoin", price=100, change_24h=-5.0)

        assert price.change_indicator == "▼"

    def test_change_indicator_zero(self):
        """Test change indicator for zero change."""
        price = PriceData(coin_id="bitcoin", price=100, change_24h=0)

        assert price.change_indicator == "―"

    def test_change_formatted_positive(self):
        """Test change formatting for positive values."""
        price = PriceData(coin_id="bitcoin", price=100, change_24h=5.5)

        assert price.change_formatted == "+5.50%"

    def test_change_formatted_negative(self):
        """Test change formatting for negative values."""
        price = PriceData(coin_id="bitcoin", price=100, change_24h=-3.25)

        assert price.change_formatted == "-3.25%"

    def test_default_timestamp(self):
        """Test that timestamp defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        price = PriceData(coin_id="bitcoin", price=100)
        after = datetime.now(timezone.utc)

        assert before <= price.timestamp <= after


class TestCoinSearchResult:
    """Tests for CoinSearchResult dataclass."""

    def test_create_with_price(self):
        """Test creating result with price data."""
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        price = PriceData(coin_id="bitcoin", price=45000)
        result = CoinSearchResult(coin=btc, price_data=price)

        assert result.has_price() is True
        assert result.coin.name == "Bitcoin"
        assert result.price_data is not None
        assert result.price_data.price == 45000

    def test_create_without_price(self):
        """Test creating result without price data."""
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        result = CoinSearchResult(coin=btc)

        assert result.has_price() is False
        assert result.price_data is None


class TestFavoriteCoin:
    """Tests for FavoriteCoin dataclass."""

    def test_create_favorite(self):
        """Test basic favorite creation."""
        fav = FavoriteCoin(symbol="BTC")

        assert fav.symbol == "btc"  # Normalized to lowercase
        assert fav.added_at is not None

    def test_symbol_normalization(self):
        """Test that symbols are normalized to lowercase."""
        fav = FavoriteCoin(symbol="Eth")

        assert fav.symbol == "eth"

    def test_custom_added_at(self):
        """Test custom added_at timestamp."""
        custom_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        fav = FavoriteCoin(symbol="btc", added_at=custom_time)

        assert fav.added_at == custom_time


class TestPriceAlert:
    """Tests for PriceAlert dataclass."""

    def test_create_alert(self):
        """Test basic alert creation."""
        alert = PriceAlert(
            coin_id="bitcoin",
            target_price=50000,
            condition="above"
        )

        assert alert.coin_id == "bitcoin"
        assert alert.target_price == 50000
        assert alert.condition == "above"
        assert alert.is_active is True
        assert alert.triggered_at is None

    def test_triggered_alert(self):
        """Test triggered alert."""
        triggered_time = datetime.now(timezone.utc)
        alert = PriceAlert(
            coin_id="bitcoin",
            target_price=50000,
            condition="above"
        )
        alert.triggered_at = triggered_time
        alert.is_active = False

        assert alert.is_active is False
        assert alert.triggered_at == triggered_time


class TestExceptions:
    """Tests for custom exceptions."""

    def test_coin_not_found_error(self):
        """Test CoinNotFoundError."""
        error = CoinNotFoundError("notexist")

        assert error.identifier == "notexist"
        assert "notexist" in str(error)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("symbol", "", "cannot be empty")

        assert error.field == "symbol"
        assert "empty" in str(error)
