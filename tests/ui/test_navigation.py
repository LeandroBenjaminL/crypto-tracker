"""
Tests for the sidebar navigation module.

Mocks streamlit to test navigation state, page selection, and helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.ui.navigation import (
    CURRENCY_OPTIONS,
    PAGE_OPTIONS,
    THEME_OPTIONS,
    get_page,
    is_page,
    render_sidebar,
)


class MockSessionState:
    """Mimics streamlit's session_state with attribute and 'in' access."""

    def __init__(self, **kwargs: str) -> None:
        self._data: dict[str, str] = {}
        for k, v in kwargs.items():
            self._data[k] = v

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: str) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: str | None = None) -> str | None:
        """Dict-style .get() used by navigation and theme modules."""
        return self._data.get(key, default)


class TestConstants:
    """Tests for navigation constants."""

    def test_page_options_count(self) -> None:
        assert len(PAGE_OPTIONS) == 6

    def test_page_contains_favoritos(self) -> None:
        assert "⭐  Favoritos" in PAGE_OPTIONS

    def test_currency_options(self) -> None:
        assert "usd" in CURRENCY_OPTIONS
        assert len(CURRENCY_OPTIONS) == 7

    def test_theme_options(self) -> None:
        assert THEME_OPTIONS == ["dark", "light"]


class TestGetPage:
    """Tests for get_page."""

    @patch("src.ui.navigation.st")
    def test_get_page_from_session_state(self, mock_st: MagicMock) -> None:
        """get_page returns the value from session_state if present."""
        mock_st.session_state = MockSessionState(current_page="Precio")
        result = get_page()
        assert result == "Precio"

    @patch("src.ui.navigation.st")
    def test_get_page_no_session_state(self, mock_st: MagicMock) -> None:
        """get_page falls back to _render_radio when session_state is empty."""
        mock_st.session_state = MockSessionState()
        _radio_result = "🔍  Precio"
        mock_st.radio.return_value = _radio_result
        mock_st.sidebar = MagicMock()
        mock_st.selectbox.return_value = "usd"
        mock_st.divider = MagicMock()
        mock_st.markdown = MagicMock()

        result = get_page()
        assert result == _radio_result


class TestIsPage:
    """Tests for is_page."""

    @patch("src.ui.navigation.st")
    def test_is_page_matches(self, mock_st: MagicMock) -> None:
        """is_page returns True when the page name is in current_page."""
        mock_st.session_state = MockSessionState(current_page="🔍  Precio")
        assert is_page("Precio") is True

    @patch("src.ui.navigation.st")
    def test_is_page_no_match(self, mock_st: MagicMock) -> None:
        """is_page returns False when the page doesn't match."""
        mock_st.session_state = MockSessionState(current_page="⭐  Favoritos")
        assert is_page("Precio") is False

    @patch("src.ui.navigation.st")
    def test_is_page_empty_session(self, mock_st: MagicMock) -> None:
        """is_page returns False when current_page is not in session."""
        mock_st.session_state = MockSessionState()
        assert is_page("Precio") is False


class TestRenderSidebar:
    """Tests for render_sidebar."""

    @patch("src.ui.navigation.st")
    def test_render_sidebar_returns_page_and_currency(self, mock_st: MagicMock) -> None:
        """render_sidebar returns a tuple of (page, currency)."""
        mock_st.session_state = MockSessionState()
        mock_st.sidebar = MagicMock()
        mock_st.radio.return_value = "⭐  Favoritos"
        mock_st.selectbox.side_effect = ["usd", "dark"]
        mock_st.divider = MagicMock()
        mock_st.markdown = MagicMock()

        page, currency = render_sidebar()

        assert page == "⭐  Favoritos"
        assert currency == "usd"

    @patch("src.ui.navigation.st")
    def test_render_sidebar_currency_from_session(self, mock_st: MagicMock) -> None:
        """render_sidebar reads currency from session_state when set."""
        mock_st.session_state = MockSessionState(currency="eur")
        mock_st.sidebar = MagicMock()
        mock_st.radio.return_value = "🔍  Precio"
        mock_st.selectbox.side_effect = ["eur", "dark"]
        mock_st.divider = MagicMock()
        mock_st.markdown = MagicMock()

        page, currency = render_sidebar()
        assert currency == "eur"
