"""
ETL Pipeline para crypto-tracker.

Extrae datos de CoinGecko, transforma y carga en PostgreSQL.
Esto permite que la API responda rápido sin llamar a CoinGecko
cada vez que alguien pide un precio.

Flujo completo:
  1. Conecta a PostgreSQL
  2. Pide las top N criptos a CoinGecko → price_snapshots
  3. Si pasaron +6h desde la última vez, también trae histórico
     de las top 20 monedas → price_history
  4. La API lee de ambas tablas, CoinGecko es solo el fallback
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.adapters.api_client import CoinGeckoClient
from src.adapters.database import PriceHistoryRow, PriceSnapshotRow
from src.config import settings

_logger = logging.getLogger("crypto-tracker.pipeline")

# Períodos de histórico a cachear
_HISTORY_DAYS = [7, 30, 90]

# Monedas populares para las que cacheamos histórico
_TOP_HISTORY_COINS = 20

# Cada cuánto refrescamos el histórico (6 horas)
_HISTORY_TTL = timedelta(hours=6)


# ======================================================================
# Pipeline principal
# ======================================================================


def run(database_url: str | None = None, top_n: int = 100) -> dict[str, int]:
    """
    Ejecuta el pipeline ETL completo.

    Args:
        database_url: URL de PostgreSQL. Si no se pasa, usa la de settings.
        top_n: Cantidad de monedas a traer (default 100, max 250).

    Returns:
        Dict con stats: {"snapshots": N, "history_updated": bool}
    """
    db_url = database_url or settings.database_url
    if not db_url:
        msg = "No hay DATABASE_URL configurada"
        raise PipelineError(msg)

    engine = create_engine(db_url, pool_pre_ping=True)

    # ------------------------------------------------------------------
    # 1. Snapshots de precios (cada 30 min)
    # ------------------------------------------------------------------
    _logger.info("Extrayendo top %s desde CoinGecko...", top_n)
    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
    )

    raw_coins = client.get_top_coins(limit=top_n, currency="usd")
    _logger.info("Recibidas %s monedas", len(raw_coins))

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

    with Session(engine) as session:
        session.add_all(rows)
        session.commit()

    stats: dict[str, int] = {"snapshots": len(rows), "history_updated": 0}

    # ------------------------------------------------------------------
    # 2. Histórico de precios (cada 6h)
    # ------------------------------------------------------------------
    history_updated = _refresh_history_if_stale(client, engine)
    if history_updated:
        stats["history_updated"] = history_updated
    else:
        stats["history_updated"] = 0

    _logger.info(
        "Pipeline completado: %s snapshots, %s históricos actualizados",
        stats["snapshots"],
        stats["history_updated"],
    )
    return stats


# ======================================================================
# Histórico
# ======================================================================


def _refresh_history_if_stale(
    client: CoinGeckoClient,
    engine: Any,
) -> int:
    """
    Refresca el histórico si pasaron más de _HISTORY_TTL desde la última vez.

    Returns: cantidad de monedas actualizadas, 0 si no hizo falta.
    """
    session_factory = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)

    # Primero: identificar qué monedas top tenemos
    top_coin_ids: list[str] = []
    try:
        with session_factory() as session:
            # La última tanda de snapshots nos dice las monedas top actuales
            latest_batch = (
                session.query(PriceSnapshotRow)
                .order_by(PriceSnapshotRow.snapshot_at.desc())
                .limit(_TOP_HISTORY_COINS)
                .all()
            )
            # Sacamos coin_ids únicos (puede haber repetidos del último batch)
            seen: set[str] = set()
            for row in latest_batch:
                if row.coin_id not in seen:
                    seen.add(row.coin_id)
                    top_coin_ids.append(row.coin_id)
    except Exception:
        _logger.warning("No se pudieron leer las monedas top de la DB")
        return 0

    if not top_coin_ids:
        _logger.warning("No hay monedas en la DB para refrescar histórico")
        return 0

    updated_count = 0
    for coin_id in top_coin_ids:
        for days in _HISTORY_DAYS:
            # Ver si ya tenemos datos frescos
            try:
                with session_factory() as session:
                    existing = (
                        session.query(PriceHistoryRow)
                        .filter(
                            PriceHistoryRow.coin_id == coin_id,
                            PriceHistoryRow.days == days,
                        )
                        .first()
                    )
                    if existing and (now - existing.updated_at) < _HISTORY_TTL:
                        continue  # está fresco, no tocar
            except Exception:
                pass  # si hay error, intentamos refrescar igual

            # Refrescar desde CoinGecko
            try:
                raw = client.get_coin_history(
                    coin_id, days=days, currency="usd"
                )
                prices = raw.get("prices", [])
                # Filtramos nulls y formateamos
                clean_data = [
                    {"timestamp": ts, "price": price}
                    for ts, price in prices
                    if price is not None
                ]
                data_json = json.dumps(clean_data)

                with session_factory() as session:
                    # Upsert: borramos lo viejo e insertamos nuevo
                    session.query(PriceHistoryRow).filter(
                        PriceHistoryRow.coin_id == coin_id,
                        PriceHistoryRow.days == days,
                    ).delete()
                    session.add(
                        PriceHistoryRow(
                            coin_id=coin_id,
                            days=days,
                            data=data_json,
                            updated_at=now,
                        )
                    )
                    session.commit()

                _logger.info("  ✓ %s %sd history", coin_id, days)
                updated_count += 1

            except Exception as exc:
                _logger.warning(
                    "  ✗ %s %sd: %s", coin_id, days, exc
                )

    return updated_count


# ======================================================================
# Funciones para la API (lectura desde DB)
# ======================================================================


def get_latest_snapshot(
    coin_id: str,
) -> PriceSnapshotRow | None:
    """Devuelve el snapshot más reciente para una moneda."""
    engine = _get_engine()
    if engine is None:
        return None

    try:
        with Session(engine) as session:
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
    Returns: dict {coin_id: PriceSnapshotRow}
    """
    engine = _get_engine()
    if engine is None or not coin_ids:
        return {}

    try:
        with Session(engine) as session:
            rows = (
                session.query(PriceSnapshotRow)
                .filter(PriceSnapshotRow.coin_id.in_(coin_ids))
                .order_by(PriceSnapshotRow.snapshot_at.desc())
                .all()
            )

        result: dict[str, PriceSnapshotRow] = {}
        for row in rows:
            if row.coin_id not in result:
                result[row.coin_id] = row
        return result
    except Exception:
        _logger.exception("Error al leer snapshots")
        return {}


def get_top_from_db(limit: int = 10) -> list[PriceSnapshotRow] | None:
    """
    Devuelve las top N monedas desde price_snapshots.

    Usa la última tanda de snapshots (mismo snapshot_at)
    ordenada por rank. Si no hay datos, devuelve None.
    """
    engine = _get_engine()
    if engine is None:
        return None

    try:
        with Session(engine) as session:
            # Encontrar el último timestamp de snapshot
            latest_time = (
                session.query(PriceSnapshotRow.snapshot_at)
                .order_by(PriceSnapshotRow.snapshot_at.desc())
                .first()
            )
            if not latest_time:
                return None

            rows = (
                session.query(PriceSnapshotRow)
                .filter(PriceSnapshotRow.snapshot_at == latest_time[0])
                .order_by(PriceSnapshotRow.rank.asc().nullslast())
                .limit(limit)
                .all()
            )
            return rows if rows else None
    except Exception:
        _logger.exception("Error al leer top desde DB")
        return None


def get_history_from_db(
    coin_id: str, days: int = 7
) -> list[dict[str, float]] | None:
    """
    Devuelve histórico de precios desde price_history.

    Returns: lista de {timestamp, price} o None si no hay datos frescos.
    """
    engine = _get_engine()
    if engine is None:
        return None

    try:
        with Session(engine) as session:
            row = (
                session.query(PriceHistoryRow)
                .filter(
                    PriceHistoryRow.coin_id == coin_id,
                    PriceHistoryRow.days == days,
                )
                .first()
            )
            if row is None:
                return None

            # Verificar que no esté muy viejo (> 24h para history)
            age = datetime.now(timezone.utc) - row.updated_at
            if age > timedelta(hours=24):
                _logger.info(
                    "History for %s %sd is stale (%s old), skipping",
                    coin_id, days, age,
                )
                return None

            return json.loads(row.data)
    except Exception:
        _logger.exception("Error al leer history de %s %sd", coin_id, days)
        return None


# ======================================================================
# Helpers
# ======================================================================


def _get_engine() -> Any | None:
    """Crea engine si hay DATABASE_URL configurada."""
    if not settings.database_url:
        return None
    return create_engine(settings.database_url, pool_pre_ping=True)


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
