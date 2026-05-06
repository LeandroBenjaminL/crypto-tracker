"""
ETL Pipeline para crypto-tracker.

Extrae datos de CoinGecko, transforma y carga en PostgreSQL.
Esto permite que la API responda rápido sin llamar a CoinGecko
cada vez que alguien pide un precio.

Flujo:
  1. Conecta a PostgreSQL
  2. Pide las top N criptos a CoinGecko
  3. Las inserta en price_snapshots con timestamp
  4. Listo — la API las toma de ahi
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.adapters.api_client import CoinGeckoClient
from src.adapters.database import PriceSnapshotRow
from src.config import settings

_logger = logging.getLogger("crypto-tracker.pipeline")


def run(database_url: str | None = None, top_n: int = 100) -> int:
    """
    Ejecuta el pipeline ETL.

    Args:
        database_url: URL de PostgreSQL. Si no se pasa, usa la de settings.
        top_n: Cantidad de monedas a traer (default 100, max 250).

    Returns:
        Cantidad de snapshots insertados.

    Raises:
        PipelineError: si algo sale mal.
    """
    db_url = database_url or settings.database_url
    if not db_url:
        msg = "No hay DATABASE_URL configurada"
        raise PipelineError(msg)

    # ------------------------------------------------------------------
    # 1. Conectar a la DB
    # ------------------------------------------------------------------
    engine = create_engine(db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)

    # ------------------------------------------------------------------
    # 2. Extraer datos de CoinGecko
    # ------------------------------------------------------------------
    _logger.info("Extrayendo top %s desde CoinGecko...", top_n)

    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
    )

    raw_coins = client.get_top_coins(limit=top_n, currency="usd")
    _logger.info("Recibidas %s monedas de CoinGecko", len(raw_coins))

    # ------------------------------------------------------------------
    # 3. Transformar y cargar
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    rows: list[PriceSnapshotRow] = []

    for raw in raw_coins:
        try:
            row = PriceSnapshotRow(
                coin_id=raw.get("id", ""),
                symbol=raw.get("symbol", ""),
                name=raw.get("name", ""),
                price=float(raw.get("current_price", 0) or 0),
                change_24h=_safe_float(raw, "price_change_percentage_24h"),
                volume_24h=_safe_float(raw, "total_volume"),
                market_cap=_safe_float(raw, "market_cap"),
                rank=raw.get("market_cap_rank"),
                snapshot_at=now,
            )
            rows.append(row)
        except (ValueError, TypeError) as exc:
            _logger.warning("Saltando moneda inválida %s: %s", raw.get("id"), exc)

    if not rows:
        msg = "No se pudo extraer ninguna moneda válida"
        raise PipelineError(msg)

    # ------------------------------------------------------------------
    # 4. Insertar en lote (batch insert)
    # ------------------------------------------------------------------
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()

    _logger.info("Pipeline completado: %s snapshots insertados", len(rows))
    return len(rows)


def get_latest_snapshot(
    coin_id: str, session_factory: sessionmaker | None = None
) -> PriceSnapshotRow | None:
    """
    Devuelve el snapshot más reciente para una moneda.

    Esto es lo que usa la API para responder rápido.
    """
    db_url = settings.database_url
    if not db_url:
        return None

    engine = create_engine(db_url, pool_pre_ping=True)
    sf = session_factory or sessionmaker(bind=engine)

    try:
        with sf() as session:
            return (
                session.query(PriceSnapshotRow)
                .filter(PriceSnapshotRow.coin_id == coin_id)
                .order_by(PriceSnapshotRow.snapshot_at.desc())
                .first()
            )
    except Exception:
        _logger.exception("Error al leer snapshot de %s", coin_id)
        return None


def get_latest_snapshots(
    coin_ids: list[str],
) -> dict[str, PriceSnapshotRow]:
    """
    Devuelve el snapshot más reciente para varias monedas.

    Returns:
        Dict {coin_id: PriceSnapshotRow} con los que encontró.
    """
    db_url = settings.database_url
    if not db_url or not coin_ids:
        return {}

    engine = create_engine(db_url, pool_pre_ping=True)
    sf = sessionmaker(bind=engine)

    try:
        with sf() as session:
            rows = (
                session.query(PriceSnapshotRow)
                .filter(PriceSnapshotRow.coin_id.in_(coin_ids))
                .order_by(PriceSnapshotRow.snapshot_at.desc())
                .all()
            )

        # De cada moneda, nos quedamos con el snapshot más reciente
        result: dict[str, PriceSnapshotRow] = {}
        for row in rows:
            if row.coin_id not in result:
                result[row.coin_id] = row
        return result
    except Exception:
        _logger.exception("Error al leer snapshots")
        return {}


def _safe_float(raw: dict[str, Any], key: str) -> float | None:
    """Convierte a float o devuelve None si no existe."""
    value = raw.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class PipelineError(Exception):
    """Algo salió mal en el pipeline."""
