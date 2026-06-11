"""
Tests for the theme module.

Mocks streamlit to test theme detection, setting, and color palettes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.ui.theme import (
    DARK_VARS,
    LIGHT_VARS,
    detect_theme,
    get_theme_vars,
    inject_theme_css,
    set_theme,
    theme_colors,
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


class TestDetectTheme:
    """Tests for detect_theme."""

    @patch("src.ui.theme.st")
    def test_detect_theme_default(self, mock_st: MagicMock) -> None:
        """When no theme is in session, defaults to 'dark'."""
        mock_st.session_state = MockSessionState()
        assert detect_theme() == "dark"

    @patch("src.ui.theme.st")
    def test_detect_theme_dark(self, mock_st: MagicMock) -> None:
        """Returns 'dark' when session has 'dark'."""
        mock_st.session_state = MockSessionState(theme="dark")
        assert detect_theme() == "dark"

    @patch("src.ui.theme.st")
    def test_detect_theme_light(self, mock_st: MagicMock) -> None:
        """Returns 'light' when session has 'light'."""
        mock_st.session_state = MockSessionState(theme="light")
        assert detect_theme() == "light"


class TestSetTheme:
    """Tests for set_theme."""

    @patch("src.ui.theme.st")
    def test_set_theme_changes(self, mock_st: MagicMock) -> None:
        """Setting a different theme updates session and reruns."""
        mock_st.session_state = MockSessionState(theme="dark")
        set_theme("light")
        assert mock_st.session_state.theme == "light"
        mock_st.rerun.assert_called_once()

    @patch("src.ui.theme.st")
    def test_set_theme_same(self, mock_st: MagicMock) -> None:
        """Setting the same theme does nothing (no rerun)."""
        mock_st.session_state = MockSessionState(theme="dark")
        set_theme("dark")
        mock_st.rerun.assert_not_called()


class TestThemeColors:
    """Tests for theme_colors."""

    @patch("src.ui.theme.detect_theme", return_value="dark")
    def test_theme_colors_dark(self, mock_detect: MagicMock) -> None:
        """Dark theme returns dark color palette."""
        colors = theme_colors()
        assert colors["green"] == "#00d4aa"
        assert colors["red"] == "#ff6b6b"
        assert colors["text"] == "#f0f0f0"

    @patch("src.ui.theme.detect_theme", return_value="light")
    def test_theme_colors_light(self, mock_detect: MagicMock) -> None:
        """Light theme returns light color palette."""
        colors = theme_colors()
        assert colors["green"] == "#00a676"
        assert colors["red"] == "#e53e3e"
        assert colors["text"] == "#1a1a2e"

    @patch("src.ui.theme.detect_theme", return_value="dark")
    def test_theme_colors_all_keys(self, mock_detect: MagicMock) -> None:
        """Theme colors dict includes all expected keys."""
        colors = theme_colors()
        expected_keys = {
            "green",
            "red",
            "text",
            "text_secondary",
            "grid",
            "bg_table",
            "bg_table_header",
            "bg_table_border",
            "bg_table_text",
            "bg_table_header_text",
            "bg_table_hover",
            "treemap_mid",
            "fill_green",
            "fill_red",
        }
        assert set(colors.keys()) == expected_keys


class TestGetThemeVars:
    """Tests for get_theme_vars."""

    @patch("src.ui.theme.detect_theme", return_value="dark")
    def test_get_theme_vars_dark(self, mock_detect: MagicMock) -> None:
        """Dark theme returns DARK_VARS."""
        assert get_theme_vars() == DARK_VARS

    @patch("src.ui.theme.detect_theme", return_value="light")
    def test_get_theme_vars_light(self, mock_detect: MagicMock) -> None:
        """Light theme returns LIGHT_VARS."""
        assert get_theme_vars() == LIGHT_VARS


class TestInjectThemeCss:
    """Tests for inject_theme_css."""

    @patch("src.ui.theme.st")
    def test_inject_theme_css_calls_markdown(self, mock_st: MagicMock) -> None:
        """inject_theme_css calls st.markdown with CSS content."""
        mock_st.session_state = MockSessionState(theme="dark")
        inject_theme_css()
        mock_st.markdown.assert_called_once()
        args, kwargs = mock_st.markdown.call_args
        assert "unsafe_allow_html" in kwargs
        assert ":root" in args[0]
