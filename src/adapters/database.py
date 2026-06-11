"""
Adapter de base de datos para crypto-tracker.

Usa SQLAlchemy 2.0 para conectarse a PostgreSQL (o SQLite en testing).
Reemplaza el JSON file de FavoritesManager por una tabla real.

Convivencia pacífica: si no hay DATABASE_URL configurada, el server
sigue usando el JSON file de siempre. Esto permite desarrollo local
sin PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.core.exceptions import CryptoTrackerError
from src.core.models import FavoriteCoin, PortfolioHolding

_logger = logging.getLogger("crypto-tracker.db")


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Base para todos los modelos SQLAlchemy."""


class FavoriteRow(Base):
    """Una fila en la tabla favorites."""

    __tablename__ = "favorites"

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PriceSnapshotRow(Base):
    """
    Una fila en la tabla price_snapshots.

    Guarda el precio de una cripto en un momento específico.
    Cada corrida del pipeline inserta N filas (una por moneda).
    """

    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    change_24h: Mapped[float] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PriceHistoryRow(Base):
    """
    Historial de precios cacheado en DB.

    Guarda el resultado de /api/history para cada moneda y período
    (7, 30, 90, 365 días). El pipeline refresca esto cada 6 horas.
    La API lo sirve sin tocar CoinGecko.
    """

    __tablename__ = "price_history"

    coin_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    days: Mapped[int] = mapped_column(Integer, primary_key=True)  # 7, 30, 90, 365
    data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: [{"timestamp": ..., "price": ...}]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PipelineRunRow(Base):
    """
    Registro de una ejecución del pipeline ETL.

    Cada vez que corre el pipeline (cada 30min en GitHub Actions,
    o manual), se guarda una fila acá. Permite monitorear
    estado, tiempos y errores.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # running | success | error
    snapshots_inserted: Mapped[int] = mapped_column(Integer, default=0)
    history_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")  # manual | schedule


class PriceAlertRow(Base):
    """
    Una alerta de precio configurada por el usuario.

    Se crea con un coin_id, un precio objetivo y una condición
    (above/below). El pipeline checkea las activas después de
    cada snapshot y las marca como triggered cuando se cumplen.
    """

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)  # above | below
    symbol: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, default=True)  # SQLAlchemy: Integer como bool
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PortfolioHoldingRow(Base):
    """
    Una fila en la tabla portfolio_holdings.

    Guarda las posiciones del usuario: qué moneda, cuántos tokens,
    y a qué precio se compraron. Sirve para calcular P&L.
    """

    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)





# ---------------------------------------------------------------------------
# Migraciones de Alembic
# ---------------------------------------------------------------------------


def run_migrations(database_url: str | None = None) -> None:
    """
    Ejecuta `alembic upgrade head` programáticamente.

    Se llama al arrancar la API y al ejecutar el pipeline.
    Si no hay DATABASE_URL configurada, no hace nada (modo dev sin DB).

    Usa la URL provista o la del settings. Con eso configura Alembic
    y aplica todas las migraciones pendientes.
    """
    from src.config import settings

    db_url = database_url or settings.database_url
    if not db_url:
        _logger.info("No hay DATABASE_URL — salteando migraciones")
        return

    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "migrations")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        _logger.info("Corriendo migraciones de Alembic...")
        command.upgrade(alembic_cfg, "head")
        _logger.info("Migraciones aplicadas correctamente")
    except Exception as exc:
        _logger.warning("Error al correr migraciones: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Excepción propia del repositorio
# ---------------------------------------------------------------------------


class RepositoryError(CryptoTrackerError):
    """Algo salió mal en el repositorio de base de datos."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class FavoritesRepository:
    """
    Repositorio de favoritos contra PostgreSQL.

    Reemplaza a FavoritesManager cuando hay DB disponible.
    Misma interfaz, distinto backend.
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
    ) -> None:
        # SQLite no soporta pool_size/max_overflow (usa SingletonThreadPool).
        # PostgreSQL sí — se los pasamos solo cuando aplican.
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if not database_url.startswith("sqlite"):
            kwargs["pool_size"] = pool_size
            kwargs["max_overflow"] = max_overflow

        self._engine = create_engine(database_url, **kwargs)
        self._session_factory = sessionmaker(bind=self._engine)

        # Crear tablas si no existen (útil para primera vez / dev)
        Base.metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # Public API (misma firma que FavoritesManager)
    # ------------------------------------------------------------------

    def list_all(self) -> list[FavoriteCoin]:
        """Todos los favoritos, ordenados por fecha."""
        try:
            with self._session_factory() as session:
                rows = (
                    session.query(FavoriteRow)
                    .order_by(FavoriteRow.added_at)
                    .all()
                )
                return [
                    FavoriteCoin(symbol=r.symbol, added_at=r.added_at)
                    for r in rows
                ]
        except OperationalError as exc:
            _logger.error("DB error listing favorites: %s", exc)
            raise RepositoryError("No se pudieron leer los favoritos") from exc

    def add(self, symbol: str) -> None:
        """Agrega un favorito (idempotente)."""
        normalized = symbol.strip().lower()
        if not normalized:
            raise ValueError("Symbol cannot be empty")

        try:
            with self._session_factory() as session:
                session.add(FavoriteRow(symbol=normalized))
                session.commit()
        except IntegrityError:
            # Ya existe — es idempotente. El race condition de dos POST
            # simultáneos también cae acá y se maneja silenciosamente.
            pass
        except OperationalError as exc:
            _logger.error("DB error adding favorite '%s': %s", normalized, exc)
            raise RepositoryError("No se pudo agregar el favorito") from exc

    def remove(self, symbol: str) -> None:
        """Elimina un favorito."""
        normalized = symbol.strip().lower()
        if not normalized:
            raise ValueError("Symbol cannot be empty")

        try:
            with self._session_factory() as session:
                session.query(FavoriteRow).filter(
                    FavoriteRow.symbol == normalized
                ).delete()
                session.commit()
        except OperationalError as exc:
            _logger.error("DB error removing favorite '%s': %s", normalized, exc)
            raise RepositoryError("No se pudo eliminar el favorito") from exc

    def is_favorite(self, symbol: str) -> bool:
        """Chequea si un símbolo está en favoritos."""
        normalized = symbol.strip().lower()
        if not normalized:
            return False

        try:
            with self._session_factory() as session:
                return (
                    session.query(FavoriteRow)
                    .filter(FavoriteRow.symbol == normalized)
                    .first()
                ) is not None
        except OperationalError as exc:
            _logger.error("DB error checking favorite '%s': %s", normalized, exc)
            raise RepositoryError("No se pudo verificar el favorito") from exc


class PortfolioRepository:
    """
    Repositorio de holdings de portfolio contra PostgreSQL.

    Maneja las posiciones del usuario: crear, leer, actualizar,
    y eliminar holdings. Calcula P&L basado en precios actuales.
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
    ) -> None:
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if not database_url.startswith("sqlite"):
            kwargs["pool_size"] = pool_size
            kwargs["max_overflow"] = max_overflow

        self._engine = create_engine(database_url, **kwargs)
        self._session_factory = sessionmaker(bind=self._engine)

        # Crear tablas si no existen
        Base.metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def list_all(self) -> list[PortfolioHolding]:
        """Lista todos los holdings del portfolio."""
        try:
            with self._session_factory() as session:
                rows = (
                    session.query(PortfolioHoldingRow)
                    .order_by(PortfolioHoldingRow.created_at.desc())
                    .all()
                )
                return [self._row_to_holding(r) for r in rows]
        except OperationalError as exc:
            _logger.error("DB error listing holdings: %s", exc)
            raise RepositoryError("No se pudieron leer los holdings") from exc

    def get_by_id(self, holding_id: int) -> PortfolioHolding | None:
        """Busca un holding por ID."""
        try:
            with self._session_factory() as session:
                row = (
                    session.query(PortfolioHoldingRow)
                    .filter(PortfolioHoldingRow.id == holding_id)
                    .first()
                )
                return self._row_to_holding(row) if row else None
        except OperationalError as exc:
            _logger.error("DB error getting holding %d: %s", holding_id, exc)
            raise RepositoryError("No se pudo leer el holding") from exc

    def create(
        self,
        coin_id: str,
        symbol: str,
        quantity: float,
        purchase_price: float,
    ) -> PortfolioHolding:
        """Crea un nuevo holding."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if purchase_price < 0:
            raise ValueError("Purchase price cannot be negative")

        normalized_symbol = symbol.strip().lower()
        normalized_coin_id = coin_id.strip().lower()

        try:
            with self._session_factory() as session:
                row = PortfolioHoldingRow(
                    coin_id=normalized_coin_id,
                    symbol=normalized_symbol,
                    quantity=quantity,
                    purchase_price=purchase_price,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                return self._row_to_holding(row)
        except OperationalError as exc:
            _logger.error("DB error creating holding: %s", exc)
            raise RepositoryError("No se pudo crear el holding") from exc

    def update(
        self,
        holding_id: int,
        quantity: float | None = None,
        purchase_price: float | None = None,
    ) -> PortfolioHolding | None:
        """Actualiza un holding existente."""
        try:
            with self._session_factory() as session:
                row = (
                    session.query(PortfolioHoldingRow)
                    .filter(PortfolioHoldingRow.id == holding_id)
                    .first()
                )
                if row is None:
                    return None

                if quantity is not None:
                    if quantity <= 0:
                        raise ValueError("Quantity must be positive")
                    row.quantity = quantity
                if purchase_price is not None:
                    if purchase_price < 0:
                        raise ValueError("Purchase price cannot be negative")
                    row.purchase_price = purchase_price

                row.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(row)
                return self._row_to_holding(row)
        except OperationalError as exc:
            _logger.error("DB error updating holding %d: %s", holding_id, exc)
            raise RepositoryError("No se pudo actualizar el holding") from exc

    def delete(self, holding_id: int) -> bool:
        """Elimina un holding. Retorna True si existía."""
        try:
            with self._session_factory() as session:
                row = (
                    session.query(PortfolioHoldingRow)
                    .filter(PortfolioHoldingRow.id == holding_id)
                    .first()
                )
                if row is None:
                    return False
                session.delete(row)
                session.commit()
                return True
        except OperationalError as exc:
            _logger.error("DB error deleting holding %d: %s", holding_id, exc)
            raise RepositoryError("No se pudo eliminar el holding") from exc

    # ------------------------------------------------------------------
    # Portfolio Summary (with current prices)
    # ------------------------------------------------------------------

    def get_summary(self, current_prices: dict[str, float]) -> dict:
        """
        Calcula el resumen del portfolio.

        Args:
            current_prices: dict {coin_id: current_price} desde CoinGecko o DB

        Returns:
            {total_value, total_cost, total_pnl, pnl_percent, holdings_count}
        """
        holdings = self.list_all()
        if not holdings:
            return {
                "total_value": 0.0,
                "total_cost": 0.0,
                "total_pnl": 0.0,
                "pnl_percent": 0.0,
                "holdings_count": 0,
            }

        total_cost = 0.0
        total_value = 0.0

        for holding in holdings:
            # Usar current_price del dict o fallback al purchase_price
            current = current_prices.get(holding.coin_id, holding.purchase_price)

            # Update holding con current_price para cálculo
            holding.current_price = current

            total_cost += holding.cost_basis
            total_value += holding.current_value

        total_pnl = total_value - total_cost
        pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
            "holdings_count": len(holdings),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_holding(self, row: PortfolioHoldingRow) -> PortfolioHolding:
        """Convierte una fila del DB a PortfolioHolding del dominio."""
        return PortfolioHolding(
            id=row.id,
            coin_id=row.coin_id,
            symbol=row.symbol,
            quantity=row.quantity,
            purchase_price=row.purchase_price,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
