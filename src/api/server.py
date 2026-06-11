"""
API REST con FastAPI para crypto-tracker.

Es otra delivery mechanism más, como el CLI y Streamlit. Misma lógica de negocio,
mismos services, pero expuestos como endpoints HTTP con OpenAPI docs.

Uso:
    uvicorn src.api.server:app --reload
    # después: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
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
    PortfolioHolding,
)
from src.core.pipeline import (
    PriceSnapshotRow,
    get_history_from_db,
    get_latest_snapshot,
    get_latest_snapshots,
    get_top_from_db,
)
from src.core.price_service import PriceService

_logger = logging.getLogger("crypto-tracker.api")

# Si hay DATABASE_URL configurada, intentamos PostgreSQL.
# Si la DB no responde o hay error, caemos al JSON file de siempre
# con un log para que el operador sepa que pasó.
if settings.database_url:
    try:
        from src.adapters.database import FavoritesRepository

        _favorites = FavoritesRepository(settings.database_url)
        _favorites_source = "postgresql"
    except Exception as exc:
        _logger.warning("DB no disponible, usando JSON fallback: %s", exc)
        _favorites = FavoritesManager()
        _favorites_source = "json_fallback"
else:
    _favorites = FavoritesManager()
    _favorites_source = "json"

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
    favorites_source: str
    price_source: str = "coingecko"  # "db" si el pipeline ya cargó datos


class HoldingOut(BaseModel):
    """Holding como lo ve el usuario."""

    id: int
    coin_id: str
    symbol: str
    quantity: float
    purchase_price: float
    current_price: float = 0.0
    cost_basis: float
    current_value: float
    pnl: float
    pnl_percent: float
    created_at: str
    updated_at: str | None = None


class HoldingCreate(BaseModel):
    """Datos para crear un holding."""

    coin_id: str
    symbol: str
    quantity: float
    purchase_price: float


class HoldingUpdate(BaseModel):
    """Datos para actualizar un holding."""

    quantity: float | None = None
    purchase_price: float | None = None


class PortfolioSummaryOut(BaseModel):
    """Resumen del portfolio."""

    total_value: float
    total_cost: float
    total_pnl: float
    pnl_percent: float
    holdings_count: int


class ErrorOut(BaseModel):
    """Error con mensaje amigable."""

    detail: str
    code: str | None = None


# ---------------------------------------------------------------------------
# Services singleton
# ---------------------------------------------------------------------------

# La API cachea 120s para que Streamlit no tenga que repreguntar tan seguido
_client = CoinGeckoClient(api_key=settings.coingecko_api_key, cache_ttl=120.0)
_service = PriceService(api_client=_client)
_VERSION = "0.3.0"

# ---------------------------------------------------------------------------
# Precargar datos populares al arrancar (mínimo — el pipeline hace el resto)
# ---------------------------------------------------------------------------

_POPULAR_COINS = ["btc", "eth", "sol", "xrp", "ada"]


def _precache() -> None:
    """
    Precarga mínima al arrancar.

    El pipeline se encarga de mantener los datos frescos.
    Esto es solo para que la primera request no se encuentre
    con la DB vacía si el pipeline aún no corrió.
    """
    import time

    from src.adapters.api_client import CoinGeckoClient, RateLimiter
    from src.core.price_service import PriceService

    precache_client = CoinGeckoClient(
        api_key=settings.coingecko_api_key,
        cache_ttl=30.0,
        rate_limiter=RateLimiter(
            max_calls=2,
            window_seconds=60.0,
            max_wait=30.0,
        ),
    )
    precache_service = PriceService(api_client=precache_client)

    _logger.info("Precarga ligera (background)...")

    # Solo las top 10 para no quemar rate limit
    try:
        precache_service.list_top(limit=10)
        _logger.info("  ✓ Top 10")
    except Exception:
        pass

    # Solo BTC y ETH para calentar
    for symbol in ["btc", "eth"]:
        try:
            precache_service.get_price(symbol)
            _logger.info("  ✓ %s", symbol)
        except Exception:
            pass
        time.sleep(0.5)

    _logger.info("Precarga lista.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Corre migraciones y precarga datos en background."""
    # 1. Migraciones de DB (si hay DATABASE_URL)
    from src.adapters.database import run_migrations

    try:
        run_migrations()
    except Exception as exc:
        _logger.warning("Migraciones fallaron (la API igual arranca): %s", exc)

    # 2. Precarga en background
    t = threading.Thread(target=_precache, daemon=True)
    t.start()
    yield


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


def _snapshot_to_coin_out(row: PriceSnapshotRow) -> CoinOut:
    """Convierte un PriceSnapshotRow directamente a CoinOut (sin tocar CoinGecko)."""
    return CoinOut(
        id=row.coin_id,
        symbol=row.symbol,
        name=row.name,
        rank=row.rank or 0,
        price=row.price,
        change_24h=row.change_24h,
        volume_24h=row.volume_24h,
        market_cap=row.market_cap,
        price_formatted=(
            f"${row.price:,.2f}"
            if row.price >= 1
            else f"${row.price:.4f}"
            if row.price >= 0.01
            else f"${row.price:.8f}"
        ),
    )


def _try_db_price(query: str) -> CoinOut | None:
    """
    Intenta resolver un precio desde PostgreSQL.

    1. Resuelve el query a coin_id (símbolo → ID)
    2. Busca el snapshot más reciente en la DB
    3. Si hay datos frescos, devuelve CoinOut sin tocar CoinGecko

    Returns None si no hay DB o no encontró datos.
    """
    if not settings.database_url:
        return None

    # Resolver símbolo a coin_id usando el mapping local
    from src.core.price_service import _normalize_query, _try_resolve_id

    try:
        coin_id = _try_resolve_id(query) or _normalize_query(query)
    except Exception:
        coin_id = query.strip().lower()

    snapshot = get_latest_snapshot(coin_id)
    if snapshot is None:
        return None

    return _snapshot_to_coin_out(snapshot)


def _try_db_prices(queries: list[str]) -> tuple[dict[str, CoinOut], list[str]]:
    """
    Intenta resolver múltiples precios desde PostgreSQL.

    Returns:
        (found: dict {query: CoinOut}, missing: list de queries que no estaban en DB)
    """
    if not settings.database_url:
        return {}, list(queries)

    from src.core.price_service import SYMBOL_TO_ID, _normalize_query

    # Resolver queries a coin_ids
    coin_ids: list[str] = []
    query_to_id: dict[str, str] = {}
    for q in queries:
        try:
            cid = SYMBOL_TO_ID.get(q.strip().lower()) or _normalize_query(q)
        except Exception:
            cid = q.strip().lower()
        coin_ids.append(cid)
        query_to_id[q] = cid

    # Buscar todos los snapshots en un solo query
    snapshots = get_latest_snapshots(coin_ids)

    found: dict[str, CoinOut] = {}
    missing: list[str] = []
    for q, cid in query_to_id.items():
        snap = snapshots.get(cid)
        if snap is not None:
            found[q] = _snapshot_to_coin_out(snap)
        else:
            missing.append(q)

    return found, missing


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
    Al arrancar precarga datos populares para que responda más rápido.
    """,
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
async def cryptotracker_exception_handler(request: Any, exc: CryptoTrackerError) -> Any:
    """Cualquier error del dominio se traduce a HTTP con mensaje amigable."""
    raise _map_error(exc)


# ---------------------------------------------------------------------------
# Endpoints de precio
# ---------------------------------------------------------------------------


@app.get(
    "/api/price/{query}",
    response_model=CoinOut,
    summary="Precio de una moneda",
    description="Buscá por ID (bitcoin), símbolo (btc) o nombre (Bitcoin)."
    " Si el pipeline ya cargó datos, responde desde PostgreSQL (ms)."
    " Si no, consulta CoinGecko directamente (fallback).",
)
def get_price(query: str, currency: str = "usd") -> CoinOut:
    """
    Precio actual de una criptomoneda.

    Estrategia (Opción B):
      1. Buscar en PostgreSQL (rápido, datos del pipeline)
      2. Si no hay, llamar a CoinGecko (fallback)
    """
    # Intento 1: DB (si el pipeline ya pasó)
    db_result = _try_db_price(query)
    if db_result is not None:
        return db_result

    # Intento 2: CoinGecko (fallback)
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

    # Intento 1: DB (batch)
    found, missing = _try_db_prices(queries)

    # Intento 2: CoinGecko para las que no estaban en DB
    if missing:
        try:
            results = _service.get_prices(missing, currency=currency)
            for r in results:
                found[r.coin.symbol] = _coin_to_out(r)
        except Exception:
            pass  # las que no se pudieron, se pierden

    # Devolver en el mismo orden que se pidieron
    return [found[q] for q in queries if q in found]


@app.get(
    "/api/top",
    response_model=list[CoinOut],
    summary="Top monedas por market cap",
    description="Las N monedas con mayor capitalización."
    " Si el pipeline cargó datos, responde desde PostgreSQL (ms)."
    " Si no, consulta CoinGecko.",
)
def get_top(limit: int = 10, currency: str = "usd") -> list[CoinOut]:
    """
    Las N monedas con mayor capitalización de mercado.

    Estrategia:
      1. Leer desde price_snapshots (datos del pipeline)
      2. Si no hay, llamar a CoinGecko
    """
    # Intento 1: DB
    db_rows = get_top_from_db(limit=limit)
    if db_rows:
        return [_snapshot_to_coin_out(r) for r in db_rows]

    # Intento 2: CoinGecko (fallback)
    results = _service.list_top(limit=limit, currency=currency)
    return [_coin_to_out(r) for r in results]


@app.get(
    "/api/history/{query}",
    response_model=list[HistoryPoint],
    summary="Precio histórico",
    description="Datos para graficar. Params: days (1,7,30,90,365,'max')."
    " Si el pipeline cacheó los datos, responde desde PostgreSQL.",
)
def get_history(query: str, days: int = 7, currency: str = "usd") -> list[dict[str, float]]:
    """
    Historial de precios para una moneda.

    Estrategia:
      1. Buscar en price_history
      2. Si no hay, llamar a CoinGecko
    """
    from src.core.price_service import SYMBOL_TO_ID

    # Resolver símbolo a coin_id
    coin_id = SYMBOL_TO_ID.get(query.strip().lower(), query.strip().lower())

    # Intento 1: DB
    cached = get_history_from_db(coin_id, days=days)
    if cached is not None:
        return cached

    # Intento 2: CoinGecko (fallback)
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
    return [CoinOut(id=c.id, symbol=c.symbol, name=c.name, rank=c.rank) for c in coins]


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
    normalized = symbol.strip().lower()
    _favorites.add(normalized)
    favs = _favorites.list_all()
    fav = next(
        (f for f in favs if f.symbol == normalized),
        None,
    )
    if fav is None:
        raise HTTPException(
            status_code=500,
            detail="El favorito se agregó pero no se pudo verificar",
        )
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
# Price Alerts
# ---------------------------------------------------------------------------


class AlertOut(BaseModel):
    """Alerta como la ve el usuario."""

    id: int
    coin_id: str
    symbol: str | None
    target_price: float
    condition: str
    is_active: bool
    triggered_at: str | None
    created_at: str


class AlertCreate(BaseModel):
    """Datos para crear una alerta."""

    coin_id: str
    target_price: float
    condition: str = "above"  # above | below
    symbol: str | None = None


class AlertTriggeredOut(BaseModel):
    """Alerta que se disparó."""

    id: int
    coin_id: str
    symbol: str | None
    target_price: float
    condition: str
    triggered_at: str


@app.post(
    "/api/alerts",
    response_model=AlertOut,
    status_code=201,
    summary="Crear alerta de precio",
    description="Ej: avisame cuando Bitcoin supere los $100,000",
)
def create_alert(data: AlertCreate) -> AlertOut:
    """Crea una alerta de precio."""
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.adapters.database import PriceAlertRow
    from src.core.price_service import SYMBOL_TO_ID

    if not settings.database_url:
        raise HTTPException(400, "Se necesita PostgreSQL para alertas")

    # Resolver símbolo a coin_id si es necesario
    coin_id = SYMBOL_TO_ID.get(data.coin_id.strip().lower(), data.coin_id.strip().lower())

    engine = create_engine(settings.database_url)
    row = PriceAlertRow(
        coin_id=coin_id,
        symbol=data.symbol or coin_id,
        target_price=data.target_price,
        condition=data.condition,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)

    return AlertOut(
        id=row.id,
        coin_id=row.coin_id,
        symbol=row.symbol,
        target_price=row.target_price,
        condition=row.condition,
        is_active=bool(row.is_active),
        triggered_at=row.triggered_at.isoformat() if row.triggered_at else None,
        created_at=row.created_at.isoformat(),
    )


@app.get(
    "/api/alerts",
    response_model=list[AlertOut],
    summary="Listar alertas",
    description="Todas las alertas activas (no triggered).",
)
def list_alerts() -> list[AlertOut]:
    """Lista alertas activas."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.adapters.database import PriceAlertRow

    if not settings.database_url:
        return []

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        rows = (
            session.query(PriceAlertRow)
            .filter(PriceAlertRow.is_active == 1)
            .order_by(PriceAlertRow.created_at.desc())
            .all()
        )
        return [
            AlertOut(
                id=r.id,
                coin_id=r.coin_id,
                symbol=r.symbol,
                target_price=r.target_price,
                condition=r.condition,
                is_active=bool(r.is_active),
                triggered_at=r.triggered_at.isoformat() if r.triggered_at else None,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]


@app.get(
    "/api/alerts/triggered",
    response_model=list[AlertTriggeredOut],
    summary="Alertas disparadas",
    description="Alertas que ya se cumplieron.",
)
def list_triggered_alerts() -> list[AlertTriggeredOut]:
    """Lista alertas que ya se dispararon."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.adapters.database import PriceAlertRow

    if not settings.database_url:
        return []

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        rows = (
            session.query(PriceAlertRow)
            .filter(PriceAlertRow.is_active == 0)
            .order_by(PriceAlertRow.triggered_at.desc())
            .all()
        )
        return [
            AlertTriggeredOut(
                id=r.id,
                coin_id=r.coin_id,
                symbol=r.symbol,
                target_price=r.target_price,
                condition=r.condition,
                triggered_at=r.triggered_at.isoformat(),
            )
            for r in rows
        ]


@app.delete(
    "/api/alerts/{alert_id}",
    status_code=204,
    summary="Cancelar alerta",
)
def delete_alert(alert_id: int) -> None:
    """Cancela una alerta (la desactiva, no la borra)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.adapters.database import PriceAlertRow

    if not settings.database_url:
        raise HTTPException(400, "Se necesita PostgreSQL para alertas")

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        alert = session.query(PriceAlertRow).filter(PriceAlertRow.id == alert_id).first()
        if alert is None:
            raise HTTPException(404, "Alerta no encontrada")
        alert.is_active = 0
        session.commit()


# ---------------------------------------------------------------------------
# Pipeline monitoring
# ---------------------------------------------------------------------------


@app.get(
    "/api/pipeline/stats",
    summary="Estadísticas del pipeline ETL",
    description="Muestra cantidad de ejecuciones, tasa de éxito, última corrida.",
)
def pipeline_stats() -> dict:
    """Estadísticas de las ejecuciones del pipeline."""
    from src.core.pipeline import get_pipeline_stats

    stats = get_pipeline_stats()
    if stats is None:
        return {"total_runs": 0, "message": "No hay DB o no hay datos aún"}
    return stats


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
    # Detectar si el pipeline ya cargó datos en la DB
    price_source = "coingecko"
    if settings.database_url:
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(settings.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM price_snapshots"))
                count = result.scalar()
                if count and count > 0:
                    price_source = "db"
        except Exception:
            pass

    return HealthOut(
        status="ok",
        api_key_configured=bool(settings.coingecko_api_key),
        version=_VERSION,
        favorites_source=_favorites_source,
        price_source=price_source,
    )


# ---------------------------------------------------------------------------
# Portfolio Holdings CRUD
# ---------------------------------------------------------------------------


def _holding_to_out(holding: PortfolioHolding) -> HoldingOut:
    """Convierte un PortfolioHolding del dominio a HoldingOut para la API."""
    return HoldingOut(
        id=holding.id,
        coin_id=holding.coin_id,
        symbol=holding.symbol,
        quantity=holding.quantity,
        purchase_price=holding.purchase_price,
        current_price=holding.current_price,
        cost_basis=holding.cost_basis,
        current_value=holding.current_value,
        pnl=holding.pnl,
        pnl_percent=holding.pnl_percent,
        created_at=holding.created_at.isoformat(),
        updated_at=holding.updated_at.isoformat() if holding.updated_at else None,
    )


@app.post(
    "/api/holdings",
    response_model=HoldingOut,
    status_code=201,
    summary="Crear holding",
    description="Agrega una posición al portfolio.",
)
def create_holding(data: HoldingCreate) -> HoldingOut:
    """Crea un nuevo holding en el portfolio."""
    from src.adapters.database import PortfolioRepository

    if not settings.database_url:
        raise HTTPException(400, "Se necesita DATABASE_URL para usar el portfolio")

    # Validar quantity y purchase_price
    if data.quantity <= 0:
        raise HTTPException(422, "Quantity debe ser mayor a 0")
    if data.purchase_price < 0:
        raise HTTPException(422, "Purchase price no puede ser negativo")

    repo = PortfolioRepository(settings.database_url)
    holding = repo.create(
        coin_id=data.coin_id,
        symbol=data.symbol,
        quantity=data.quantity,
        purchase_price=data.purchase_price,
    )
    return _holding_to_out(holding)


@app.get(
    "/api/holdings",
    response_model=list[HoldingOut],
    summary="Listar holdings",
    description="Lista todas las posiciones del portfolio.",
)
def list_holdings() -> list[HoldingOut]:
    """Lista todos los holdings del portfolio."""
    from src.adapters.database import PortfolioRepository
    from src.core.pipeline import get_latest_snapshots

    if not settings.database_url:
        raise HTTPException(400, "Se necesita DATABASE_URL para usar el portfolio")

    repo = PortfolioRepository(settings.database_url)
    holdings = repo.list_all()

    # Obtener precios actuales para calcular P&L
    coin_ids = [h.coin_id for h in holdings]
    snapshots = get_latest_snapshots(coin_ids) if coin_ids else {}
    current_prices: dict[str, float] = {s.coin_id: s.price for s in snapshots.values()}

    # Actualizar cada holding con current_price y devolver
    result: list[HoldingOut] = []
    for h in holdings:
        h.current_price = current_prices.get(h.coin_id, h.purchase_price)
        result.append(_holding_to_out(h))

    return result


@app.put(
    "/api/holdings/{holding_id}",
    response_model=HoldingOut,
    summary="Actualizar holding",
    description="Actualiza quantity y/o purchase_price de un holding.",
)
def update_holding(holding_id: int, data: HoldingUpdate) -> HoldingOut:
    """Actualiza un holding existente."""
    from src.adapters.database import PortfolioRepository

    if not settings.database_url:
        raise HTTPException(400, "Se necesita DATABASE_URL para usar el portfolio")

    # Validar
    if data.quantity is not None and data.quantity <= 0:
        raise HTTPException(422, "Quantity debe ser mayor a 0")
    if data.purchase_price is not None and data.purchase_price < 0:
        raise HTTPException(422, "Purchase price no puede ser negativo")

    repo = PortfolioRepository(settings.database_url)
    holding = repo.update(
        holding_id=holding_id,
        quantity=data.quantity,
        purchase_price=data.purchase_price,
    )
    if holding is None:
        raise HTTPException(404, "Holding no encontrado")

    return _holding_to_out(holding)


@app.delete(
    "/api/holdings/{holding_id}",
    status_code=204,
    summary="Eliminar holding",
    description="Elimina una posición del portfolio.",
)
def delete_holding(holding_id: int) -> None:
    """Elimina un holding."""
    from src.adapters.database import PortfolioRepository

    if not settings.database_url:
        raise HTTPException(400, "Se necesita DATABASE_URL para usar el portfolio")

    repo = PortfolioRepository(settings.database_url)
    deleted = repo.delete(holding_id)
    if not deleted:
        raise HTTPException(404, "Holding no encontrado")


# ---------------------------------------------------------------------------
# Portfolio Summary
# ---------------------------------------------------------------------------


@app.get(
    "/api/portfolio/summary",
    response_model=PortfolioSummaryOut,
    summary="Resumen del portfolio",
    description="Muestra valor total, costo total, P&L total del portfolio.",
)
def portfolio_summary() -> PortfolioSummaryOut:
    """Resumen agregado del portfolio."""
    from src.adapters.database import PortfolioRepository
    from src.core.pipeline import get_latest_snapshots

    if not settings.database_url:
        raise HTTPException(400, "Se necesita DATABASE_URL para usar el portfolio")

    repo = PortfolioRepository(settings.database_url)

    # Obtener precios actuales
    holdings = repo.list_all()
    coin_ids = [h.coin_id for h in holdings]
    snapshots = get_latest_snapshots(coin_ids) if coin_ids else {}
    current_prices: dict[str, float] = {s.coin_id: s.price for s in snapshots.values()}

    summary = repo.get_summary(current_prices)
    return PortfolioSummaryOut(**summary)
