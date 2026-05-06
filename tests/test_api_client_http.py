"""
Tests para el cliente HTTP de la API (src/api/client.py).

Este módulo lo usa Streamlit para consumir nuestra propia API REST.
Mockeamos requests.get/post/delete para no necesitar un server vivo.

Cubre:
  - Todos los endpoints (price, prices, top, history, search, favorites, health)
  - Traducción de errores HTTP a excepciones del dominio
  - Errores de red (connection, timeout)
  - Edge cases (empty, 204, JSON malformado)
  - Helpers internos (_safe_detail, _handle_response)
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import requests

from src.api import client as api
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(
    json_data: object,
    status_code: int = 200,
) -> requests.Response:
    """Construye un requests.Response simulado sin tocar la red."""
    resp = requests.Response()
    resp._content = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
    resp.status_code = status_code
    resp.encoding = "utf-8"
    resp.headers["Content-Type"] = "application/json"
    # Forzar .ok según status_code
    if 200 <= status_code < 300:
        resp.raw  # no-op, solo para que el objeto sea válido
    return resp


# ===================================================================
# Tests de helpers internos
# ===================================================================


class TestSafeDetail:
    """Tests directos de _safe_detail()."""

    @patch("src.api.client.requests.get")
    def test_extracts_detail_from_json(self, mock_get):
        """_safe_detail extrae el campo detail del JSON."""
        resp = _mock_response({"detail": "Not found"}, status_code=404)
        from src.api.client import _safe_detail
        assert _safe_detail(resp) == "Not found"

    @patch("src.api.client.requests.get")
    def test_fallback_to_status_code(self, mock_get):
        """Sin JSON válido, devuelve el status code como string."""
        resp = _mock_response("not json", status_code=500)
        # Forzar que el response content no sea JSON válido
        resp._content = b"not json at all"
        from src.api.client import _safe_detail
        assert _safe_detail(resp) == "500"


class TestHandleResponse:
    """Tests directos de _handle_response()."""

    def test_ok_response_returns_json(self):
        """200 devuelve el JSON parseado."""
        resp = _mock_response({"price": 45000})
        assert api._handle_response(resp) == {"price": 45000}

    def test_ok_no_content_returns_none(self):
        """204 sin contenido devuelve None."""
        resp = _mock_response(None, status_code=204)
        resp._content = b""
        assert api._handle_response(resp) is None

    def test_404_raises(self):
        resp = _mock_response({"detail": "not found"}, status_code=404)
        with pytest.raises(CoinNotFoundError):
            api._handle_response(resp)

    def test_429_raises(self):
        resp = _mock_response({"detail": "rate limit"}, status_code=429)
        with pytest.raises(RateLimitError):
            api._handle_response(resp)

    def test_502_raises(self):
        resp = _mock_response({"detail": "bad gateway"}, status_code=502)
        with pytest.raises(APIError):
            api._handle_response(resp)

    def test_422_raises(self):
        resp = _mock_response({"detail": "validation error"}, status_code=422)
        with pytest.raises(ValidationError):
            api._handle_response(resp)

    def test_unknown_error_raises_api_error(self):
        resp = _mock_response({"detail": "server error"}, status_code=500)
        with pytest.raises(APIError):
            api._handle_response(resp)


# ===================================================================
# Price endpoints
# ===================================================================


class TestGetPrice:
    """api.get_price()"""

    @patch("src.api.client.requests.get")
    def test_success(self, mock_get):
        """Precio de una moneda."""
        mock_get.return_value = _mock_response({
            "id": "bitcoin", "symbol": "btc", "price": 45000.50, "change_24h": 2.5,
            "price_formatted": "$45,000.50",
        })
        result = api.get_price("btc")
        assert result["symbol"] == "btc"
        assert result["price"] == 45000.50
        mock_get.assert_called_once_with(
            "http://127.0.0.1:8000/api/price/btc",
            params={"currency": "usd"},
        )

    @patch("src.api.client.requests.get")
    def test_custom_currency(self, mock_get):
        """Precio con moneda personalizada."""
        mock_get.return_value = _mock_response({"price": 41000.0})
        api.get_price("btc", currency="eur")
        assert mock_get.call_args[1]["params"]["currency"] == "eur"

    @patch("src.api.client.requests.get")
    def test_no_price_data(self, mock_get):
        """Moneda sin precio."""
        mock_get.return_value = _mock_response({
            "symbol": "btc", "price": None, "price_formatted": None,
        })
        result = api.get_price("btc")
        assert result["price"] is None

    @patch("src.api.client.requests.get")
    def test_network_connection_error(self, mock_get):
        """ConnectionError se traduce a NetworkError."""
        mock_get.side_effect = requests.ConnectionError("refused")
        with pytest.raises(NetworkError):
            api.get_price("btc")

    @patch("src.api.client.requests.get")
    def test_network_timeout(self, mock_get):
        """Timeout también se traduce a NetworkError."""
        mock_get.side_effect = requests.Timeout("timed out")
        with pytest.raises(NetworkError):
            api.get_price("btc")

    @patch("src.api.client.requests.get")
    def test_404(self, mock_get):
        mock_get.return_value = _mock_response({"detail": "no"}, status_code=404)
        with pytest.raises(CoinNotFoundError):
            api.get_price("fake")

    @patch("src.api.client.requests.get")
    def test_429(self, mock_get):
        mock_get.return_value = _mock_response({"detail": "slow"}, status_code=429)
        with pytest.raises(RateLimitError):
            api.get_price("btc")

    @patch("src.api.client.requests.get")
    def test_502(self, mock_get):
        mock_get.return_value = _mock_response({"detail": "bad"}, status_code=502)
        with pytest.raises(APIError):
            api.get_price("btc")


class TestGetPrices:
    """api.get_prices()"""

    @patch("src.api.client.requests.get")
    def test_multiple(self, mock_get):
        """Varias monedas."""
        mock_get.return_value = _mock_response([
            {"symbol": "btc", "price": 45000.50},
            {"symbol": "eth", "price": 3200.0},
        ])
        results = api.get_prices(["btc", "eth"])
        assert len(results) == 2

    @patch("src.api.client.requests.get")
    def test_empty_list(self, mock_get):
        """Lista vacía."""
        mock_get.return_value = _mock_response([])
        assert api.get_prices([]) == []

    @patch("src.api.client.requests.get")
    def test_single_item(self, mock_get):
        """Un solo elemento."""
        mock_get.return_value = _mock_response([{"symbol": "sol", "price": 150.0}])
        assert len(api.get_prices(["sol"])) == 1


class TestGetTop:
    """api.get_top()"""

    @patch("src.api.client.requests.get")
    def test_default(self, mock_get):
        """Top coins default."""
        mock_get.return_value = _mock_response([
            {"rank": 1, "symbol": "btc"},
            {"rank": 2, "symbol": "eth"},
        ])
        results = api.get_top()
        assert len(results) == 2
        assert results[0]["rank"] == 1

    @patch("src.api.client.requests.get")
    def test_custom_limit(self, mock_get):
        """Límite personalizado."""
        mock_get.return_value = _mock_response([])
        api.get_top(limit=25)
        assert mock_get.call_args[1]["params"]["limit"] == 25

    @patch("src.api.client.requests.get")
    def test_with_currency(self, mock_get):
        """Moneda personalizada."""
        mock_get.return_value = _mock_response([])
        api.get_top(currency="eur")
        assert mock_get.call_args[1]["params"]["currency"] == "eur"


class TestGetHistory:
    """api.get_history()"""

    @patch("src.api.client.requests.get")
    def test_success(self, mock_get):
        """Historial."""
        mock_get.return_value = _mock_response([
            {"timestamp": 1700000000000, "price": 45000.0},
        ])
        results = api.get_history("bitcoin", days=7)
        assert len(results) == 1
        assert results[0]["price"] == 45000.0

    @patch("src.api.client.requests.get")
    def test_empty(self, mock_get):
        """Historial vacío."""
        mock_get.return_value = _mock_response([])
        assert api.get_history("bitcoin") == []

    @patch("src.api.client.requests.get")
    def test_custom_days_and_currency(self, mock_get):
        """Parámetros personalizados."""
        mock_get.return_value = _mock_response([])
        api.get_history("btc", days=30, currency="eur")
        params = mock_get.call_args[1]["params"]
        assert params["days"] == 30
        assert params["currency"] == "eur"


# ===================================================================
# Search
# ===================================================================


class TestSearch:
    """api.search()"""

    @patch("src.api.client.requests.get")
    def test_found(self, mock_get):
        """Encuentra monedas."""
        mock_get.return_value = _mock_response([
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "rank": 1},
        ])
        assert len(api.search("bitcoin")) == 1

    @patch("src.api.client.requests.get")
    def test_no_results(self, mock_get):
        """Sin resultados."""
        mock_get.return_value = _mock_response([])
        assert api.search("nonexistent") == []

    @patch("src.api.client.requests.get")
    def test_network_error(self, mock_get):
        """Error de red en search."""
        mock_get.side_effect = requests.ConnectionError()
        with pytest.raises(NetworkError):
            api.search("bitcoin")


# ===================================================================
# Favorites
# ===================================================================


class TestListFavorites:
    """api.list_favorites()"""

    @patch("src.api.client.requests.get")
    def test_empty(self, mock_get):
        mock_get.return_value = _mock_response([])
        assert api.list_favorites() == []

    @patch("src.api.client.requests.get")
    def test_with_data(self, mock_get):
        mock_get.return_value = _mock_response([
            {"symbol": "btc", "added_at": "2026-01-01T00:00:00"},
        ])
        assert api.list_favorites()[0]["symbol"] == "btc"

    @patch("src.api.client.requests.get")
    def test_network_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        with pytest.raises(NetworkError):
            api.list_favorites()


class TestAddFavorite:
    """api.add_favorite()"""

    @patch("src.api.client.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(
            {"symbol": "btc", "added_at": "2026-01-01T00:00:00"},
            status_code=201,
        )
        result = api.add_favorite("btc")
        assert result["symbol"] == "btc"
        mock_post.assert_called_once_with("http://127.0.0.1:8000/api/favorites/btc")

    @patch("src.api.client.requests.post")
    def test_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError()
        with pytest.raises(NetworkError):
            api.add_favorite("btc")


class TestRemoveFavorite:
    """api.remove_favorite()"""

    @patch("src.api.client.requests.delete")
    def test_success(self, mock_delete):
        """204 sin contenido devuelve None."""
        mock_delete.return_value = _mock_response(None, status_code=204)
        mock_delete.return_value._content = b""
        assert api.remove_favorite("btc") is None

    @patch("src.api.client.requests.delete")
    def test_not_found(self, mock_delete):
        """404 se traduce a CoinNotFoundError."""
        mock_delete.return_value = _mock_response(
            {"detail": "Not found"}, status_code=404,
        )
        with pytest.raises(CoinNotFoundError):
            api.remove_favorite("nonexistent")

    @patch("src.api.client.requests.delete")
    def test_network_error(self, mock_delete):
        mock_delete.side_effect = requests.ConnectionError()
        with pytest.raises(NetworkError):
            api.remove_favorite("btc")


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    """api.health()"""

    @patch("src.api.client.requests.get")
    def test_ok(self, mock_get):
        """API responde."""
        mock_get.return_value = _mock_response({
            "status": "ok", "version": "0.2.0",
            "api_key_configured": False, "favorites_source": "json",
        })
        result = api.health()
        assert result["status"] == "ok"
        assert result["version"] == "0.2.0"

    @patch("src.api.client.requests.get")
    def test_down(self, mock_get):
        """API no responde devuelve status down."""
        mock_get.side_effect = requests.ConnectionError()
        result = api.health()
        assert result["status"] == "down"


# ===================================================================
# API_BASE_URL custom
# ===================================================================


class TestApiBaseUrl:
    """Verifica que API_BASE_URL se pueda configurar vía env var."""

    @patch.dict(os.environ, {"API_BASE_URL": "http://custom:8888"}, clear=True)
    def test_custom_base_url(self):
        """API_BASE_URL cambia la base."""
        import importlib

        import src.api.client as client
        importlib.reload(client)
        assert client._API_BASE == "http://custom:8888"
        # Restauramos el valor original
        importlib.reload(api)
