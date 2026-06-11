"""
Tests para PortfolioRepository con SQLite in-memory.

SQLite in-memory es ideal para testear repositorios SQLAlchemy:
  - Rápido (no necesita servidor)
  - Se auto-limpia entre tests
  - Misma API que PostgreSQL para operaciones CRUD básicas

Cubre:
  - CRUD completo (create, list, get_by_id, update, delete)
  - Validaciones de dominio (quantity > 0, purchase_price >= 0)
  - Normalización de símbolos y coin_ids
  - Portfolio summary con cálculos de P&L
  - Edge cases: holding inexistente, DB caída
"""

from __future__ import annotations

import pytest

from src.adapters.database import PortfolioRepository


@pytest.fixture
def repo() -> PortfolioRepository:
    """Create a PortfolioRepository backed by SQLite in-memory."""
    return PortfolioRepository("sqlite://")


# ======================================================================
# CREATE & LIST
# ======================================================================


class TestCreateAndList:
    """Tests para crear holdings y listarlos."""

    def test_create_and_list(self, repo: PortfolioRepository) -> None:
        """Crear un holding hace que aparezca en la lista."""
        h = repo.create(coin_id="bitcoin", symbol="btc", quantity=1.5, purchase_price=30000)
        assert h.id > 0
        assert h.coin_id == "bitcoin"
        assert h.symbol == "btc"
        assert h.quantity == 1.5
        assert h.purchase_price == 30000

        holdings = repo.list_all()
        assert len(holdings) == 1
        assert holdings[0].id == h.id

    def test_create_multiple(self, repo: PortfolioRepository) -> None:
        """Se pueden crear varios holdings y listarlos en orden descendente."""
        h1 = repo.create("bitcoin", "btc", 1.0, 30000)
        h2 = repo.create("ethereum", "eth", 10.0, 2000)
        h3 = repo.create("solana", "sol", 100.0, 50)

        holdings = repo.list_all()
        assert len(holdings) == 3
        # Orden descendente por created_at: el último creado es el primero
        assert holdings[0].id == h3.id
        assert holdings[1].id == h2.id
        assert holdings[2].id == h1.id

    def test_create_normalizes_symbol(self, repo: PortfolioRepository) -> None:
        """El símbolo se normaliza a minúsculas y se le sacan espacios."""
        h = repo.create("bitcoin", "  BTC  ", 1.0, 30000)
        assert h.symbol == "btc"

    def test_create_normalizes_coin_id(self, repo: PortfolioRepository) -> None:
        """El coin_id se normaliza a minúsculas y se le sacan espacios."""
        h = repo.create("  Bitcoin  ", "btc", 1.0, 30000)
        assert h.coin_id == "bitcoin"

    def test_create_quantity_zero_raises(self, repo: PortfolioRepository) -> None:
        """Cantidad cero levanta ValueError."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            repo.create("bitcoin", "btc", 0, 30000)

    def test_create_quantity_negative_raises(self, repo: PortfolioRepository) -> None:
        """Cantidad negativa levanta ValueError."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            repo.create("bitcoin", "btc", -1, 30000)

    def test_create_purchase_price_negative_raises(self, repo: PortfolioRepository) -> None:
        """Precio de compra negativo levanta ValueError."""
        with pytest.raises(ValueError, match="Purchase price cannot be negative"):
            repo.create("bitcoin", "btc", 1.0, -100)

    def test_create_purchase_price_zero_is_valid(self, repo: PortfolioRepository) -> None:
        """Precio de compra cero es válido (ej: token minado gratis)."""
        h = repo.create("bitcoin", "btc", 1.0, 0)
        assert h.purchase_price == 0.0

    def test_list_empty(self, repo: PortfolioRepository) -> None:
        """Listar sin holdings devuelve lista vacía."""
        assert repo.list_all() == []


# ======================================================================
# GET BY ID
# ======================================================================


class TestGetById:
    """Tests para buscar holdings por ID."""

    def test_get_by_id_existing(self, repo: PortfolioRepository) -> None:
        """Buscar un holding existente por ID lo devuelve."""
        created = repo.create("bitcoin", "btc", 1.5, 30000)
        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.coin_id == "bitcoin"
        assert found.quantity == 1.5

    def test_get_by_id_nonexistent(self, repo: PortfolioRepository) -> None:
        """Buscar un ID que no existe devuelve None."""
        assert repo.get_by_id(99999) is None

    def test_get_by_id_after_delete(self, repo: PortfolioRepository) -> None:
        """Buscar un holding después de eliminarlo devuelve None."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        repo.delete(h.id)
        assert repo.get_by_id(h.id) is None

    def test_get_by_id_zero(self, repo: PortfolioRepository) -> None:
        """ID cero (no existe) devuelve None."""
        assert repo.get_by_id(0) is None


# ======================================================================
# UPDATE
# ======================================================================


class TestUpdate:
    """Tests para actualizar holdings."""

    def test_update_quantity(self, repo: PortfolioRepository) -> None:
        """Actualizar cantidad cambia la cantidad."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        updated = repo.update(h.id, quantity=2.5)
        assert updated is not None
        assert updated.quantity == 2.5
        assert updated.purchase_price == 30000  # Sin cambios

    def test_update_purchase_price(self, repo: PortfolioRepository) -> None:
        """Actualizar precio de compra cambia el precio."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        updated = repo.update(h.id, purchase_price=35000)
        assert updated is not None
        assert updated.purchase_price == 35000
        assert updated.quantity == 1.0  # Sin cambios

    def test_update_both(self, repo: PortfolioRepository) -> None:
        """Actualizar cantidad y precio juntos."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        updated = repo.update(h.id, quantity=2.0, purchase_price=25000)
        assert updated is not None
        assert updated.quantity == 2.0
        assert updated.purchase_price == 25000

    def test_update_nonexistent_returns_none(self, repo: PortfolioRepository) -> None:
        """Actualizar un holding que no existe devuelve None."""
        assert repo.update(99999, quantity=1.0) is None

    def test_update_quantity_zero_raises(self, repo: PortfolioRepository) -> None:
        """Actualizar cantidad a cero levanta ValueError."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        with pytest.raises(ValueError, match="Quantity must be positive"):
            repo.update(h.id, quantity=0)

    def test_update_quantity_negative_raises(self, repo: PortfolioRepository) -> None:
        """Actualizar cantidad a negativo levanta ValueError."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        with pytest.raises(ValueError, match="Quantity must be positive"):
            repo.update(h.id, quantity=-5)

    def test_update_purchase_price_negative_raises(self, repo: PortfolioRepository) -> None:
        """Actualizar precio a negativo levanta ValueError."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        with pytest.raises(ValueError, match="Purchase price cannot be negative"):
            repo.update(h.id, purchase_price=-100)

    def test_update_purchase_price_zero(self, repo: PortfolioRepository) -> None:
        """Actualizar precio a cero es válido."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        updated = repo.update(h.id, purchase_price=0)
        assert updated is not None
        assert updated.purchase_price == 0.0

    def test_update_no_changes(self, repo: PortfolioRepository) -> None:
        """Llamar update sin cambios devuelve el holding igual."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        updated = repo.update(h.id)
        assert updated is not None
        assert updated.quantity == 1.0
        assert updated.purchase_price == 30000

    def test_update_sets_updated_at(self, repo: PortfolioRepository) -> None:
        """Update cambia updated_at a un timestamp no nulo."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        assert h.updated_at is None  # Recién creado
        updated = repo.update(h.id, quantity=2.0)
        assert updated is not None
        assert updated.updated_at is not None
        assert updated.updated_at != h.updated_at


# ======================================================================
# DELETE
# ======================================================================


class TestDelete:
    """Tests para eliminar holdings."""

    def test_delete_existing(self, repo: PortfolioRepository) -> None:
        """Eliminar un holding existente devuelve True y desaparece."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        assert repo.delete(h.id) is True
        assert repo.get_by_id(h.id) is None
        assert len(repo.list_all()) == 0

    def test_delete_nonexistent(self, repo: PortfolioRepository) -> None:
        """Eliminar un holding que no existe devuelve False."""
        assert repo.delete(99999) is False

    def test_delete_then_list(self, repo: PortfolioRepository) -> None:
        """Eliminar un holding no afecta a los otros."""
        h1 = repo.create("bitcoin", "btc", 1.0, 30000)
        h2 = repo.create("ethereum", "eth", 10.0, 2000)
        repo.delete(h1.id)
        holdings = repo.list_all()
        assert len(holdings) == 1
        assert holdings[0].id == h2.id


# ======================================================================
# PORTFOLIO SUMMARY
# ======================================================================


class TestGetSummary:
    """Tests para el cálculo del resumen del portfolio."""

    def test_empty_portfolio(self, repo: PortfolioRepository) -> None:
        """Portfolio vacío devuelve todo en cero."""
        summary = repo.get_summary({})
        assert summary == {
            "total_value": 0.0,
            "total_cost": 0.0,
            "total_pnl": 0.0,
            "pnl_percent": 0.0,
            "holdings_count": 0,
        }

    def test_single_holding_profit(self, repo: PortfolioRepository) -> None:
        """Un holding con ganancia calcula P&L correctamente."""
        repo.create("bitcoin", "btc", 1.0, 30000)
        summary = repo.get_summary({"bitcoin": 45000})
        assert summary["total_value"] == 45000.0
        assert summary["total_cost"] == 30000.0
        assert summary["total_pnl"] == 15000.0
        assert summary["pnl_percent"] == 50.0
        assert summary["holdings_count"] == 1

    def test_single_holding_loss(self, repo: PortfolioRepository) -> None:
        """Un holding con pérdida calcula P&L negativo."""
        repo.create("bitcoin", "btc", 1.0, 30000)
        summary = repo.get_summary({"bitcoin": 15000})
        assert summary["total_pnl"] == -15000.0
        assert summary["pnl_percent"] == -50.0

    def test_multiple_holdings(self, repo: PortfolioRepository) -> None:
        """Múltiples holdings agregan costos y valores."""
        repo.create("bitcoin", "btc", 1.0, 30000)  # cost=30000
        repo.create("ethereum", "eth", 10.0, 2000)  # cost=20000
        # Total cost = 50000
        summary = repo.get_summary({"bitcoin": 45000, "ethereum": 2500})
        # Total value = 45000 + 25000 = 70000
        # P&L = 70000 - 50000 = 20000
        assert summary["total_value"] == 70000.0
        assert summary["total_cost"] == 50000.0
        assert summary["total_pnl"] == 20000.0
        assert summary["pnl_percent"] == 40.0
        assert summary["holdings_count"] == 2

    def test_coin_id_not_in_prices(self, repo: PortfolioRepository) -> None:
        """Si un coin_id no está en current_prices, usa purchase_price como fallback."""
        repo.create("bitcoin", "btc", 1.0, 30000)
        # No pasamos bitcoin en current_prices
        summary = repo.get_summary({})
        # Fallback: current_price = purchase_price = 30000
        assert summary["total_value"] == 30000.0
        assert summary["total_cost"] == 30000.0
        assert summary["total_pnl"] == 0.0
        assert summary["pnl_percent"] == 0.0

    def test_coin_id_in_prices_after_fallback(self, repo: PortfolioRepository) -> None:
        """Mezcla: algunos IDs están en prices, otros no."""
        repo.create("bitcoin", "btc", 1.0, 30000)  # tiene price
        repo.create("unknown-coin", "unk", 10.0, 100)  # no tiene price -> fallback
        summary = repo.get_summary({"bitcoin": 45000})
        # bitcoin: value=45000, cost=30000
        # unknown: value=1000 (fallback), cost=1000
        # Total: value=46000, cost=31000, pnl=15000
        assert summary["total_value"] == 46000.0
        assert summary["total_cost"] == 31000.0
        assert summary["total_pnl"] == 15000.0

    def test_quantity_with_decimals(self, repo: PortfolioRepository) -> None:
        """Cantidades con decimales se calculan correctamente."""
        repo.create("bitcoin", "btc", 0.5, 30000)  # cost=15000
        summary = repo.get_summary({"bitcoin": 45000})
        # value = 0.5 * 45000 = 22500
        assert summary["total_value"] == 22500.0
        assert summary["total_cost"] == 15000.0
        assert summary["total_pnl"] == 7500.0

    def test_no_holdings_after_delete(self, repo: PortfolioRepository) -> None:
        """Portfolio vacío después de eliminar todo."""
        h = repo.create("bitcoin", "btc", 1.0, 30000)
        repo.delete(h.id)
        summary = repo.get_summary({"bitcoin": 45000})
        assert summary == {
            "total_value": 0.0,
            "total_cost": 0.0,
            "total_pnl": 0.0,
            "pnl_percent": 0.0,
            "holdings_count": 0,
        }


# ======================================================================
# ERROR HANDLING
# ======================================================================


class TestRepositoryErrors:
    """Tests para manejo de errores del repositorio."""

    def test_error_db_down(self) -> None:
        """Si la base de datos no existe, levanta error de conexión."""
        with pytest.raises(Exception):
            PortfolioRepository("postgresql://nadie:1234@localhost:9999/nonexistent")

    def test_create_normalizes_invalid_symbol(self, repo: PortfolioRepository) -> None:
        """Símbolo con solo espacios se convierte a string vacío (no ideal pero no explota)."""
        # Esto no debería pasar en producción, pero verificamos que no crashea
        h = repo.create("bitcoin", "  ", 1.0, 30000)
        assert h.symbol == ""

    def test_list_after_db_connection_error(self) -> None:
        """Simular DB caída: SQLite con ruta inválida."""
        with pytest.raises(Exception):
            PortfolioRepository("/invalid/path/that/does/not/exist/db.sqlite")
