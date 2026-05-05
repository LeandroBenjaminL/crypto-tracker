"""
API REST con FastAPI para crypto-tracker.

Es otra delivery mechanism más, como el CLI y Streamlit. Misma lógica de negocio,
mismos services, pero expuestos como endpoints HTTP con OpenAPI docs.

Uso:
    uvicorn src.api.server:app --reload
    # después: http://localhost:8000/docs
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.adapters.api_client import CoinGeckoClient
from src.config import settings
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.favorites import FavoritesManager
from src.core.models import (
    CoinSearchResult,
    Cryptocurrency,
    FavoriteCoin,
    PriceData,
)
from src.core.price_service import PriceService

# ---------------------------------------------------------------------------
# Schemas de respuesta — Pydantic, no dataclasses, porque FastAPI los serializa solo
# ---------------------------------------------------------------------------


class CoinOut(BaseModel):
    """Lo que devolvemos cuando preguntan por una moneda."""

    id: str
    symbol: str
    name: str
    rank: int
    price: float | None = None
    change_24h: float | None = None
    volume_24h: float | None = None
    market_cap: float | None = None
    price_formatted: str | None = None


class HistoryPoint(BaseModel):
    """Un punto del gráfico histórico."""

    timestamp: float  # epoch ms
    price: float


class FavoriteOut(BaseModel):
    """Favorito como lo ve el usuario."""

    symbol: str
    added_at: str  # isoformat


class HealthOut(BaseModel):
    """Estado del servicio."""

    status: str
    api_key_configured: bool
    version: str


class ErrorOut(BaseModel):
    """Error con mensaje amigable."""

    detail: str
    code: str | None = None


# ---------------------------------------------------------------------------
# Services singleton
# ---------------------------------------------------------------------------

_client = CoinGeckoClient(api_key=settings.coingecko_api_key, cache_ttl=30.0)
_service = PriceService(api_client=_client)
_favorites = FavoritesManager()
_VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coin_to_out(result: CoinSearchResult) -> CoinOut:
    """Convierte un CoinSearchResult del dominio a CoinOut para la API."""
    coin = result.coin
    pd = result.price_data
    return CoinOut(
        id=coin.id,
        symbol=coin.symbol,
        name=coin.name,
        rank=coin.rank,
        price=pd.price if pd else None,
        change_24h=pd.change_24h if pd else None,
        volume_24h=pd.volume_24h if pd else None,
        market_cap=pd.market_cap if pd else None,
        price_formatted=pd.price_formatted if pd else None,
    )


def _map_error(exc: CryptoTrackerError) -> HTTPException:
    """Traduce excepciones del dominio a HTTP errors con mensajes piolas."""
    mapping: dict[type, tuple[int, str]] = {
        CoinNotFoundError: (404, "Moneda no encontrada"),
        RateLimitError: (429, "Límite de API alcanzado. Esperá un toque."),
        NetworkError: (502, "Error de conexión con la API externa."),
        ValidationError: (422, str(exc)),
        APIError: (502, f"Error de API externa: {exc}"),
    }

    for exc_type, (status, msg) in mapping.items():
        if isinstance(exc, exc_type):
            return HTTPException(status_code=status, detail=msg)

    return HTTPException(status_code=500, detail=f"Error interno: {exc}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Crypto Tracker API",
    description="""
    API REST para追踪ar precios de criptomonedas.
    Se basa en CoinGecko y expone los mismos datos que el CLI y el dashboard.
    """,
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — abierto para desarrollo, en prod se restringe
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handler global — atrapa cualquier CryptoTrackerError
# ---------------------------------------------------------------------------


@app.exception_handler(CryptoTrackerError)
async def cryptotracker_exception_handler(
    request: Any, exc: CryptoTrackerError
) -> Any:
    """Cualquier error del dominio se traduce a HTTP con mensaje amigable."""
    raise _map_error(exc)


# ---------------------------------------------------------------------------
# Endpoints de precio
# ---------------------------------------------------------------------------


@app.get(
    "/api/price/{query}",
    response_model=CoinOut,
    summary="Precio de una moneda",
    description="Buscá por ID (bitcoin), símbolo (btc) o nombre (Bitcoin).",
)
def get_price(query: str, currency: str = "usd") -> CoinOut:
    """Precio actual de una criptomoneda."""
    result = _service.get_price(query, currency=currency)
    return _coin_to_out(result)


@app.get(
    "/api/prices",
    response_model=list[CoinOut],
    summary="Precios de varias monedas",
    description="Pasá los símbolos separados por coma: ?q=btc,eth,sol",
)
def get_prices(q: str = "btc,eth", currency: str = "usd") -> list[CoinOut]:
    """Precios de varias monedas de una sola vez."""
    queries = [s.strip() for s in q.split(",") if s.strip()]
    results = _service.get_prices(queries, currency=currency)
    return [_coin_to_out(r) for r in results]


@app.get(
    "/api/top",
    response_model=list[CoinOut],
    summary="Top monedas por market cap",
)
def get_top(limit: int = 10, currency: str = "usd") -> list[CoinOut]:
    """Las N monedas con mayor capitalización de mercado."""
    results = _service.list_top(limit=limit, currency=currency)
    return [_coin_to_out(r) for r in results]


@app.get(
    "/api/history/{query}",
    response_model=list[HistoryPoint],
    summary="Precio histórico",
    description="Datos para graficar. Params: days (1,7,30,90,365,'max').",
)
def get_history(
    query: str, days: int = 7, currency: str = "usd"
) -> list[dict[str, float]]:
    """Historial de precios para una moneda."""
    return _service.get_history(query, days=days, currency=currency)


# ---------------------------------------------------------------------------
# Endpoints de búsqueda
# ---------------------------------------------------------------------------


@app.get(
    "/api/search/{query}",
    response_model=list[CoinOut],
    summary="Buscar monedas",
)
def search_coins(query: str) -> list[CoinOut]:
    """Buscá monedas por nombre o símbolo."""
    coins = _service.search(query)
    return [
        CoinOut(id=c.id, symbol=c.symbol, name=c.name, rank=c.rank)
        for c in coins
    ]


# ---------------------------------------------------------------------------
# Endpoints de favoritos
# ---------------------------------------------------------------------------


@app.get(
    "/api/favorites",
    response_model=list[FavoriteOut],
    summary="Listar favoritos",
)
def list_favorites() -> list[FavoriteOut]:
    """Todas las monedas guardadas como favoritas."""
    favs = _favorites.list_all()
    return [
        FavoriteOut(
            symbol=f.symbol,
            added_at=f.added_at.isoformat(),
        )
        for f in favs
    ]


@app.post(
    "/api/favorites/{symbol}",
    response_model=FavoriteOut,
    summary="Agregar favorito",
    status_code=201,
)
def add_favorite(symbol: str) -> FavoriteOut:
    """Guarda una moneda como favorita (idempotente)."""
    _favorites.add(symbol)
    favs = _favorites.list_all()
    fav = next(f for f in favs if f.symbol == symbol.lower())
    return FavoriteOut(
        symbol=fav.symbol,
        added_at=fav.added_at.isoformat(),
    )


@app.delete(
    "/api/favorites/{symbol}",
    status_code=204,
    summary="Quitar favorito",
)
def remove_favorite(symbol: str) -> None:
    """Saca una moneda de favoritos. No falla si no existe."""
    _favorites.remove(symbol)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get(
    "/api/health",
    response_model=HealthOut,
    summary="Health check",
    description="Indica si el servicio está vivo y si hay API key.",
)
def health() -> HealthOut:
    """Endpoint de health check para monitoreo."""
    return HealthOut(
        status="ok",
        api_key_configured=bool(settings.coingecko_api_key),
        version=_VERSION,
    )
