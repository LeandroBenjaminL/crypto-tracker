"""
Tests for the FavoritesManager.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.favorites import FavoritesManager, FavoritesError
from src.core.models import FavoriteCoin


@pytest.fixture
def fav_file(tmp_path: Path) -> Path:
    """Create a temporary file for favorites."""
    return tmp_path / ".crypto_tracker.json"


@pytest.fixture
def manager(fav_file: Path) -> FavoritesManager:
    """Create a FavoritesManager backed by a temp file."""
    return FavoritesManager(file_path=fav_file)


class TestFavoritesManager:
    """Tests for favorites CRUD operations."""

    def test_add_and_list(self, manager: FavoritesManager):
        """Adding a coin makes it appear in list."""
        manager.add("btc")
        favs = manager.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "btc"

    def test_add_is_idempotent(self, manager: FavoritesManager):
        """Adding the same coin twice does not create duplicates."""
        manager.add("btc")
        manager.add("btc")
        assert len(manager.list_all()) == 1

    def test_add_multiple(self, manager: FavoritesManager):
        """Can add multiple different coins."""
        manager.add("btc")
        manager.add("eth")
        manager.add("sol")
        assert len(manager.list_all()) == 3

    def test_add_normalizes_symbol(self, manager: FavoritesManager):
        """Symbols are lowercased and stripped."""
        manager.add("  BTC  ")
        assert manager.list_all()[0].symbol == "btc"

    def test_add_empty_raises(self, manager: FavoritesManager):
        """Empty symbol raises ValueError."""
        with pytest.raises(ValueError):
            manager.add("")

    def test_remove_existing(self, manager: FavoritesManager):
        """Removing an existing coin works."""
        manager.add("btc")
        manager.add("eth")
        manager.remove("btc")
        favs = manager.list_all()
        assert len(favs) == 1
        assert favs[0].symbol == "eth"

    def test_remove_nonexistent(self, manager: FavoritesManager):
        """Removing a coin not in favorites does not error."""
        manager.add("btc")
        manager.remove("eth")  # not in list
        assert len(manager.list_all()) == 1

    def test_remove_normalizes(self, manager: FavoritesManager):
        """Remove handles case differences."""
        manager.add("btc")
        manager.remove("BTC")
        assert len(manager.list_all()) == 0

    def test_is_favorite(self, manager: FavoritesManager):
        """is_favorite returns correct status."""
        assert manager.is_favorite("btc") is False
        manager.add("btc")
        assert manager.is_favorite("btc") is True

    def test_is_favorite_case_insensitive(self, manager: FavoritesManager):
        """is_favorite is case insensitive."""
        manager.add("btc")
        assert manager.is_favorite("BTC") is True
        assert manager.is_favorite("Btc") is True

    def test_is_favorite_empty(self, manager: FavoritesManager):
        """Empty string is never a favorite."""
        assert manager.is_favorite("") is False

    def test_list_all_empty(self, manager: FavoritesManager):
        """New manager has empty favorites list."""
        assert manager.list_all() == []

    def test_persistence_across_instances(self, fav_file: Path):
        """Favorites survive across different manager instances."""
        m1 = FavoritesManager(file_path=fav_file)
        m1.add("btc")
        m1.add("eth")

        m2 = FavoritesManager(file_path=fav_file)
        favs = m2.list_all()
        assert len(favs) == 2

    def test_corrupted_json_raises(self, fav_file: Path):
        """Corrupted JSON file raises FavoritesError."""
        fav_file.write_text("{corrupted json", encoding="utf-8")
        m = FavoritesManager(file_path=fav_file)
        with pytest.raises(FavoritesError):
            m.list_all()

    def test_returns_favoritecoin_objects(self, manager: FavoritesManager):
        """list_all returns FavoriteCoin instances."""
        manager.add("btc")
        favs = manager.list_all()
        assert isinstance(favs[0], FavoriteCoin)
        assert hasattr(favs[0], "symbol")
        assert hasattr(favs[0], "added_at")

    def test_file_is_valid_json(self, fav_file: Path, manager: FavoritesManager):
        """Written file is valid JSON."""
        manager.add("btc")
        manager.add("eth")

        with open(fav_file, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["symbol"] == "btc"
        assert "added_at" in data[0]
