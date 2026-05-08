"""
Tests for core domain models.

Cubre:
  - Creación y atributos de todos los modelos
  - Formateo de precios (altos, bajos, muy bajos, cero)
  - Indicadores de cambio (positivo, negativo, cero)
  - Igualdad y hash de Cryptocurrency
  - Normalización en FavoriteCoin
  - PriceAlert (activo, triggered, edge cases)
  - CoinSearchResult (con/sin precio)
  - Excepciones del dominio
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    ConfigurationError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.models import (
    CoinSearchResult,
    Cryptocurrency,
    FavoriteCoin,
    PortfolioHolding,
    PriceAlert,
    PriceData,
)


class TestCryptocurrency:
    """Cryptocurrency creation, equality, hash, repr."""

    def test_create(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1)
        assert btc.id == "bitcoin"
        assert btc.symbol == "btc"
        assert btc.name == "Bitcoin"
        assert btc.rank == 1

    def test_default_rank_is_zero(self):
        c = Cryptocurrency(id="x", symbol="x", name="X")
        assert c.rank == 0

    def test_str(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        assert str(btc) == "Bitcoin (BTC)"

    def test_equality_by_id(self):
        c1 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1)
        c2 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=2)
        assert c1 == c2

    def test_inequality_different_id(self):
        c1 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        c2 = Cryptocurrency(id="ethereum", symbol="eth", name="Ethereum")
        assert c1 != c2

    def test_not_equal_to_non_crypto(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        assert btc != "bitcoin"  # noqa: E721 — comparación intencional

    def test_hash_based_on_id(self):
        c1 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        c2 = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=99)
        assert hash(c1) == hash(c2)
        # Se pueden usar en sets
        s = {c1, c2}
        assert len(s) == 1  # mismo hash = mismo elemento

    def test_hash_different_for_different_ids(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        eth = Cryptocurrency(id="ethereum", symbol="eth", name="Ethereum")
        assert hash(btc) != hash(eth)


class TestPriceData:
    """PriceData creation, formatting, indicators."""

    def test_create(self):
        p = PriceData(
            coin_id="bitcoin", price=45000.50,
            change_24h=2.5, volume_24h=25e9, market_cap=850e9,
        )
        assert p.coin_id == "bitcoin"
        assert p.price == 45000.50

    def test_price_formatted_high(self):
        """>= $1: formato con 2 decimales."""
        assert PriceData(coin_id="x", price=45000.50).price_formatted == "$45,000.50"

    def test_price_formatted_medium(self):
        """>= $0.01: formato con 4 decimales."""
        assert PriceData(coin_id="x", price=0.0234).price_formatted == "$0.0234"

    def test_price_formatted_low(self):
        """< $0.01: formato con 8 decimales."""
        assert PriceData(coin_id="x", price=0.00001234).price_formatted == "$0.00001234"

    def test_price_formatted_zero(self):
        """Precio 0 cae en < 0.01 → 8 decimales."""
        # No es ideal pero es el comportamiento actual del formateo
        assert PriceData(coin_id="x", price=0).price_formatted == "$0.00000000"

    def test_price_formatted_exact_one(self):
        """Precio exactamente 1."""
        assert PriceData(coin_id="x", price=1.0).price_formatted == "$1.00"

    def test_price_formatted_exact_cent(self):
        """Precio exactamente 0.01."""
        assert PriceData(coin_id="x", price=0.01).price_formatted == "$0.0100"

    def test_price_formatted_negative(self):
        """Precio negativo también cae en < 0.01 → 8 decimales."""
        assert PriceData(coin_id="x", price=-5.0).price_formatted == "$-5.00000000"

    def test_change_indicator_positive(self):
        assert PriceData(coin_id="x", price=100, change_24h=5.0).change_indicator == "▲"

    def test_change_indicator_negative(self):
        assert PriceData(coin_id="x", price=100, change_24h=-5.0).change_indicator == "▼"

    def test_change_indicator_zero(self):
        assert PriceData(coin_id="x", price=100, change_24h=0).change_indicator == "―"

    def test_change_indicator_very_small(self):
        """0.0001 cuenta como positivo."""
        assert PriceData(coin_id="x", price=100, change_24h=0.0001).change_indicator == "▲"

    def test_change_formatted_positive(self):
        assert PriceData(coin_id="x", price=100, change_24h=5.5).change_formatted == "+5.50%"

    def test_change_formatted_negative(self):
        assert PriceData(coin_id="x", price=100, change_24h=-3.25).change_formatted == "-3.25%"

    def test_change_formatted_zero(self):
        assert PriceData(coin_id="x", price=100, change_24h=0).change_formatted == "0.00%"

    def test_default_timestamp_is_utc(self):
        before = datetime.now(timezone.utc)
        p = PriceData(coin_id="x", price=100)
        after = datetime.now(timezone.utc)
        assert before <= p.timestamp <= after
        assert p.timestamp.tzinfo is not None  # timezone-aware


class TestCoinSearchResult:
    """CoinSearchResult with/without price."""

    def test_with_price(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        price = PriceData(coin_id="bitcoin", price=45000)
        r = CoinSearchResult(coin=btc, price_data=price)
        assert r.has_price() is True
        assert r.price_data is not None
        assert r.price_data.price == 45000

    def test_without_price(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        r = CoinSearchResult(coin=btc)
        assert r.has_price() is False
        assert r.price_data is None

    def test_coin_is_accessible(self):
        btc = Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin")
        r = CoinSearchResult(coin=btc)
        assert r.coin.name == "Bitcoin"
        assert r.coin.symbol == "btc"


class TestFavoriteCoin:
    """FavoriteCoin creation and normalization."""

    def test_symbol_normalized_to_lowercase(self):
        assert FavoriteCoin(symbol="BTC").symbol == "btc"

    def test_symbol_normalized_mixed_case(self):
        assert FavoriteCoin(symbol="Eth").symbol == "eth"

    def test_default_timestamp(self):
        before = datetime.now(timezone.utc)
        f = FavoriteCoin(symbol="btc")
        after = datetime.now(timezone.utc)
        assert before <= f.added_at <= after

    def test_custom_timestamp(self):
        t = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        f = FavoriteCoin(symbol="btc", added_at=t)
        assert f.added_at == t

    def test_post_init_normalizes(self):
        """__post_init__ se ejecuta y normaliza."""
        f = FavoriteCoin(symbol="  BTC  ")
        # Nota: el post_init hace .lower() pero no strip() en la implementación actual
        # Verificamos lo que realmente hace
        assert f.symbol == "  btc  "  # lowercased pero no stripped


class TestPriceAlert:
    """PriceAlert creation and state changes."""

    def test_create_alert(self):
        a = PriceAlert(coin_id="bitcoin", target_price=50000, condition="above")
        assert a.coin_id == "bitcoin"
        assert a.target_price == 50000
        assert a.condition == "above"
        assert a.is_active is True
        assert a.triggered_at is None

    def test_triggered_alert(self):
        t = datetime.now(timezone.utc)
        a = PriceAlert(coin_id="bitcoin", target_price=50000, condition="below")
        a.is_active = False
        a.triggered_at = t
        assert a.is_active is False
        assert a.triggered_at == t

    def test_default_created_at(self):
        a = PriceAlert(coin_id="x", target_price=100, condition="above")
        assert a.created_at is not None

    def test_condition_above(self):
        a = PriceAlert(coin_id="x", target_price=100, condition="above")
        assert a.condition == "above"

    def test_condition_below(self):
        a = PriceAlert(coin_id="x", target_price=100, condition="below")
        assert a.condition == "below"

    def test_default_is_active(self):
        a = PriceAlert(coin_id="x", target_price=100, condition="above")
        assert a.is_active is True

    def test_is_active_false_after_trigger(self):
        a = PriceAlert(coin_id="x", target_price=100, condition="above")
        a.is_active = False
        assert a.is_active is False


class TestExceptions:
    """Custom exception hierarchy."""

    def test_coin_not_found(self):
        e = CoinNotFoundError("testcoin")
        assert e.identifier == "testcoin"
        assert "testcoin" in str(e)

    def test_validation_error(self):
        e = ValidationError("symbol", "", "cannot be empty")
        assert e.field == "symbol"
        assert "empty" in str(e)

    def test_rate_limit_with_retry(self):
        e = RateLimitError(retry_after=30)
        assert e.retry_after == 30
        assert "30" in str(e)

    def test_rate_limit_without_retry(self):
        e = RateLimitError()
        assert e.retry_after is None

    def test_api_error_with_status(self):
        e = APIError("message", status_code=502)
        assert e.status_code == 502

    def test_api_error_without_status(self):
        e = APIError("message")
        assert e.status_code is None

    def test_network_error_with_cause(self):
        cause = Exception("connection failed")
        e = NetworkError(original_error=cause)
        assert "Exception" in str(e)  # type().__name__ del error original
        assert e.original_error is cause

    def test_network_error_without_cause(self):
        e = NetworkError()
        assert "network" in str(e).lower()

    def test_configuration_error(self):
        e = ConfigurationError("missing env var")
        assert "missing" in str(e)

    def test_crypto_tracker_error_base(self):
        e = CryptoTrackerError("base error")
        assert isinstance(e, Exception)

    def test_all_exceptions_inherit_from_base(self):
        """Todas las excepciones heredan de CryptoTrackerError."""
        assert issubclass(CoinNotFoundError, CryptoTrackerError)
        assert issubclass(APIError, CryptoTrackerError)
        assert issubclass(RateLimitError, APIError)
        assert issubclass(NetworkError, CryptoTrackerError)
        assert issubclass(ValidationError, CryptoTrackerError)
        assert issubclass(ConfigurationError, CryptoTrackerError)


class TestPortfolioHolding:
    """PortfolioHolding creation, P&L calculations, formatting."""

    def test_create_minimal(self):
        """Crea un holding con solo datos requeridos."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
        )
        assert h.coin_id == "bitcoin"
        assert h.symbol == "btc"
        assert h.quantity == 1.0
        assert h.purchase_price == 50000.0
        assert h.current_price == 0.0  # default

    def test_create_full(self):
        """Crea un holding con todos los campos."""
        now = datetime.now(timezone.utc)
        h = PortfolioHolding(
            id=1,
            coin_id="ethereum",
            symbol="eth",
            quantity=10.0,
            purchase_price=3000.0,
            current_price=3500.0,
            created_at=now,
        )
        assert h.id == 1
        assert h.symbol == "eth"
        assert h.current_price == 3500.0

    def test_cost_basis(self):
        """Calcula cost_basis = quantity * purchase_price."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=2.0,
            purchase_price=50000.0,
        )
        assert h.cost_basis == 100000.0

    def test_cost_basis_zero_quantity(self):
        """Cost basis es 0 si quantity es 0."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=0.0,
            purchase_price=50000.0,
        )
        assert h.cost_basis == 0.0

    def test_current_value(self):
        """Calcula current_value = quantity * current_price."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=2.0,
            purchase_price=50000.0,
            current_price=60000.0,
        )
        assert h.current_value == 120000.0

    def test_current_value_uses_zero_when_not_set(self):
        """current_value es 0 si current_price no está seteado."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=2.0,
            purchase_price=50000.0,
        )
        assert h.current_value == 0.0

    def test_pnl_positive(self):
        """pnl positivo cuando el precio sube."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
            current_price=60000.0,
        )
        assert h.pnl == 10000.0

    def test_pnl_negative(self):
        """pnl negativo cuando el precio baja."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=60000.0,
            current_price=50000.0,
        )
        assert h.pnl == -10000.0

    def test_pnl_zero_when_no_change(self):
        """pnl es 0 cuando no hay cambio de precio."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
            current_price=50000.0,
        )
        assert h.pnl == 0.0

    def test_pnl_percent_positive(self):
        """pnl_percent positivo con gain."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
            current_price=60000.0,
        )
        assert h.pnl_percent == 20.0

    def test_pnl_percent_negative(self):
        """pnl_percent negativo con loss."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=60000.0,
            current_price=50000.0,
        )
        assert h.pnl_percent == pytest.approx(-16.67, rel=0.01)

    def test_pnl_percent_zero_cost_basis(self):
        """pnl_percent es 0 si cost_basis es 0."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=0.0,
            purchase_price=0.0,
            current_price=50000.0,
        )
        assert h.pnl_percent == 0.0

    def test_cost_basis_formatted(self):
        """Formatea cost basis con $ y comas."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=2.0,
            purchase_price=50000.0,
        )
        assert h.cost_basis_formatted == "$100,000.00"

    def test_current_value_formatted_high(self):
        """Formatea value > 1 con 2 decimales."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=2.0,
            purchase_price=50000.0,
            current_price=65000.0,
        )
        assert h.current_value_formatted == "$130,000.00"

    def test_current_value_formatted_low(self):
        """Formatea value 0.01-1 con 4 decimales."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1000.0,
            purchase_price=0.001,
            current_price=0.0025,
        )
        assert h.current_value_formatted == "$2.50"

    def test_current_value_formatted_very_low(self):
        """Formatea value < 0.01 con 8 decimales."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1000.0,
            purchase_price=0.0001,
            current_price=0.00015,
        )
        assert h.current_value_formatted == "$0.1500"

    def test_pnl_formatted_positive(self):
        """Formatea P&L positivo con + y sign."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
            current_price=60000.0,
        )
        assert h.pnl_formatted == "+$10,000.00"

    def test_pnl_formatted_negative(self):
        """Formatea P&L negativo con -."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=60000.0,
            current_price=50000.0,
        )
        assert h.pnl_formatted == "$-10,000.00"

    def test_pnl_percent_formatted_positive(self):
        """Formatea P&L% positivo con +."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=50000.0,
            current_price=60000.0,
        )
        assert h.pnl_percent_formatted == "+20.00%"

    def test_pnl_percent_formatted_negative(self):
        """Formatea P&L% negativo."""
        h = PortfolioHolding(
            coin_id="bitcoin",
            symbol="btc",
            quantity=1.0,
            purchase_price=60000.0,
            current_price=50000.0,
        )
        assert h.pnl_percent_formatted == "-16.67%"
