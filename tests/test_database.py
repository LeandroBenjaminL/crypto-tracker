"""
Tests para FavoritesRepository con SQLite in-memory.

SQLite in-memory es ideal para testear repositorios SQLAlchemy:
  - Rápido (no necesita servidor)
  - Se auto-limpia entre tests
  - Misma API que PostgreSQL para operaciones CRUD básicas
"""

from __future__ import annotations

import pytest

from src.adapters.database import FavoritesRepository


@pytest.fixture
def repo() -> FavoritesRepository:
    """Create a FavoritesRepository backed by SQLite in-memory."""
    return FavoritesRepository("sqlite://")


class TestFavoritesRepository:
    """Tests para CRUD de favoritos en base de datos."""

    def test_add_and_list(self, repo: FavoritesRepository):
        """Agregar un favorito hace que aparezca en la lista."""
        repo.add("btc")
        favs = repo.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "btc"

    def test_add_is_idempotent(self, repo: FavoritesRepository):
        """Agregar el mismo favorito dos veces no crea duplicados."""
        repo.add("btc")
        repo.add("btc")  # No debe explotar ni crear duplicado
        assert len(repo.list_all()) == 1

    def test_add_multiple(self, repo: FavoritesRepository):
        """Se pueden agregar varias monedas distintas."""
        repo.add("btc")
        repo.add("eth")
        repo.add("sol")
        assert len(repo.list_all()) == 3

    def test_add_normalizes_symbol(self, repo: FavoritesRepository):
        """Los símbolos se normalizan a minúsculas."""
        repo.add("  BTC  ")
        assert repo.list_all()[0].symbol == "btc"

    def test_add_empty_raises(self, repo: FavoritesRepository):
        """Símbolo vacío levanta ValueError."""
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            repo.add("")

    def test_remove_existing(self, repo: FavoritesRepository):
        """Eliminar un favorito existente funciona."""
        repo.add("btc")
        repo.add("eth")
        repo.remove("btc")
        favs = repo.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "eth"

    def test_remove_nonexistent(self, repo: FavoritesRepository):
        """Eliminar un favorito que no existe no tira error."""
        repo.add("btc")
        repo.remove("eth")  # no está en la lista
        assert len(repo.list_all()) == 1

    def test_remove_normalizes(self, repo: FavoritesRepository):
        """Remove maneja mayúsculas/minúsculas."""
        repo.add("btc")
        repo.remove("BTC")
        assert len(repo.list_all()) == 0

    def test_remove_empty_raises(self, repo: FavoritesRepository):
        """Remove con símbolo vacío levanta ValueError."""
        repo.add("btc")
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            repo.remove("")

    def test_is_favorite(self, repo: FavoritesRepository):
        """is_favorite devuelve el estado correcto."""
        assert repo.is_favorite("btc") is False
        repo.add("btc")
        assert repo.is_favorite("btc") is True

    def test_is_favorite_case_insensitive(self, repo: FavoritesRepository):
        """is_favorite no distingue mayúsculas."""
        repo.add("btc")
        assert repo.is_favorite("BTC") is True

    def test_is_favorite_empty_returns_false(self, repo: FavoritesRepository):
        """Símbolo vacío en is_favorite devuelve False sin explotar."""
        assert repo.is_favorite("") is False

    def test_list_order(self, repo: FavoritesRepository):
        """La lista devuelve ordenada por fecha de agregado."""
        repo.add("btc")
        repo.add("eth")
        repo.add("sol")
        favs = repo.list_all()
        assert favs[0].symbol == "btc"
        assert favs[1].symbol == "eth"
        assert favs[2].symbol == "sol"

    def test_error_db_down(self):
        """Si la base de datos no existe, levanta error de conexión."""
        pytest.importorskip("psycopg2", reason="Requiere psycopg2 para test de conexión fallida")
        # create_engine + create_all() intenta conectar y falla.
        # La excepción varía según OS, pero siempre hereda de Exception.
        with pytest.raises(Exception):
            FavoritesRepository("postgresql://nadie:1234@localhost:9999/nonexistent")
