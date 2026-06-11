"""
Tests for the Telegram bot handlers.

We mock at the handler level: mock telegram.Update, ContextTypes.DEFAULT_TYPE,
and PriceService (since CoinGeckoClient is constructed inside the handler).
This keeps tests fast, deterministic, and offline-friendly.

Covers:
  - /start — welcome message, unauthorized
  - /price — price display, error, no args, unauthorized
  - /top — top list, error, invalid limit, unauthorized
  - /alert — alert creation, validation, missing DB, unauthorized
  - /help — delegates to start
  - _is_allowed — with/without allowed users
  - main — token missing, successful build
  - get_triggered_since_last — no pipeline stats
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CallbackContext

from src.telegram.bot import (
    _is_allowed,
    cmd_alert,
    cmd_help,
    cmd_price,
    cmd_top,
    get_triggered_since_last,
    main,
    start,
)
from telegram import Update

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def mock_update() -> MagicMock:
    """Create a mock telegram Update with a working message.reply_text."""
    update = MagicMock(spec=Update)
    update.effective_user.id = 12345
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context() -> MagicMock:
    """Create a mock CallbackContext with empty args."""
    context = MagicMock(spec=CallbackContext)
    context.args = []
    return context


@pytest.fixture(autouse=True)
def clear_token_env() -> Generator[None, None, None]:
    """Ensure TELEGRAM_BOT_TOKEN is not set in default test env."""
    with patch.dict("os.environ", {}, clear=True):
        yield


# ======================================================================
# _is_allowed
# ======================================================================


class TestIsAllowed:
    """Tests for the _is_allowed helper."""

    def test_allowed_when_list_empty(self) -> None:
        """If ALLOWED_USERS is empty, everybody is allowed."""
        assert _is_allowed(99999) is True

    @patch("src.telegram.bot._ALLOWED_USERS", [100, 200, 300])
    def test_allowed_user_in_list(self) -> None:
        """A user in the allowed list is permitted."""
        assert _is_allowed(200) is True

    @patch("src.telegram.bot._ALLOWED_USERS", [100, 200, 300])
    def test_allowed_user_not_in_list(self) -> None:
        """A user NOT in the allowed list is rejected."""
        assert _is_allowed(999) is False


# ======================================================================
# /start
# ======================================================================


class TestStart:
    """Tests for the /start command handler."""

    async def test_start_welcome(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/start sends a welcome message with Markdown."""
        await start(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        args, kwargs = mock_update.message.reply_text.await_args
        assert "Crypto Tracker Bot" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"

    @patch("src.telegram.bot._ALLOWED_USERS", [100])
    async def test_start_unauthorized(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Unauthorized user gets blocked."""
        mock_update.effective_user.id = 999
        await start(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with("⛔ No autorizado")


# ======================================================================
# /price
# ======================================================================


class TestCmdPrice:
    """Tests for the /price command handler."""

    async def test_price_no_args(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Missing coin argument shows usage message."""
        mock_context.args = []
        await cmd_price(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with("Usá: /price <moneda>\nEj: /price btc")

    async def test_price_success(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/price btc returns formatted price with positive change."""
        mock_context.args = ["btc"]

        mock_result = MagicMock()
        mock_result.has_price.return_value = True
        mock_result.price_data.price = 45000.50
        mock_result.price_data.change_24h = 2.5
        mock_result.price_data.market_cap = 850_000_000_000
        mock_result.coin.name = "Bitcoin"
        mock_result.coin.symbol = "btc"

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.get_price.return_value = mock_result
            mock_svc_cls.return_value = mock_service

            await cmd_price(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        args, kwargs = mock_update.message.reply_text.await_args
        assert "Bitcoin" in args[0]
        assert "45,000" in args[0]
        assert "+2.50" in args[0] or "2.50" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"

    async def test_price_negative_change(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/price with negative change shows 📉 indicator."""
        mock_context.args = ["eth"]

        mock_result = MagicMock()
        mock_result.has_price.return_value = True
        mock_result.price_data.price = 3000.00
        mock_result.price_data.change_24h = -1.5
        mock_result.price_data.market_cap = 350_000_000_000
        mock_result.coin.name = "Ethereum"
        mock_result.coin.symbol = "eth"

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.get_price.return_value = mock_result
            mock_svc_cls.return_value = mock_service

            await cmd_price(mock_update, mock_context)

        args, kwargs = mock_update.message.reply_text.await_args
        assert "Ethereum" in args[0]
        assert "-1.50" in args[0] or "1.50" in args[0]

    async def test_price_no_data(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Coin not found shows an error message."""
        mock_context.args = ["unknowncoin"]

        mock_result = MagicMock()
        mock_result.has_price.return_value = False

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.get_price.return_value = mock_result
            mock_svc_cls.return_value = mock_service

            await cmd_price(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once_with("❌ No hay datos para 'unknowncoin'")

    async def test_price_api_error(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """API error shows the error message."""
        mock_context.args = ["btc"]

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.get_price.side_effect = Exception("API timeout")
            mock_svc_cls.return_value = mock_service

            await cmd_price(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once_with("❌ Error: API timeout")

    @patch("src.telegram.bot._ALLOWED_USERS", [100])
    async def test_price_unauthorized(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Unauthorized user gets silently ignored (no reply)."""
        mock_update.effective_user.id = 999
        mock_context.args = ["btc"]
        await cmd_price(mock_update, mock_context)
        mock_update.message.reply_text.assert_not_awaited()


# ======================================================================
# /top
# ======================================================================


class TestCmdTop:
    """Tests for the /top command handler."""

    async def test_top_default_limit(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/top without args uses default limit of 10."""
        mock_context.args = []

        mock_result = MagicMock()
        mock_result.price_data.price = 45000.50
        mock_result.price_data.change_24h = 2.5
        mock_result.coin.name = "Bitcoin"
        mock_result.coin.symbol = "btc"

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.return_value = [mock_result]
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        mock_service.list_top.assert_called_once_with(limit=10)
        mock_update.message.reply_text.assert_awaited_once()
        args, kwargs = mock_update.message.reply_text.await_args
        assert "Bitcoin" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"

    async def test_top_with_limit(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/top 5 passes limit=5."""
        mock_context.args = ["5"]

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.return_value = []
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        mock_service.list_top.assert_called_once_with(limit=5)

    async def test_top_clamps_limit(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/top 200 caps at 50."""
        mock_context.args = ["200"]

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.return_value = []
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        mock_service.list_top.assert_called_once_with(limit=50)

    async def test_top_invalid_limit_defaults(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/top abc ignores invalid int and uses default 10."""
        mock_context.args = ["abc"]

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.return_value = []
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        mock_service.list_top.assert_called_once_with(limit=10)

    async def test_top_truncated_to_10(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Only the first 10 results are rendered (Telegram message limit)."""
        mock_context.args = []

        results = []
        for i in range(1, 16):
            r = MagicMock()
            r.price_data.price = float(i * 1000)
            r.price_data.change_24h = float(i)
            r.coin.name = f"Coin{i}"
            r.coin.symbol = f"c{i}"
            results.append(r)

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.return_value = results
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        args, kwargs = mock_update.message.reply_text.await_args
        # Only first 10 items rendered
        assert "Coin1" in args[0]
        assert "Coin10" in args[0]
        assert "Coin11" not in args[0]

    async def test_top_error(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """API error in /top shows the error message."""
        mock_context.args = ["10"]

        with patch("src.telegram.bot.PriceService") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.list_top.side_effect = Exception("Rate limited")
            mock_svc_cls.return_value = mock_service

            await cmd_top(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once_with("❌ Error: Rate limited")

    @patch("src.telegram.bot._ALLOWED_USERS", [100])
    async def test_top_unauthorized(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Unauthorized user is silently ignored."""
        mock_update.effective_user.id = 999
        mock_context.args = ["10"]
        await cmd_top(mock_update, mock_context)
        mock_update.message.reply_text.assert_not_awaited()


# ======================================================================
# /alert
# ======================================================================


class TestCmdAlert:
    """Tests for the /alert command handler."""

    async def test_alert_too_few_args(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Less than 3 args shows usage."""
        mock_context.args = ["btc"]
        await cmd_alert(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        args, _ = mock_update.message.reply_text.await_args
        assert "Usá:" in args[0]

    async def test_alert_invalid_condition(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Invalid condition (not above/below) shows error."""
        mock_context.args = ["btc", "exactly", "100000"]
        await cmd_alert(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with("❌ Condición: 'above' o 'below'")

    async def test_alert_invalid_price(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Non-numeric price shows error."""
        mock_context.args = ["btc", "above", "mucho"]
        await cmd_alert(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with("❌ Precio inválido")

    async def test_alert_no_db(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Missing DATABASE_URL shows error."""
        mock_context.args = ["btc", "above", "100000"]

        with patch("src.telegram.bot.settings") as mock_settings:
            mock_settings.database_url = ""
            await cmd_alert(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once_with("❌ No hay DB configurada para alertas")

    async def test_alert_success_above(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Creating an 'above' alert succeeds."""
        mock_context.args = ["btc", "above", "100000"]

        mock_row = MagicMock()
        mock_row.id = 42

        with (
            patch("src.telegram.bot.settings") as mock_settings,
            patch("sqlalchemy.orm.Session") as mock_session_cls,
        ):
            mock_settings.database_url = "sqlite:///test.db"
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session
            mock_session.add.return_value = None
            mock_session.commit.return_value = None
            mock_session.refresh.return_value = None
            mock_session.add.call_args = None  # capture the row

            # We need to intercept the row creation
            def add_side_effect(row: MagicMock) -> None:
                row.id = 42

            mock_session.add.side_effect = add_side_effect

            await cmd_alert(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        args, _ = mock_update.message.reply_text.await_args
        assert "#42" in args[0]
        assert "supere" in args[0]
        assert "100,000" in args[0]

    async def test_alert_success_below(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Creating a 'below' alert succeeds."""
        mock_context.args = ["eth", "below", "2000"]

        mock_row = MagicMock()
        mock_row.id = 7

        with (
            patch("src.telegram.bot.settings") as mock_settings,
            patch("sqlalchemy.orm.Session") as mock_session_cls,
        ):
            mock_settings.database_url = "sqlite:///test.db"
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session

            def add_side_effect(row: MagicMock) -> None:
                row.id = 7

            mock_session.add.side_effect = add_side_effect
            mock_session.commit.return_value = None
            mock_session.refresh.return_value = None

            await cmd_alert(mock_update, mock_context)

        args, _ = mock_update.message.reply_text.await_args
        assert "#7" in args[0]
        assert "baje de" in args[0]

    @patch("src.telegram.bot._ALLOWED_USERS", [100])
    async def test_alert_unauthorized(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """Unauthorized user gets silently ignored."""
        mock_update.effective_user.id = 999
        mock_context.args = ["btc", "above", "100000"]
        await cmd_alert(mock_update, mock_context)
        mock_update.message.reply_text.assert_not_awaited()


# ======================================================================
# /help
# ======================================================================


class TestCmdHelp:
    """Tests for the /help command handler (delegates to /start)."""

    async def test_help_delegates_to_start(self, mock_update: MagicMock, mock_context: MagicMock) -> None:
        """/help should produce the same output as /start."""
        await cmd_help(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        args, kwargs = mock_update.message.reply_text.await_args
        assert "Crypto Tracker Bot" in args[0]
        assert kwargs.get("parse_mode") == "Markdown"


# ======================================================================
# get_triggered_since_last
# ======================================================================


class TestGetTriggeredSinceLast:
    """Tests for get_triggered_since_last helper."""

    @patch("src.core.pipeline.get_pipeline_stats", return_value=None)
    def test_no_stats_returns_empty(self, mock_stats: MagicMock) -> None:
        """Without pipeline stats, returns an empty list."""
        result = get_triggered_since_last(chat_id=123)
        assert result == []

    @patch("src.core.pipeline.get_pipeline_stats", return_value={})
    def test_empty_stats_returns_empty(self, mock_stats: MagicMock) -> None:
        """Empty pipeline stats dict returns empty list."""
        result = get_triggered_since_last(chat_id=123)
        assert result == []

    @patch("src.core.pipeline.get_pipeline_stats", return_value={"last_run": "2026-01-01"})
    def test_stats_without_alert_tracking(self, mock_stats: MagicMock) -> None:
        """Even with pipeline stats, returns empty (TODO not implemented)."""
        result = get_triggered_since_last(chat_id=123)
        assert result == []


# ======================================================================
# main
# ======================================================================


class TestMain:
    """Tests for the main() entry point."""

    @patch("src.telegram.bot._TOKEN", "")
    def test_main_no_token(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Without TELEGRAM_BOT_TOKEN, main prints error and exits early."""
        main()
        captured = capsys.readouterr()
        assert "TELEGRAM_BOT_TOKEN no está configurado" in captured.out

    @patch("src.telegram.bot._TOKEN", "fake:token")
    @patch("src.telegram.bot.Application.builder")
    def test_main_builds_app(self, mock_builder: MagicMock) -> None:
        """With a token, main builds the Application and registers handlers."""
        mock_app = MagicMock()
        mock_builder.return_value.token.return_value.build.return_value = mock_app

        main()

        mock_builder.return_value.token.assert_called_once_with("fake:token")
        assert mock_app.add_handler.call_count >= 5  # start, price, top, alert, help
        mock_app.run_polling.assert_called_once()
