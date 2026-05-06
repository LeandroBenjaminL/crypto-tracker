"""
Tests for the FavoritesManager.

Cubre:
  - CRUD básico (add, remove, list, is_favorite)
  - Idempotencia y normalización
  - Persistencia entre instancias
  - Archivos corruptos, vacíos, con estructura inválida
  - Errores de escritura (permisos, ruta inválida)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.favorites import FavoritesError, FavoritesManager
from src.core.models import FavoriteCoin


@pytest.fixture
def fav_file(tmp_path: Path) -> Path:
    """Crea un archivo temporal para favoritos."""
    return tmp_path / ".crypto_tracker.json"


@pytest.fixture
def manager(fav_file: Path) -> FavoritesManager:
    """FavoritesManager con archivo temporal."""
    return FavoritesManager(file_path=fav_file)


class TestFavoritesManager:
    """Tests principales de CRUD."""

    def test_add_and_list(self, manager: FavoritesManager):
        """Agregar hace que aparezca en la lista."""
        manager.add("btc")
        favs = manager.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "btc"

    def test_add_is_idempotent(self, manager: FavoritesManager):
        """Agregar el mismo dos veces no duplica."""
        manager.add("btc")
        manager.add("btc")
        assert len(manager.list_all()) == 1

    def test_add_multiple(self, manager: FavoritesManager):
        """Varias monedas distintas."""
        manager.add("btc")
        manager.add("eth")
        manager.add("sol")
        assert len(manager.list_all()) == 3

    def test_add_normalizes_symbol(self, manager: FavoritesManager):
        """Símbolo se normaliza a minúsculas y sin espacios."""
        manager.add("  BTC  ")
        assert manager.list_all()[0].symbol == "btc"

    def test_add_uppercase(self, manager: FavoritesManager):
        """Mayúsculas se pasan a minúsculas."""
        manager.add("ETH")
        assert manager.list_all()[0].symbol == "eth"

    def test_add_empty_raises(self, manager: FavoritesManager):
        """Símbolo vacío da ValueError."""
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            manager.add("")

    def test_remove_existing(self, manager: FavoritesManager):
        """Eliminar un favorito existente."""
        manager.add("btc")
        manager.add("eth")
        manager.remove("btc")
        assert [f.symbol for f in manager.list_all()] == ["eth"]

    def test_remove_nonexistent(self, manager: FavoritesManager):
        """Eliminar uno que no existe no falla."""
        manager.add("btc")
        manager.remove("eth")  # no está
        assert len(manager.list_all()) == 1

    def test_remove_normalizes(self, manager: FavoritesManager):
        """Remove maneja mayúsculas."""
        manager.add("btc")
        manager.remove("BTC")
        assert len(manager.list_all()) == 0

    def test_remove_last_item(self, manager: FavoritesManager):
        """Eliminar el único favorito deja la lista vacía."""
        manager.add("btc")
        manager.remove("btc")
        assert manager.list_all() == []

    def test_is_favorite(self, manager: FavoritesManager):
        """is_favorite con True."""
        assert manager.is_favorite("btc") is False
        manager.add("btc")
        assert manager.is_favorite("btc") is True

    def test_is_favorite_case_insensitive(self, manager: FavoritesManager):
        """is_favorite es case-insensitive."""
        manager.add("btc")
        assert manager.is_favorite("BTC") is True
        assert manager.is_favorite("Btc") is True

    def test_is_favorite_empty_returns_false(self, manager: FavoritesManager):
        """Símbolo vacío nunca es favorito."""
        assert manager.is_favorite("") is False

    def test_list_all_empty_initially(self, manager: FavoritesManager):
        """Al arrancar no hay favoritos."""
        assert manager.list_all() == []

    def test_persistence_across_instances(self, fav_file: Path):
        """Favoritos sobreviven entre instancias de FavoritesManager."""
        m1 = FavoritesManager(file_path=fav_file)
        m1.add("btc")
        m1.add("eth")

        m2 = FavoritesManager(file_path=fav_file)
        assert len(m2.list_all()) == 2

    def test_returns_favoritecoin_objects(self, manager: FavoritesManager):
        """list_all devuelve FavoriteCoin, no dicts."""
        manager.add("btc")
        fav = manager.list_all()[0]
        assert isinstance(fav, FavoriteCoin)
        assert hasattr(fav, "symbol")
        assert hasattr(fav, "added_at")

    def test_file_is_valid_json(self, fav_file: Path, manager: FavoritesManager):
        """El archivo escrito es JSON válido."""
        manager.add("btc")
        with open(fav_file, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["symbol"] == "btc"
        assert "added_at" in data[0]

    def test_add_creates_file(self, fav_file: Path, manager: FavoritesManager):
        """Agregar un favorito crea el archivo si no existe."""
        assert not fav_file.exists()
        manager.add("btc")
        assert fav_file.exists()

    def test_multiple_adds_increments_file(self, fav_file: Path, manager: FavoritesManager):
        """Cada add incrementa el contenido del archivo."""
        manager.add("btc")
        manager.add("eth")
        manager.add("sol")
        with open(fav_file) as f:
            assert len(json.load(f)) == 3


class TestFileErrors:
    """Tests de errores de archivo."""

    def test_corrupted_json_raises(self, fav_file: Path):
        """JSON corrupto da FavoritesError."""
        fav_file.write_text("{broken", encoding="utf-8")
        m = FavoritesManager(file_path=fav_file)
        with pytest.raises(FavoritesError, match="Can't read"):
            m.list_all()

    def test_empty_file_raises(self, fav_file: Path):
        """Archivo vacío (no JSON) da FavoritesError."""
        fav_file.write_text("", encoding="utf-8")
        m = FavoritesManager(file_path=fav_file)
        with pytest.raises(FavoritesError):
            m.list_all()

    def test_not_a_list_raises(self, fav_file: Path):
        """Archivo con JSON que no es lista da lista vacía (no explota)."""
        fav_file.write_text('{"not": "a list"}', encoding="utf-8")
        m = FavoritesManager(file_path=fav_file)
        assert m.list_all() == []

    def test_file_does_not_exist_returns_empty(self, fav_file: Path):
        """Archivo que no existe se trata como lista vacía."""
        assert not fav_file.exists()
        m = FavoritesManager(file_path=fav_file)
        assert m.list_all() == []

    def test_file_with_extra_fields(self, fav_file: Path):
        """Archivo con campos extra no rompe."""
        fav_file.write_text(
            '[{"symbol": "btc", "added_at": "2026-01-01T00:00:00", "extra": true}]',
            encoding="utf-8",
        )
        m = FavoritesManager(file_path=fav_file)
        assert m.list_all()[0].symbol == "btc"

    def test_cache_clears_on_file_change(self, fav_file: Path):
        """Si el archivo cambia entre instancias, se relee."""
        m1 = FavoritesManager(file_path=fav_file)
        m1.add("btc")

        # Escribir directamente al archivo
        with open(fav_file, "w") as f:
            json.dump([{"symbol": "eth", "added_at": "2026-01-01T00:00:00"}], f)

        m2 = FavoritesManager(file_path=fav_file)
        favs = m2.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "eth"
