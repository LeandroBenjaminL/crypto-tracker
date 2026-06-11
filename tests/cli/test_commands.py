"""
Tests for CLI commands: alerts, pipeline, formatting, and error handling.

Commands tested here were not covered by test_cli.py.
Uses CliRunner, unittest.mock, and SQLite in-memory where needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.adapters.database import Base, PriceAlertRow
from src.cli.commands import (
    _format_change,
    _format_market_cap,
    _format_price,
    _handle_error,
    cli,
)
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CliRunner for invoking commands."""
    return CliRunner()


@pytest.fixture
def sqlite_engine():
    """SQLite in-memory engine with tables for alert/pipeline tests."""
    engine = create_engine("sqlite://", pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_service() -> MagicMock:
    """Mock PriceService for pipeline commands that delegate to it."""
    return MagicMock()


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """Mock for src.core.pipeline.run and get_pipeline_stats."""
    return MagicMock()


# ======================================================================
# Tests: Alert commands
# ======================================================================


class TestAlertAdd:
    """Tests for `alert add` command."""

    def _mock_settings(self, db_url: str = "sqlite://"):
        """Patch settings with a mock that allows attribute assignment."""
        mock_settings = MagicMock()
        mock_settings.database_url = db_url
        return mock_settings

    def test_add_above(self, runner: CliRunner, sqlite_engine):
        """alert add btc --above 100000 crea alerta en DB."""
        with patch("src.cli.commands.settings", self._mock_settings()):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "add", "btc", "--above", "100000"])

        assert result.exit_code == 0
        assert "Alerta" in result.output
        assert "btc" in result.output
        with Session(sqlite_engine) as session:
            alerts = session.query(PriceAlertRow).all()
            assert len(alerts) == 1
            assert alerts[0].coin_id == "bitcoin"  # resolved via SYMBOL_TO_ID
            assert alerts[0].target_price == 100000.0
            assert alerts[0].condition == "above"

    def test_add_below(self, runner: CliRunner, sqlite_engine):
        """alert add eth --below 1500 crea alerta below."""
        with patch("src.cli.commands.settings", self._mock_settings()):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "add", "eth", "--below", "1500"])

        assert result.exit_code == 0
        assert "Alerta" in result.output
        with Session(sqlite_engine) as session:
            alerts = session.query(PriceAlertRow).all()
            assert len(alerts) == 1
            assert alerts[0].condition == "below"

    def test_add_both_flags_error(self, runner: CliRunner, sqlite_engine):
        """alert add con --above y --below → mensaje de error."""
        with patch("src.cli.commands.settings", self._mock_settings()):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "add", "btc", "--above", "50000", "--below", "30000"])

        assert result.exit_code == 0
        assert "Elegí" in result.output or "no ambos" in result.output

    def test_add_no_flag_error(self, runner: CliRunner, sqlite_engine):
        """alert add sin --above ni --below → mensaje de error."""
        with patch("src.cli.commands.settings", self._mock_settings()):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "add", "btc"])

        assert result.exit_code == 0
        assert "Necesitás" in result.output

    def test_add_no_db(self, runner: CliRunner):
        """alert add sin DATABASE_URL → mensaje de error."""
        with patch("src.cli.commands.settings", self._mock_settings(db_url="")):
            result = runner.invoke(cli, ["alert", "add", "btc", "--above", "50000"])

        assert result.exit_code == 0
        assert "PostgreSQL" in result.output


class TestAlertList:
    """Tests for `alert list` command."""

    def test_list_active(self, runner: CliRunner, sqlite_engine):
        """alert list muestra alertas activas de la DB."""
        with Session(sqlite_engine) as session:
            session.add_all([
                PriceAlertRow(
                    coin_id="bitcoin", target_price=100000.0,
                    condition="above", is_active=1,
                    created_at=datetime.now(timezone.utc),
                ),
                PriceAlertRow(
                    coin_id="ethereum", target_price=1500.0,
                    condition="below", is_active=1,
                    created_at=datetime.now(timezone.utc),
                ),
            ])
            session.commit()

        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "list"])

        assert result.exit_code == 0
        assert "bitcoin" in result.output
        assert "ethereum" in result.output
        assert "Alertas" in result.output or "activas" in result.output

    def test_list_empty(self, runner: CliRunner):
        """alert list sin alertas → mensaje."""
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=engine):
                result = runner.invoke(cli, ["alert", "list"])

        assert result.exit_code == 0
        assert "No tenés" in result.output

    def test_list_no_db(self, runner: CliRunner):
        """alert list sin DB → mensaje."""
        with patch("src.cli.commands.settings", MagicMock(database_url="")):
            result = runner.invoke(cli, ["alert", "list"])

        assert result.exit_code == 0
        assert "PostgreSQL" in result.output


class TestAlertRemove:
    """Tests for `alert remove` command."""

    def test_remove_existing(self, runner: CliRunner, sqlite_engine):
        """alert remove desactiva una alerta existente."""
        with Session(sqlite_engine) as session:
            session.add(
                PriceAlertRow(
                    coin_id="bitcoin", target_price=50000.0,
                    condition="above", is_active=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "remove", "1"])

        assert result.exit_code == 0
        assert "cancelada" in result.output
        with Session(sqlite_engine) as session:
            alert = session.query(PriceAlertRow).first()
            assert alert is not None
            assert alert.is_active == 0

    def test_remove_nonexistent(self, runner: CliRunner, sqlite_engine):
        """alert remove con ID inválido → mensaje."""
        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "remove", "999"])

        assert result.exit_code == 0
        assert "no encontrada" in result.output


class TestAlertTriggered:
    """Tests for `alert triggered` command."""

    def test_triggered_shows_alerts(self, runner: CliRunner, sqlite_engine):
        """alert triggered muestra alertas disparadas."""
        with Session(sqlite_engine) as session:
            session.add(
                PriceAlertRow(
                    coin_id="bitcoin", target_price=100000.0,
                    condition="above", is_active=0,
                    triggered_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=sqlite_engine):
                result = runner.invoke(cli, ["alert", "triggered"])

        assert result.exit_code == 0
        assert "bitcoin" in result.output
        assert "disparada" in result.output or "superó" in result.output

    def test_triggered_empty(self, runner: CliRunner):
        """alert triggered sin alertas disparadas → mensaje."""
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            with patch("sqlalchemy.create_engine", return_value=engine):
                result = runner.invoke(cli, ["alert", "triggered"])

        assert result.exit_code == 0
        assert "No hay" in result.output


# ======================================================================
# Tests: Pipeline commands
# ======================================================================


class TestPipelineGroup:
    """Tests for `pipeline` command group."""

    @patch("src.core.pipeline.run")
    def test_pipeline_invoke_default(self, mock_run, runner: CliRunner):
        """pipeline sin subcomando invoca el pipeline."""
        mock_run.return_value = {"snapshots": 50, "history_updated": 3}
        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            result = runner.invoke(cli, ["pipeline"])

        assert result.exit_code == 0
        assert "Pipeline" in result.output or "completado" in result.output

    @patch("src.core.pipeline.run")
    def test_pipeline_run(self, mock_run, runner: CliRunner):
        """pipeline run --top 50 ejecuta el pipeline."""
        mock_run.return_value = {"snapshots": 50, "history_updated": 3}
        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            result = runner.invoke(cli, ["pipeline", "run", "--top", "50"])

        assert result.exit_code == 0
        assert "Pipeline" in result.output

    def test_pipeline_stats_no_db(self, runner: CliRunner):
        """pipeline stats sin DB → mensaje."""
        with patch("src.cli.commands.settings", MagicMock(database_url="")):
            result = runner.invoke(cli, ["pipeline", "stats"])

        assert result.exit_code == 0
        assert "DATABASE_URL" in result.output

    @patch("src.core.pipeline.get_pipeline_stats")
    def test_pipeline_stats_with_data(self, mock_stats, runner: CliRunner):
        """pipeline stats muestra estadísticas."""
        mock_stats.return_value = {
            "total_runs": 10,
            "successful_runs": 8,
            "failed_runs": 2,
            "success_rate": 80.0,
            "last_run": {
                "status": "success",
                "started_at": "2026-06-11T00:00:00",
                "finished_at": "2026-06-11T00:01:00",
                "snapshots": 100,
                "history": 5,
                "error": None,
                "trigger": "manual",
            },
            "recent_runs": [],
        }

        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            result = runner.invoke(cli, ["pipeline", "stats"])

        assert result.exit_code == 0
        assert "10" in result.output or "80" in result.output

    @patch("src.core.pipeline.get_pipeline_stats")
    def test_pipeline_stats_empty(self, mock_stats, runner: CliRunner):
        """pipeline stats sin ejecuciones → mensaje."""
        mock_stats.return_value = None

        with patch("src.cli.commands.settings", MagicMock(database_url="sqlite://")):
            result = runner.invoke(cli, ["pipeline", "stats"])

        assert result.exit_code == 0
        assert "No hay ejecuciones" in result.output


# ======================================================================
# Tests: Formatting helpers
# ======================================================================


class TestFormatPrice:
    """Tests for _format_price()."""

    def test_high_price(self):
        """Precio >= 1 usa 2 decimales con coma de miles."""
        assert _format_price(45000.0) == "$45,000.00"
        assert _format_price(1.0) == "$1.00"
        assert _format_price(1234567.89) == "$1,234,567.89"

    def test_medium_price(self):
        """Precio entre 0.01 y 1 usa 4 decimales."""
        result = _format_price(0.5)
        assert result == "$0.5000"
        assert _format_price(0.01) == "$0.0100"

    def test_low_price(self):
        """Precio < 0.01 usa 8 decimales."""
        assert _format_price(0.001) == "$0.00100000"
        assert _format_price(0.00005678) == "$0.00005678"


class TestFormatChange:
    """Tests for _format_change()."""

    def test_positive_change(self):
        """Cambio positivo muestra triángulo verde."""
        result = _format_change(2.5)
        assert "▲" in result
        assert "+2.50%" in result

    def test_negative_change(self):
        """Cambio negativo muestra triángulo rojo."""
        result = _format_change(-1.2)
        assert "▼" in result
        assert "-1.20%" in result

    def test_zero_change(self):
        """Cambio cero muestra em dash blanco."""
        result = _format_change(0.0)
        assert "―" in result or "0.00%" in result


class TestFormatMarketCap:
    """Tests for _format_market_cap()."""

    def test_trillions(self):
        """>= 1T muestra en trillones."""
        assert _format_market_cap(2_000_000_000_000) == "$2.00T"

    def test_billions(self):
        """>= 1B muestra en billones."""
        assert _format_market_cap(850_000_000_000) == "$850.00B"

    def test_millions(self):
        """>= 1M muestra en millones."""
        assert _format_market_cap(50_000_000) == "$50.00M"

    def test_small_value(self):
        """< 1M muestra valor sin abreviar."""
        assert _format_market_cap(500_000) == "$500,000"


# ======================================================================
# Tests: Error handler
# ======================================================================


class TestHandleError:
    """Tests for _handle_error() mapping exceptions to output."""

    def test_validation_error(self, runner: CliRunner):
        """ValidationError muestra mensaje de input inválido."""
        with runner.isolated_filesystem():
            _handle_error(ValidationError("symbol", "", "empty"))
        # No exception is the assertion

    def test_coin_not_found(self, runner: CliRunner):
        """CoinNotFoundError muestra mensaje amarillo."""
        with runner.isolated_filesystem():
            _handle_error(CoinNotFoundError("fakecoin"))

    def test_rate_limit(self, runner: CliRunner):
        """RateLimitError muestra mensaje de espera."""
        with runner.isolated_filesystem():
            _handle_error(RateLimitError(retry_after=30))

    def test_network_error(self, runner: CliRunner):
        """NetworkError muestra mensaje de conexión."""
        with runner.isolated_filesystem():
            _handle_error(NetworkError())

    def test_api_error(self, runner: CliRunner):
        """APIError muestra mensaje de error de API."""
        with runner.isolated_filesystem():
            _handle_error(APIError("Server error", status_code=502))

    def test_generic_error(self, runner: CliRunner):
        """Error genérico no mapeado muestra mensaje unexpected."""
        with runner.isolated_filesystem():
            _handle_error(CryptoTrackerError("something weird"))
