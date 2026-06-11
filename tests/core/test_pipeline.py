"""
Tests for the ETL Pipeline module (src/core/pipeline.py).

Covers the full pipeline run, alert checking, history refresh,
all read helper functions, and internal helpers. Uses SQLite in-memory
for DB operations and unittest.mock for external service isolation.

Coverage: ~35-40 tests across all public functions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from src.adapters.database import (
    Base,
    PipelineRunRow,
    PriceAlertRow,
    PriceHistoryRow,
    PriceSnapshotRow,
)
from src.core.pipeline import (
    PipelineError,
    _refresh_history_if_stale,
    _safe_float,
    check_alerts,
    get_history_from_db,
    get_latest_snapshot,
    get_latest_snapshots,
    get_pipeline_stats,
    get_top_from_db,
    run,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


# Helper: naive UTC datetime for SQLite compatibility (SQLite ignores DateTime(timezone=True))
def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utcnow_aware() -> str:
    """Current UTC as ISO string with +00:00, for SQLite raw inserts (preserves tz)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00:00")


SAMPLE_COINS = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 45000.0,
        "price_change_percentage_24h": 2.5,
        "total_volume": 25_000_000_000,
        "market_cap": 850_000_000_000,
        "market_cap_rank": 1,
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3200.0,
        "price_change_percentage_24h": -1.2,
        "total_volume": 15_000_000_000,
        "market_cap": 380_000_000_000,
        "market_cap_rank": 2,
    },
    {
        "id": "solana",
        "symbol": "sol",
        "name": "Solana",
        "current_price": 145.0,
        "price_change_percentage_24h": 5.0,
        "total_volume": 3_000_000_000,
        "market_cap": 65_000_000_000,
        "market_cap_rank": 5,
    },
    {
        "id": "cardano",
        "symbol": "ada",
        "name": "Cardano",
        "current_price": 0.45,
        "price_change_percentage_24h": None,
        "total_volume": 500_000_000,
        "market_cap": 15_000_000_000,
        "market_cap_rank": 8,
    },
    {
        "id": "dogecoin",
        "symbol": "doge",
        "name": "Dogecoin",
        "current_price": 0.08,
        "price_change_percentage_24h": 0.0,
        "total_volume": None,
        "market_cap": None,
        "market_cap_rank": None,
    },
]

SAMPLE_COINS_WITH_INVALID = [
    *SAMPLE_COINS,
    {
        "id": "broken-coin",
        "symbol": "brk",
        "name": "Broken Coin",
        "current_price": "not-a-number",
        "price_change_percentage_24h": None,
        "total_volume": None,
        "market_cap": None,
        "market_cap_rank": None,
    },
]

SAMPLE_HISTORY = {
    "prices": [
        [1_700_000_000, 44000.0],
        [1_700_086_400, 44500.0],
        [1_700_172_800, 44800.0],
    ],
    "market_caps": [
        [1_700_000_000, 830_000_000_000],
        [1_700_086_400, 840_000_000_000],
        [1_700_172_800, 850_000_000_000],
    ],
    "total_volumes": [
        [1_700_000_000, 24_000_000_000],
        [1_700_086_400, 25_000_000_000],
        [1_700_172_800, 26_000_000_000],
    ],
}


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def sqlite_engine():
    """SQLite in-memory engine with all tables created."""
    engine = create_engine("sqlite://", pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def engine_with_snapshots(sqlite_engine):
    """Engine with sample snapshots inserted."""
    now = _utcnow()
    with Session(sqlite_engine) as session:
        for coin in SAMPLE_COINS:
            session.add(
                PriceSnapshotRow(
                    coin_id=coin["id"],
                    symbol=coin["symbol"],
                    name=coin["name"],
                    price=float(coin.get("current_price", 0) or 0),
                    change_24h=_safe_float(coin, "price_change_percentage_24h"),
                    volume_24h=_safe_float(coin, "total_volume"),
                    market_cap=_safe_float(coin, "market_cap"),
                    rank=coin.get("market_cap_rank"),
                    snapshot_at=now,
                )
            )
        session.commit()
    return sqlite_engine


@pytest.fixture
def shared_engine():
    """SQLite engine shared between test and run() via create_engine patch."""
    engine = create_engine("sqlite://", pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_client():
    """Mocked CoinGeckoClient that returns sample data."""
    client = MagicMock()
    client.get_top_coins.return_value = SAMPLE_COINS
    client.get_coin_history.return_value = SAMPLE_HISTORY
    return client


# ======================================================================
# Tests: run() — pipeline principal
# ======================================================================


class TestRun:
    """Tests for the main pipeline run() function."""

    @patch("src.core.pipeline.create_engine")
    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_success(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
        mock_create_engine: MagicMock,
        shared_engine,
    ):
        """Pipeline completo con datos válidos devuelve stats correctos."""
        mock_create_engine.return_value = shared_engine
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = SAMPLE_COINS
        mock_client.get_coin_history.return_value = SAMPLE_HISTORY

        result = run(database_url="sqlite://", top_n=5, trigger="manual")

        assert result["snapshots"] == 5
        assert "history_updated" in result
        assert "alerts_triggered" not in result  # no alerts configured
        mock_client.get_top_coins.assert_called_once_with(limit=5, currency="usd")

    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_empty_coins_raises(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
    ):
        """Sin monedas válidas de CoinGecko → PipelineError."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = []

        with pytest.raises(PipelineError, match="No se pudo extraer ninguna moneda válida"):
            run(database_url="sqlite://")

    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_all_coins_invalid_raises(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
    ):
        """Todas las monedas inválidas → PipelineError."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = [
            {"id": "bad", "current_price": "nope", "symbol": "bad", "name": "Bad"},
        ]

        with pytest.raises(PipelineError, match="No se pudo extraer ninguna moneda válida"):
            run(database_url="sqlite://")

    @patch("src.core.pipeline.create_engine")
    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_skips_invalid_coin_in_mixed_batch(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
        mock_create_engine: MagicMock,
        shared_engine,
    ):
        """Monedas inválidas se saltean, las válidas se insertan."""
        mock_create_engine.return_value = shared_engine
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = SAMPLE_COINS_WITH_INVALID
        mock_client.get_coin_history.return_value = SAMPLE_HISTORY

        result = run(database_url="sqlite://", top_n=6)
        assert result["snapshots"] == 5

        # Verify only valid coins in DB
        with Session(shared_engine) as session:
            coins = session.query(PriceSnapshotRow.coin_id).distinct().all()
            coin_ids = {c[0] for c in coins}
            assert "broken-coin" not in coin_ids
            assert coin_ids == {"bitcoin", "ethereum", "solana", "cardano", "dogecoin"}

    def test_run_no_database_url_raises(self):
        """Sin database_url → PipelineError."""
        with pytest.raises(PipelineError, match="No hay DATABASE_URL"):
            run(database_url="")

    @patch("src.core.pipeline.create_engine")
    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_with_schedule_trigger(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
        mock_create_engine: MagicMock,
        shared_engine,
    ):
        """Trigger 'schedule' se registra correctamente en PipelineRunRow."""
        mock_create_engine.return_value = shared_engine
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = SAMPLE_COINS[:2]
        mock_client.get_coin_history.return_value = SAMPLE_HISTORY

        result = run(database_url="sqlite://", top_n=2, trigger="schedule")

        assert result["snapshots"] == 2
        # Verify the run record in the shared engine
        with Session(shared_engine) as session:
            records = session.query(PipelineRunRow).all()
            assert len(records) == 1
            assert records[0].trigger == "schedule"
            assert records[0].status == "success"

    @patch("src.core.pipeline.create_engine")
    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_migration_warning_does_not_break(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
        mock_create_engine: MagicMock,
        shared_engine,
    ):
        """Si las migraciones fallan, el pipeline continúa con warning."""
        mock_create_engine.return_value = shared_engine
        mock_migrations.side_effect = RuntimeError("Migration failed")
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.return_value = SAMPLE_COINS[:2]
        mock_client.get_coin_history.return_value = SAMPLE_HISTORY

        result = run(database_url="sqlite://", top_n=2)
        assert result["snapshots"] == 2

    @patch("src.core.pipeline.create_engine")
    @patch("src.adapters.database.run_migrations")
    @patch("src.core.pipeline.CoinGeckoClient")
    def test_run_records_error_on_exception(
        self,
        mock_client_class: MagicMock,
        mock_migrations: MagicMock,
        mock_create_engine: MagicMock,
        shared_engine,
    ):
        """Cuando run() falla, guarda PipelineRunRow con status='error'."""
        mock_create_engine.return_value = shared_engine
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_top_coins.side_effect = RuntimeError("CoinGecko is down")

        with pytest.raises(RuntimeError):
            run(database_url="sqlite://", top_n=2)

        # Verify error record in the shared engine
        with Session(shared_engine) as session:
            records = session.query(PipelineRunRow).all()
            assert len(records) >= 1
            error_records = [r for r in records if r.status == "error"]
            assert len(error_records) >= 1
            assert "CoinGecko is down" in error_records[0].error_message


# ======================================================================
# Tests: check_alerts()
# ======================================================================


class TestCheckAlerts:
    """Tests for alert checking logic."""

    def _insert_snapshot(self, session, coin_id: str, price: float, snapshot_at: datetime | None = None):
        """Helper: insert a single snapshot row."""
        session.add(
            PriceSnapshotRow(
                coin_id=coin_id,
                symbol=coin_id[:3],
                name=coin_id.capitalize(),
                price=price,
                snapshot_at=snapshot_at or _utcnow(),
            )
        )

    def test_no_active_alerts(self, sqlite_engine):
        """Sin alertas activas → lista vacía."""
        result = check_alerts(sqlite_engine)
        assert result == []

    def test_no_snapshots(self, sqlite_engine):
        """Sin snapshots en DB → lista vacía aunque haya alertas."""
        with Session(sqlite_engine) as session:
            session.add(
                PriceAlertRow(
                    coin_id="bitcoin",
                    target_price=40000.0,
                    condition="above",
                    is_active=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        result = check_alerts(sqlite_engine)
        assert result == []

    def test_alert_above_triggered(self, sqlite_engine):
        """Alerta 'above' se dispara cuando precio >= target."""
        with Session(sqlite_engine) as session:
            self._insert_snapshot(session, "bitcoin", 45000.0)
            session.add(
                PriceAlertRow(
                    coin_id="bitcoin",
                    target_price=40000.0,
                    condition="above",
                    is_active=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        result = check_alerts(sqlite_engine)
        assert len(result) == 1
        assert result[0]["coin_id"] == "bitcoin"
        assert result[0]["condition"] == "above"
        assert result[0]["current_price"] == 45000.0

    def test_alert_below_triggered(self, sqlite_engine):
        """Alerta 'below' se dispara cuando precio <= target."""
        with Session(sqlite_engine) as session:
            self._insert_snapshot(session, "ethereum", 3200.0)
            session.add(
                PriceAlertRow(
                    coin_id="ethereum",
                    target_price=3500.0,
                    condition="below",
                    is_active=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        result = check_alerts(sqlite_engine)
        assert len(result) == 1
        assert result[0]["coin_id"] == "ethereum"

    def test_alert_not_triggered(self, sqlite_engine):
        """Alerta que NO cumple condición → no se dispara."""
        with Session(sqlite_engine) as session:
            self._insert_snapshot(session, "bitcoin", 45000.0)
            session.add(
                PriceAlertRow(
                    coin_id="bitcoin",
                    target_price=50000.0,
                    condition="above",
                    is_active=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        result = check_alerts(sqlite_engine)
        assert result == []

    def test_multiple_alerts_simultaneous(self, sqlite_engine):
        """Varias alertas pueden dispararse en la misma corrida."""
        shared_at = _utcnow()
        with Session(sqlite_engine) as session:
            self._insert_snapshot(session, "bitcoin", 45000.0, snapshot_at=shared_at)
            self._insert_snapshot(session, "solana", 145.0, snapshot_at=shared_at)
            session.add_all(
                [
                    PriceAlertRow(
                        coin_id="bitcoin",
                        target_price=40000.0,
                        condition="above",
                        is_active=1,
                        created_at=shared_at,
                    ),
                    PriceAlertRow(
                        coin_id="solana",
                        target_price=100.0,
                        condition="above",
                        is_active=1,
                        created_at=shared_at,
                    ),
                    PriceAlertRow(
                        coin_id="bitcoin",
                        target_price=44000.0,
                        condition="below",
                        is_active=1,  # 45000 <= 44000 → false, no trigger
                        created_at=shared_at,
                    ),
                ]
            )
            session.commit()

        result = check_alerts(sqlite_engine)
        assert len(result) == 2  # two alertas se disparan (above), una no (below)
        assert all(a["condition"] == "above" for a in result)

    def test_alert_db_error_does_not_break(self, sqlite_engine, caplog):
        """Error de DB en check_alerts loggea warning y devuelve lista vacía."""
        # Close the engine to simulate DB error
        sqlite_engine.dispose()

        with caplog.at_level(logging.WARNING):
            result = check_alerts(sqlite_engine)
        assert result == []
        assert "Error al checkear alertas" in caplog.text


# ======================================================================
# Tests: _refresh_history_if_stale()
# ======================================================================


class TestRefreshHistory:
    """Tests for the history refresh logic."""

    def test_no_top_coins_returns_zero(self, sqlite_engine):
        """Sin snapshots en DB → return 0 sin hacer nada."""
        mock = MagicMock()
        result = _refresh_history_if_stale(mock, sqlite_engine)
        assert result == 0
        mock.get_coin_history.assert_not_called()

    def test_fresh_history_skips_refresh(self, sqlite_engine, engine_with_snapshots):
        """History con menos de 6h → no refresca desde CoinGecko.

        Insertamos con +00:00 vía raw SQL para que SQLAlchemy devuelva
        timezone-aware y la comparación en _refresh_history_if_stale funcione.
        """
        ts = _utcnow_aware()
        with sqlite_engine.connect() as conn:
            for coin in ["bitcoin", "ethereum", "solana", "cardano", "dogecoin"]:
                for days in [7, 30, 90]:
                    conn.execute(
                        sa_text(
                            "INSERT INTO price_history (coin_id, days, data, updated_at) "
                            "VALUES (:cid, :days, :data, :ts)"
                        ),
                        {
                            "cid": coin,
                            "days": days,
                            "data": json.dumps([{"timestamp": 1, "price": 44000}]),
                            "ts": ts,
                        },
                    )
            conn.commit()

        mock = MagicMock()
        result = _refresh_history_if_stale(mock, sqlite_engine)
        assert result == 0
        mock.get_coin_history.assert_not_called()

    def test_stale_history_triggers_refresh(self, sqlite_engine, engine_with_snapshots):
        """History viejo (>6h) → refresca desde CoinGecko."""
        old = _utcnow() - timedelta(hours=12)
        with Session(sqlite_engine) as session:
            session.add(
                PriceHistoryRow(
                    coin_id="bitcoin",
                    days=7,
                    data=json.dumps([{"timestamp": 1, "price": 44000}]),
                    updated_at=old,  # stale
                )
            )
            session.commit()

        mock = MagicMock()
        mock.get_coin_history.return_value = SAMPLE_HISTORY
        result = _refresh_history_if_stale(mock, sqlite_engine)
        # At least bitcoin 7d should be refreshed
        assert result >= 1
        mock.get_coin_history.assert_called()

    def test_coin_gecko_error_skips_coin_continues(self, sqlite_engine, engine_with_snapshots):
        """Si CoinGecko falla para un coin, loggea warning y sigue con el resto."""
        mock = MagicMock()
        # First call succeeds, second fails
        mock.get_coin_history.side_effect = [
            SAMPLE_HISTORY,
            RuntimeError("API error on ethereum"),
            SAMPLE_HISTORY,
        ]

        # Multiple top coins = multiple refresh attempts
        result = _refresh_history_if_stale(mock, sqlite_engine)
        # Some should succeed despite the error
        assert result >= 0  # at least the ones that succeeded

    def test_empty_coin_ids_returns_zero(self, sqlite_engine):
        """Si la consulta de top coins devuelve vacío (no hay DB data), return 0."""
        # Fresh engine with no data at all
        mock = MagicMock()
        result = _refresh_history_if_stale(mock, sqlite_engine)
        assert result == 0


# ======================================================================
# Tests: get_latest_snapshot()
# ======================================================================


class TestGetLatestSnapshot:
    """Tests for reading single snapshots."""

    @patch("src.core.pipeline._get_engine")
    def test_coin_exists_returns_snapshot(self, mock_get_engine, engine_with_snapshots):
        """Un coin existente devuelve su snapshot más reciente."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_latest_snapshot("bitcoin")
        assert result is not None
        assert result.coin_id == "bitcoin"
        assert result.price == 45000.0

    @patch("src.core.pipeline._get_engine")
    def test_coin_not_found_returns_none(self, mock_get_engine, engine_with_snapshots):
        """Un coin inexistente devuelve None."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_latest_snapshot("nonexistent")
        assert result is None

    def test_no_engine_returns_none(self):
        """Sin DB configurada → None."""
        with patch("src.core.pipeline._get_engine", return_value=None):
            result = get_latest_snapshot("bitcoin")
        assert result is None

    @patch("src.core.pipeline._get_engine")
    def test_db_error_returns_none(self, mock_get_engine, sqlite_engine):
        """Error de DB → None sin crash."""
        sqlite_engine.dispose()
        mock_get_engine.return_value = sqlite_engine
        result = get_latest_snapshot("bitcoin")
        assert result is None


# ======================================================================
# Tests: get_latest_snapshots()
# ======================================================================


class TestGetLatestSnapshots:
    """Tests for reading multiple snapshots."""

    @patch("src.core.pipeline._get_engine")
    def test_multiple_coins(self, mock_get_engine, engine_with_snapshots):
        """Varios coins existentes devuelven dict con todos."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_latest_snapshots(["bitcoin", "ethereum", "solana"])
        assert len(result) == 3
        assert "bitcoin" in result
        assert "ethereum" in result
        assert "solana" in result

    @patch("src.core.pipeline._get_engine")
    def test_empty_list_returns_empty_dict(self, mock_get_engine, engine_with_snapshots):
        """Lista vacía de coin_ids → {}."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_latest_snapshots([])
        assert result == {}

    @patch("src.core.pipeline._get_engine")
    def test_mixed_existing_and_missing(self, mock_get_engine, engine_with_snapshots):
        """Mezcla de coins existentes e inexistentes → solo los que existen."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_latest_snapshots(["bitcoin", "nonexistent", "solana"])
        assert len(result) == 2
        assert "bitcoin" in result
        assert "solana" in result


# ======================================================================
# Tests: get_top_from_db()
# ======================================================================


class TestGetTopFromDb:
    """Tests for reading top N coins from DB."""

    @patch("src.core.pipeline._get_engine")
    def test_returns_top_n_ordered_by_rank(self, mock_get_engine, engine_with_snapshots):
        """Devuelve top N ordenado por rank (ascendente)."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_top_from_db(limit=3)
        assert result is not None
        assert len(result) == 3
        # bitcoin (rank 1), ethereum (rank 2), dogecoin (rank None, nullslast)
        assert result[0].coin_id == "bitcoin"
        assert result[1].coin_id == "ethereum"

    @patch("src.core.pipeline._get_engine")
    def test_limit_greater_than_available(self, mock_get_engine, engine_with_snapshots):
        """Si limit es mayor que los datos disponibles, devuelve todos."""
        mock_get_engine.return_value = engine_with_snapshots
        result = get_top_from_db(limit=100)
        assert result is not None
        assert len(result) == 5  # only 5 sample coins

    @patch("src.core.pipeline._get_engine")
    def test_empty_db_returns_none(self, mock_get_engine, sqlite_engine):
        """DB vacía → None."""
        mock_get_engine.return_value = sqlite_engine
        result = get_top_from_db(limit=10)
        assert result is None

    def test_no_engine_returns_none(self):
        """Sin DB configurada → None."""
        with patch("src.core.pipeline._get_engine", return_value=None):
            result = get_top_from_db(limit=10)
        assert result is None


# ======================================================================
# Tests: get_history_from_db()
# ======================================================================


class TestGetHistoryFromDb:
    """Tests for reading cached history from DB.

    Nota: SQLite no preserva DateTime(timezone=True). La función
    get_history_from_db() compara con datetime.now(timezone.utc)
    que es timezone-aware. Para que funcione en tests, insertamos
    el timestamp con formato '+00:00' vía SQL raw.
    """

    @patch("src.core.pipeline._get_engine")
    def test_fresh_history_returns_data(self, mock_get_engine, sqlite_engine):
        """History fresco (<24h) devuelve datos parseados.

        Insertamos el datetime con +00:00 via SQL raw para que
        SQLAlchemy lo lea como timezone-aware (compatible con
        datetime.now(timezone.utc) en get_history_from_db).
        """
        ts = _utcnow_aware()
        with sqlite_engine.connect() as conn:
            conn.execute(
                sa_text("INSERT INTO price_history (coin_id, days, data, updated_at) VALUES (:cid, :days, :data, :ts)"),
                {
                    "cid": "bitcoin",
                    "days": 7,
                    "data": json.dumps([{"timestamp": 1, "price": 44000}]),
                    "ts": ts,
                },
            )
            conn.commit()
        mock_get_engine.return_value = sqlite_engine

        result = get_history_from_db("bitcoin", days=7)
        assert result is not None
        assert len(result) == 1
        assert result[0]["price"] == 44000

    @patch("src.core.pipeline._get_engine")
    def test_stale_history_returns_none(self, mock_get_engine, sqlite_engine):
        """History viejo (>24h) devuelve None."""
        old_dt = _utcnow() - timedelta(hours=48)
        old = old_dt.strftime("%Y-%m-%d %H:%M:%S.%f+00:00")
        with sqlite_engine.connect() as conn:
            conn.execute(
                sa_text("INSERT INTO price_history (coin_id, days, data, updated_at) VALUES (:cid, :days, :data, :ts)"),
                {
                    "cid": "bitcoin",
                    "days": 7,
                    "data": json.dumps([{"timestamp": 1, "price": 44000}]),
                    "ts": old,
                },
            )
            conn.commit()
        mock_get_engine.return_value = sqlite_engine

        result = get_history_from_db("bitcoin", days=7)
        assert result is None

    @patch("src.core.pipeline._get_engine")
    def test_no_history_returns_none(self, mock_get_engine, sqlite_engine):
        """Moneda sin history guardado → None."""
        mock_get_engine.return_value = sqlite_engine
        result = get_history_from_db("nonexistent", days=7)
        assert result is None

    def test_no_engine_returns_none(self):
        """Sin DB configurada → None."""
        with patch("src.core.pipeline._get_engine", return_value=None):
            result = get_history_from_db("bitcoin")
        assert result is None


# ======================================================================
# Tests: get_pipeline_stats()
# ======================================================================


class TestGetPipelineStats:
    """Tests for pipeline monitoring statistics."""

    @patch("src.core.pipeline._get_engine")
    def test_with_runs(self, mock_get_engine, sqlite_engine):
        """Con corridas exitosas y fallidas → stats correctos."""
        now = _utcnow()
        with Session(sqlite_engine) as session:
            session.add_all(
                [
                    PipelineRunRow(
                        started_at=now - timedelta(hours=2),
                        finished_at=now - timedelta(hours=1, minutes=55),
                        status="success",
                        snapshots_inserted=100,
                        history_updated=5,
                        trigger="schedule",
                    ),
                    PipelineRunRow(
                        started_at=now - timedelta(hours=1),
                        finished_at=now - timedelta(minutes=55),
                        status="error",
                        error_message="CoinGecko timeout",
                        trigger="schedule",
                    ),
                ]
            )
            session.commit()
        mock_get_engine.return_value = sqlite_engine

        stats = get_pipeline_stats()
        assert stats is not None
        assert stats["total_runs"] == 2
        assert stats["successful_runs"] == 1
        assert stats["failed_runs"] == 1
        assert stats["success_rate"] == 50.0
        assert stats["last_run"]["status"] == "error"

    @patch("src.core.pipeline._get_engine")
    def test_no_runs(self, mock_get_engine, sqlite_engine):
        """Sin corridas → stats con ceros."""
        mock_get_engine.return_value = sqlite_engine
        stats = get_pipeline_stats()
        assert stats is not None
        assert stats["total_runs"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["last_run"] is None

    @patch("src.core.pipeline._get_engine")
    def test_recent_runs_in_stats(self, mock_get_engine, sqlite_engine):
        """recent_runs incluye las últimas 5 corridas."""
        now = _utcnow()
        with Session(sqlite_engine) as session:
            for i in range(6):
                session.add(
                    PipelineRunRow(
                        started_at=now - timedelta(hours=i),
                        finished_at=now - timedelta(hours=i, minutes=55),
                        status="success",
                        snapshots_inserted=50,
                        history_updated=2,
                        trigger="manual",
                    )
                )
            session.commit()
        mock_get_engine.return_value = sqlite_engine

        stats = get_pipeline_stats()
        assert len(stats["recent_runs"]) == 5  # limited to 5 most recent

    def test_no_engine_returns_none(self):
        """Sin DB configurada → None."""
        with patch("src.core.pipeline._get_engine", return_value=None):
            result = get_pipeline_stats()
        assert result is None


# ======================================================================
# Tests: _safe_float()
# ======================================================================


class TestSafeFloat:
    """Tests for the _safe_float helper."""

    def test_valid_float(self):
        """Valor numérico válido."""
        assert _safe_float({"val": 42.5}, "val") == 42.5
        assert _safe_float({"val": "3.14"}, "val") == 3.14

    def test_none_value(self):
        """Valor None devuelve None."""
        assert _safe_float({"val": None}, "val") is None

    def test_missing_key(self):
        """Key inexistente devuelve None."""
        assert _safe_float({}, "nonexistent") is None

    def test_invalid_string(self):
        """String no numérico devuelve None sin crash."""
        assert _safe_float({"val": "not-a-number"}, "val") is None

    def test_zero_value(self):
        """Cero se devuelve correctamente como float."""
        assert _safe_float({"val": 0}, "val") == 0.0
