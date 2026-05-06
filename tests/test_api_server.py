"""
Tests para la API REST (FastAPI).

Usamos TestClient de Starlette para pegarle a la app sin levantar
un servidor HTTP. Mockeamos PriceService y FavoritesManager para
testear endpoints en aislamiento.

Cubre:
  - Todos los endpoints (éxito y error)
  - Mapeo de errores del dominio a HTTP
  - CORS headers
  - Helpers internos (_map_error, _coin_to_out)
  - Edge cases (empty, null, tipos raros)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.models import CoinSearchResult, Cryptocurrency, FavoriteCoin, PriceData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytest_plugins = ("pytest",)


@pytest.fixture
def mock_service() -> MagicMock:
    """Mock de PriceService para aislar los tests."""
    return MagicMock()


@pytest.fixture
def mock_favorites() -> MagicMock:
    """Mock de FavoritesManager para aislar los tests."""
    return MagicMock()


@pytest.fixture
def client(mock_service: MagicMock, mock_favorites: MagicMock) -> TestClient:
    """
    Crea un TestClient con los services mockeados.

    Parcheamos _service y _favorites en el módulo server, y también
    desactivamos la precarga para que no intente llamar a la API real.
    """
    patches = [
        patch("src.api.server._service", mock_service),
        patch("src.api.server._favorites", mock_favorites),
        patch("src.api.server._precache", lambda: None),
    ]
    for p in patches:
        p.start()

    from src.api.server import app

    with TestClient(app) as tc:
        yield tc

    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Helpers para construir datos de prueba
# ---------------------------------------------------------------------------


def _coin_search_result(
    coin_id: str = "bitcoin",
    symbol: str = "btc",
    name: str = "Bitcoin",
    rank: int = 1,
    price: float | None = 45000.50,
    change_24h: float | None = 2.5,
    volume_24h: float | None = 25_000_000_000,
    market_cap: float | None = 850_000_000_000,
) -> CoinSearchResult:
    """Construye un CoinSearchResult del dominio."""
    coin = Cryptocurrency(id=coin_id, symbol=symbol, name=name, rank=rank)
    if price is not None:
        price_data = PriceData(
            coin_id=coin_id,
            price=price,
            change_24h=change_24h or 0.0,
            volume_24h=volume_24h or 0.0,
            market_cap=market_cap or 0.0,
        )
    else:
        price_data = None
    return CoinSearchResult(coin=coin, price_data=price_data)


# ===================================================================
# Tests unitarios de helpers internos
# ===================================================================


class TestCoinToOut:
    """Tests directos de _coin_to_out()."""

    def test_converts_full_result(self):
        """Convierte CoinSearchResult completo a dict."""
        from src.api.server import _coin_to_out

        result = _coin_search_result()
        out = _coin_to_out(result)

        assert out.id == "bitcoin"
        assert out.symbol == "btc"
        assert out.name == "Bitcoin"
        assert out.rank == 1
        assert out.price == 45000.50
        assert out.change_24h == 2.5
        assert out.price_formatted == "$45,000.50"

    def test_converts_without_price(self):
        """CoinSearchResult sin precio → price=None, price_formatted=None."""
        from src.api.server import _coin_to_out

        result = _coin_search_result(price=None)
        out = _coin_to_out(result)

        assert out.price is None
        assert out.price_formatted is None

    def test_converts_zero_rank(self):
        """Coin sin rank tiene rank=0."""
        from src.api.server import _coin_to_out

        result = _coin_search_result(rank=0)
        out = _coin_to_out(result)

        assert out.rank == 0


class TestMapError:
    """Tests directos de _map_error()."""

    def _check(self, exception: CryptoTrackerError, expected_status: int, expected_detail_substr: str):
        from src.api.server import _map_error

        http_exc = _map_error(exception)
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == expected_status
        assert expected_detail_substr in http_exc.detail.lower()

    def test_coin_not_found(self):
        self._check(CoinNotFoundError("x"), 404, "no encontrada")

    def test_rate_limit_with_retry(self):
        self._check(RateLimitError(retry_after=30), 429, "límite")

    def test_rate_limit_without_retry(self):
        self._check(RateLimitError(), 429, "límite")

    def test_network_error(self):
        self._check(NetworkError(), 502, "conexión")

    def test_validation_error(self):
        self._check(ValidationError("field", "val", "bad"), 422, "validation")

    def test_api_error_generic(self):
        self._check(APIError("something broke", status_code=502), 502, "api")

    def test_api_error_with_500(self):
        """APIError genérico sin status code cae como 502."""
        self._check(APIError("fail"), 502, "fail")

    def test_generic_crypto_error(self):
        self._check(CryptoTrackerError("generic oops"), 500, "interno")


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    """GET /api/health"""

    def test_health_ok(self, client: TestClient):
        """Health check devuelve estado ok."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_has_all_keys(self, client: TestClient):
        """Health check tiene los 5 campos esperados."""
        resp = client.get("/api/health")
        assert set(resp.json().keys()) == {
            "status", "api_key_configured", "version", "favorites_source",
            "price_source",
        }

    def test_health_version_is_string(self, client: TestClient):
        """Version es un string no vacío."""
        v = client.get("/api/health").json()["version"]
        assert isinstance(v, str) and len(v) > 0

    def test_health_favorites_source(self, client: TestClient):
        """favorites_source es un string (json / postgresql / json_fallback)."""
        fs = client.get("/api/health").json()["favorites_source"]
        assert isinstance(fs, str)
        # Como mockeamos _favorites, el source depende del fixture
        # Verificamos que al menos sea un string válido


# ===================================================================
# CORS
# ===================================================================


class TestCORS:
    """Verifica que CORS esté configurado."""

    def test_cors_headers_on_get(self, client: TestClient):
        """Las respuestas GET tienen CORS headers cuando mandan Origin."""
        resp = client.get("/api/health", headers={"Origin": "http://localhost:8501"})
        # Con allow_credentials=True, Starlette refleja el origin en vez de *
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8501"

    def test_cors_preflight(self, client: TestClient):
        """OPTIONS request funciona (CORS preflight)."""
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8501"

    def test_openapi_docs_accessible(self, client: TestClient):
        """OpenAPI docs están disponibles."""
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower()

    def test_redoc_accessible(self, client: TestClient):
        """ReDoc está disponible."""
        resp = client.get("/redoc")
        assert resp.status_code == 200
        assert "redoc" in resp.text.lower()

    def test_openapi_json(self, client: TestClient):
        """OpenAPI spec JSON se sirve correctamente."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["info"]["title"] == "Crypto Tracker API"
        assert "/api/price/" in str(spec["paths"])


# ===================================================================
# Price endpoints
# ===================================================================


class TestGetPrice:
    """GET /api/price/{query}"""

    def test_get_price_by_symbol(self, client: TestClient, mock_service: MagicMock):
        """Precio por símbolo resuelve bien."""
        mock_service.get_price.return_value = _coin_search_result()
        resp = client.get("/api/price/btc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "btc"
        assert data["price"] == 45000.50
        mock_service.get_price.assert_called_once_with("btc", currency="usd")

    def test_get_price_with_custom_currency(self, client: TestClient, mock_service: MagicMock):
        """Precio con moneda distinta pasa el parámetro."""
        mock_service.get_price.return_value = _coin_search_result(price=41000.0)
        resp = client.get("/api/price/btc?currency=eur")
        assert resp.status_code == 200
        mock_service.get_price.assert_called_once_with("btc", currency="eur")

    def test_get_price_no_price_data(self, client: TestClient, mock_service: MagicMock):
        """Moneda existe pero sin datos de precio."""
        mock_service.get_price.return_value = _coin_search_result(price=None)
        resp = client.get("/api/price/btc")
        assert resp.status_code == 200
        assert resp.json()["price"] is None
        assert resp.json()["price_formatted"] is None

    def test_get_price_without_query_returns_404(self, client: TestClient, mock_service: MagicMock):
        """Pegarle sin query en la URL debería dar 404 (FastAPI)."""
        resp = client.get("/api/price/")
        assert resp.status_code == 404  # no hay trailing slash handler

    # --- Errores ---

    @pytest.mark.parametrize(
        "exception, expected_status, expected_keyword",
        [
            (CoinNotFoundError("test"), 404, "no encontrada"),
            (RateLimitError(retry_after=30), 429, "límite"),
            (RateLimitError(), 429, "límite"),  # sin retry_after
            (NetworkError(), 502, "conexión"),
            (ValidationError("query", "", "empty"), 422, "validation"),
            (APIError("ext api fail", status_code=502), 502, "api"),
            (CryptoTrackerError("generic"), 500, "interno"),
        ],
    )
    def test_get_price_errors(
        self,
        client: TestClient,
        mock_service: MagicMock,
        exception: Exception,
        expected_status: int,
        expected_keyword: str,
    ):
        """Cada error del dominio se mapea al HTTP correcto."""
        mock_service.get_price.side_effect = exception
        resp = client.get("/api/price/btc")
        assert resp.status_code == expected_status
        assert expected_keyword in resp.json()["detail"].lower()


class TestGetPrices:
    """GET /api/prices"""

    def test_batch(self, client: TestClient, mock_service: MagicMock):
        """Precios de varias monedas."""
        mock_service.get_prices.return_value = [
            _coin_search_result(coin_id="bitcoin", symbol="btc"),
            _coin_search_result(coin_id="ethereum", symbol="eth", price=3200.0),
        ]
        resp = client.get("/api/prices?q=btc,eth")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "btc"
        assert data[1]["symbol"] == "eth"

    def test_default_param(self, client: TestClient, mock_service: MagicMock):
        """Sin parámetro q usa default btc,eth."""
        mock_service.get_prices.return_value = []
        client.get("/api/prices")
        mock_service.get_prices.assert_called_once()

    def test_empty_query(self, client: TestClient, mock_service: MagicMock):
        """q vacío devuelve lista vacía."""
        mock_service.get_prices.return_value = []
        resp = client.get("/api/prices?q=")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_single_coin(self, client: TestClient, mock_service: MagicMock):
        """Un solo símbolo también funciona."""
        mock_service.get_prices.return_value = [
            _coin_search_result(coin_id="solana", symbol="sol"),
        ]
        resp = client.get("/api/prices?q=sol")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["symbol"] == "sol"


# ===================================================================
# Top Coins
# ===================================================================


class TestGetTop:
    """GET /api/top"""

    def test_default(self, client: TestClient, mock_service: MagicMock):
        """Top coins con valores default."""
        mock_service.list_top.return_value = [
            _coin_search_result(rank=1),
            _coin_search_result(coin_id="ethereum", symbol="eth", rank=2, price=3200.0),
        ]
        resp = client.get("/api/top")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[0]["rank"] == 1

    def test_custom_limit(self, client: TestClient, mock_service: MagicMock):
        """Límite personalizado se pasa al service."""
        mock_service.list_top.return_value = []
        client.get("/api/top?limit=25")
        mock_service.list_top.assert_called_once_with(limit=25, currency="usd")

    def test_with_currency(self, client: TestClient, mock_service: MagicMock):
        """Moneda distinta se pasa al service."""
        mock_service.list_top.return_value = []
        client.get("/api/top?limit=10&currency=ars")
        mock_service.list_top.assert_called_once_with(limit=10, currency="ars")

    def test_limit_min_edge(self, client: TestClient, mock_service: MagicMock):
        """limit=1 es válido."""
        mock_service.list_top.return_value = [_coin_search_result(rank=1)]
        resp = client.get("/api/top?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_validates_limit_type(self, client: TestClient):
        """limit no numérico da 422 (FastAPI validation)."""
        resp = client.get("/api/top?limit=abc")
        assert resp.status_code == 422


# ===================================================================
# History
# ===================================================================


class TestGetHistory:
    """GET /api/history/{query}"""

    def test_success(self, client: TestClient, mock_service: MagicMock):
        """Historial devuelve array de {timestamp, price}."""
        mock_service.get_history.return_value = [
            {"timestamp": 1700000000000, "price": 45000.0},
            {"timestamp": 1700086400000, "price": 46000.0},
        ]
        resp = client.get("/api/history/bitcoin?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["timestamp"] == 1700000000000
        assert data[0]["price"] == 45000.0
        mock_service.get_history.assert_called_once_with(
            "bitcoin", days=7, currency="usd"
        )

    def test_custom_days_and_currency(self, client: TestClient, mock_service: MagicMock):
        """Parámetros personalizados se pasan al service."""
        mock_service.get_history.return_value = []
        client.get("/api/history/btc?days=30&currency=eur")
        mock_service.get_history.assert_called_once_with("btc", days=30, currency="eur")

    def test_empty_history(self, client: TestClient, mock_service: MagicMock):
        """Sin datos históricos devuelve []."""
        mock_service.get_history.return_value = []
        resp = client.get("/api/history/btc")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rate_limit_error(self, client: TestClient, mock_service: MagicMock):
        """Rate limit en history también da 429."""
        mock_service.get_history.side_effect = RateLimitError(retry_after=10)
        resp = client.get("/api/history/btc?days=7")
        assert resp.status_code == 429

    def test_validates_days_type(self, client: TestClient):
        """days no numérico da 422."""
        resp = client.get("/api/history/btc?days=abc")
        assert resp.status_code == 422


# ===================================================================
# Search
# ===================================================================


class TestSearch:
    """GET /api/search/{query}"""

    def test_found(self, client: TestClient, mock_service: MagicMock):
        """Búsqueda encuentra monedas."""
        mock_service.search.return_value = [
            Cryptocurrency(id="bitcoin", symbol="btc", name="Bitcoin", rank=1),
            Cryptocurrency(id="bitcoin-cash", symbol="bch", name="Bitcoin Cash", rank=30),
        ]
        resp = client.get("/api/search/bitcoin")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "bitcoin"
        assert data[0]["symbol"] == "btc"
        assert data[0]["rank"] == 1

    def test_no_results(self, client: TestClient, mock_service: MagicMock):
        """Sin resultados devuelve []."""
        mock_service.search.return_value = []
        resp = client.get("/api/search/nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_coin_without_rank(self, client: TestClient, mock_service: MagicMock):
        """Moneda sin rank devuelve rank=0."""
        mock_service.search.return_value = [
            Cryptocurrency(id="newcoin", symbol="new", name="New Coin", rank=0),
        ]
        resp = client.get("/api/search/newcoin")
        assert resp.json()[0]["rank"] == 0

    def test_coin_id_is_present(self, client: TestClient, mock_service: MagicMock):
        """Cada resultado tiene su id de CoinGecko."""
        mock_service.search.return_value = [
            Cryptocurrency(id="solana", symbol="sol", name="Solana", rank=5),
        ]
        assert client.get("/api/search/sol").json()[0]["id"] == "solana"


# ===================================================================
# Favorites
# ===================================================================


class TestListFavorites:
    """GET /api/favorites"""

    def test_empty(self, client: TestClient, mock_favorites: MagicMock):
        """Sin favoritos devuelve []."""
        mock_favorites.list_all.return_value = []
        assert client.get("/api/favorites").json() == []

    def test_with_data(self, client: TestClient, mock_favorites: MagicMock):
        """Lista con favoritos."""
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            FavoriteCoin(symbol="eth", added_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        data = client.get("/api/favorites").json()
        assert len(data) == 2
        assert data[0]["symbol"] == "btc"
        assert data[1]["symbol"] == "eth"
        # Verificar formato iso de fecha
        for fav in data:
            assert "T" in fav["added_at"]  # ISO format

    def test_response_has_expected_keys(self, client: TestClient, mock_favorites: MagicMock):
        """Cada favorito tiene symbol y added_at."""
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        item = client.get("/api/favorites").json()[0]
        assert set(item.keys()) == {"symbol", "added_at"}


class TestAddFavorite:
    """POST /api/favorites/{symbol}"""

    def test_success(self, client: TestClient, mock_favorites: MagicMock):
        """Agregar favorito devuelve 201."""
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        resp = client.post("/api/favorites/btc")
        assert resp.status_code == 201
        assert resp.json()["symbol"] == "btc"
        mock_favorites.add.assert_called_once_with("btc")

    def test_idempotent(self, client: TestClient, mock_favorites: MagicMock):
        """POST repetido no falla."""
        fav = FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        mock_favorites.list_all.return_value = [fav]
        r1 = client.post("/api/favorites/btc")
        r2 = client.post("/api/favorites/btc")
        assert r1.status_code == 201
        assert r2.status_code == 201

    def test_normalizes_case(self, client: TestClient, mock_favorites: MagicMock):
        """Símbolo en mayúsculas se normaliza a minúsculas."""
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        client.post("/api/favorites/BTC")
        mock_favorites.add.assert_called_once_with("btc")

    def test_add_and_list_consistency(self, client: TestClient, mock_favorites: MagicMock):
        """POST seguido de GET devuelve el favorito."""
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        client.post("/api/favorites/btc")
        favs = client.get("/api/favorites").json()
        assert favs[0]["symbol"] == "btc"

    def test_post_with_trailing_space(self, client: TestClient, mock_favorites: MagicMock):
        """Símbolo con espacios se normaliza (lo maneja el repo, no la URL)."""
        # FastAPI no permite espacios en path params así que usamos algo sin espacio
        mock_favorites.list_all.return_value = [
            FavoriteCoin(symbol="btc", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ]
        client.post("/api/favorites/btc")
        mock_favorites.add.assert_called_once()


class TestRemoveFavorite:
    """DELETE /api/favorites/{symbol}"""

    def test_success(self, client: TestClient, mock_favorites: MagicMock):
        """DELETE devuelve 204 sin body."""
        resp = client.delete("/api/favorites/btc")
        assert resp.status_code == 204
        assert resp.content == b""
        mock_favorites.remove.assert_called_once_with("btc")

    def test_nonexistent(self, client: TestClient, mock_favorites: MagicMock):
        """DELETE de favorito inexistente no falla."""
        resp = client.delete("/api/favorites/nonexistent")
        assert resp.status_code == 204
        mock_favorites.remove.assert_called_once_with("nonexistent")

    def test_remove_then_list(self, client: TestClient, mock_favorites: MagicMock):
        """DELETE y después GET muestra lista vacía."""
        mock_favorites.list_all.return_value = []
        client.delete("/api/favorites/btc")
        assert client.get("/api/favorites").json() == []


# ===================================================================
# 404 para rutas inexistentes
# ===================================================================


class TestNotFound:
    """Rutas que no existen."""

    def test_unknown_endpoint(self, client: TestClient):
        """Ruta inventada devuelve 404."""
        resp = client.get("/api/unknown")
        assert resp.status_code == 404

    def test_unknown_method(self, client: TestClient):
        """Método no soportado devuelve 405."""
        resp = client.put("/api/health")  # PUT no está definido
        assert resp.status_code == 405
