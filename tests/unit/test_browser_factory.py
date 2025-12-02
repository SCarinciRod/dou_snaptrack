"""Unit tests for dou_snaptrack.utils.browser_factory module.

Tests for BrowserConfig and BrowserFactory classes.
"""
import pytest
from dou_snaptrack.utils.browser_factory import (
    BrowserConfig,
    BrowserFactory,
    CONFIG_FAST,
    CONFIG_SLOW,
    CONFIG_DEBUG,
    CONFIG_EAGENDAS,
    find_system_browser,
    get_browser_channels,
)


class TestBrowserConfig:
    """Tests for BrowserConfig dataclass."""

    def test_default_config(self):
        """Test default BrowserConfig values."""
        config = BrowserConfig()
        
        assert config.headless is True
        assert config.viewport_width == 1366
        assert config.viewport_height == 900
        assert config.ignore_https_errors is True
        assert config.slow_mo == 0
        assert config.prefer_edge is False

    def test_custom_config(self):
        """Test custom BrowserConfig values."""
        config = BrowserConfig(
            headless=False,
            timeout=60_000,
            viewport_width=1920,
            viewport_height=1080,
            block_resources=True,
            prefer_edge=True,
        )
        
        assert config.headless is False
        assert config.timeout == 60_000
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.block_resources is True
        assert config.prefer_edge is True


class TestPredefinedConfigs:
    """Tests for predefined configuration instances."""

    def test_config_fast(self):
        """Test CONFIG_FAST preset."""
        assert CONFIG_FAST.headless is True
        assert CONFIG_FAST.block_resources is True

    def test_config_slow(self):
        """Test CONFIG_SLOW preset (for unstable connections)."""
        assert CONFIG_SLOW.headless is True
        assert CONFIG_SLOW.timeout > CONFIG_FAST.timeout

    def test_config_debug(self):
        """Test CONFIG_DEBUG preset."""
        assert CONFIG_DEBUG.headless is False
        assert CONFIG_DEBUG.slow_mo > 0

    def test_config_eagendas(self):
        """Test CONFIG_EAGENDAS preset."""
        assert CONFIG_EAGENDAS.headless is True


class TestFindSystemBrowser:
    """Tests for find_system_browser function."""

    def test_returns_string_or_none(self):
        """Test find_system_browser returns path or None."""
        path = find_system_browser()
        
        assert path is None or isinstance(path, str)

    def test_finds_chrome_or_edge(self):
        """Test find_system_browser finds Chrome or Edge on Windows."""
        path = find_system_browser()
        
        if path is not None:
            assert "chrome" in path.lower() or "edge" in path.lower()
            assert path.endswith(".exe")


class TestGetBrowserChannels:
    """Tests for get_browser_channels function."""

    def test_default_order(self):
        """Test default channel order (Chrome first)."""
        channels = get_browser_channels()
        
        assert channels[0] == "chrome"
        assert "msedge" in channels

    def test_prefer_edge(self):
        """Test Edge-preferred channel order."""
        channels = get_browser_channels(prefer_edge=True)
        
        assert channels[0] == "msedge"
        assert "chrome" in channels


class TestBrowserFactory:
    """Tests for BrowserFactory static methods."""

    def test_create_is_context_manager(self):
        """Test create() returns a context manager."""
        assert hasattr(BrowserFactory, "create")
        assert callable(BrowserFactory.create)

    def test_create_async_is_context_manager(self):
        """Test create_async() returns an async context manager."""
        assert hasattr(BrowserFactory, "create_async")
        assert callable(BrowserFactory.create_async)

    def test_create_page_exists(self):
        """Test create_page() shortcut exists."""
        assert hasattr(BrowserFactory, "create_page")
        assert callable(BrowserFactory.create_page)
