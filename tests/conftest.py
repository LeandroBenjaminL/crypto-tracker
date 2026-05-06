"""
Fixtures compartidas para todos los tests de crypto-tracker.

Acá van las fixtures que se repiten en varios archivos de test:
mocks de servicios, helpers de datos, etc.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.models import CoinSearchResult, Cryptocurrency, PriceData

# ---------------------------------------------------------------------------
# API Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_price_service() -> MagicMock:
    """Mock genérico de PriceService."""
    return MagicMock()


@pytest.fixture
def mock_favorites_manager() -> MagicMock:
    """Mock genérico de FavoritesManager."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Domain object builders
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_bitcoin() -> Cryptocurrency:
    """Una Cryptocurrency de Bitcoin para tests."""
    return Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1)


@pytest.fixture
def sample_ethereum() -> Cryptocurrency:
    """Una Cryptocurrency de Ethereum para tests."""
    return Cryptocurrency(id="ethereum", symbol="eth", name="Ethereum", rank=2)


@pytest.fixture
def sample_price_data() -> PriceData:
    """PriceData de Bitcoin con valores típicos."""
    return PriceData(
        coin_id="bitcoin",
        price=45000.50,
        change_24h=2.5,
        volume_24h=25_000_000_000,
        market_cap=850_000_000_000,
    )


@pytest.fixture
def sample_coin_result(sample_bitcoin: Cryptocurrency, sample_price_data: PriceData) -> CoinSearchResult:
    """CoinSearchResult completo de Bitcoin."""
    return CoinSearchResult(coin=sample_bitcoin, price_data=sample_price_data)
