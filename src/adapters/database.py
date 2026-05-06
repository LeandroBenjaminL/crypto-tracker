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
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.exceptions import CryptoTrackerError
from src.core.models import FavoriteCoin

_logger = logging.getLogger("crypto-tracker.db")


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Base para todos los modelos SQLAlchemy."""


class FavoriteRow(Base):
    """Una fila en la tabla favorites."""

    __tablename__ = "favorites"

    symbol: str = Column(String(50), primary_key=True)
    added_at: datetime = Column(
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

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    coin_id: str = Column(String(100), nullable=False, index=True)
    symbol: str = Column(String(20), nullable=False)
    name: str = Column(String(100), nullable=False)
    price: float = Column(Float, nullable=False)
    change_24h: float = Column(Float, nullable=True)
    volume_24h: float = Column(Float, nullable=True)
    market_cap: float = Column(Float, nullable=True)
    rank: int = Column(Integer, nullable=True)
    snapshot_at: datetime = Column(
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

    coin_id: str = Column(String(100), primary_key=True)
    days: int = Column(Integer, primary_key=True)  # 7, 30, 90, 365
    data: str = Column(Text, nullable=False)  # JSON: [{"timestamp": ..., "price": ...}]
    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


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
                    is not None
                )
        except OperationalError as exc:
            _logger.error("DB error checking favorite '%s': %s", normalized, exc)
            raise RepositoryError("No se pudo verificar el favorito") from exc
