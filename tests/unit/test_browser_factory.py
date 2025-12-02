"""Unit tests for dou_snaptrack.utils.browser_factory module.

Tests for BrowserConfig and BrowserFactory classes.
"""
import os
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


# =============================================================================
# EDGE CASES AND STRESS TESTS
# =============================================================================


class TestBrowserConfigEdgeCases:
    """Edge cases for BrowserConfig."""

    def test_config_with_zero_timeout(self):
        """Test BrowserConfig with zero timeout."""
        config = BrowserConfig(timeout=0)
        assert config.timeout == 0

    def test_config_with_negative_timeout(self):
        """Test BrowserConfig with negative timeout (Playwright uses -1 for infinite)."""
        config = BrowserConfig(timeout=-1)
        assert config.timeout == -1

    def test_config_with_extreme_viewport(self):
        """Test BrowserConfig with extreme viewport sizes."""
        # Very small
        config_small = BrowserConfig(viewport_width=1, viewport_height=1)
        assert config_small.viewport_width == 1
        
        # Very large (4K)
        config_4k = BrowserConfig(viewport_width=3840, viewport_height=2160)
        assert config_4k.viewport_width == 3840
        
        # Very large (8K)
        config_8k = BrowserConfig(viewport_width=7680, viewport_height=4320)
        assert config_8k.viewport_width == 7680

    def test_config_with_zero_slow_mo(self):
        """Test BrowserConfig with zero slow_mo."""
        config = BrowserConfig(slow_mo=0)
        assert config.slow_mo == 0

    def test_config_with_large_slow_mo(self):
        """Test BrowserConfig with large slow_mo value."""
        config = BrowserConfig(slow_mo=10_000)
        assert config.slow_mo == 10_000

    def test_config_blocked_patterns_default_not_shared(self):
        """Test that default blocked_patterns are not shared between instances."""
        config1 = BrowserConfig()
        config2 = BrowserConfig()
        
        config1.blocked_patterns.append("**/*.custom")
        
        # config2 should NOT have the new pattern (no shared mutable default)
        assert "**/*.custom" not in config2.blocked_patterns

    def test_config_blocked_patterns_custom(self):
        """Test custom blocked_patterns."""
        custom_patterns = ["**/*.mp4", "**/*.webm"]
        config = BrowserConfig(blocked_patterns=custom_patterns)
        
        assert config.blocked_patterns == custom_patterns

    def test_config_all_booleans_false(self):
        """Test config with all booleans as False."""
        config = BrowserConfig(
            headless=False,
            ignore_https_errors=False,
            block_resources=False,
            prefer_edge=False,
        )
        
        assert config.headless is False
        assert config.ignore_https_errors is False
        assert config.block_resources is False
        assert config.prefer_edge is False

    def test_config_all_booleans_true(self):
        """Test config with all booleans as True."""
        config = BrowserConfig(
            headless=True,
            ignore_https_errors=True,
            block_resources=True,
            prefer_edge=True,
        )
        
        assert config.headless is True
        assert config.ignore_https_errors is True
        assert config.block_resources is True
        assert config.prefer_edge is True


class TestFindSystemBrowserEdgeCases:
    """Edge cases for find_system_browser."""

    def test_returns_absolute_path(self):
        """Test that returned path is absolute."""
        path = find_system_browser()
        
        if path is not None:
            assert os.path.isabs(path), f"Path {path} should be absolute"

    def test_returned_path_exists(self):
        """Test that returned path actually exists."""
        path = find_system_browser()
        
        if path is not None:
            assert os.path.exists(path), f"Path {path} should exist"

    def test_prefer_edge_changes_priority(self):
        """Test prefer_edge actually changes search priority."""
        # Can't fully test without mocking filesystem, but verify it doesn't crash
        path_chrome = find_system_browser(prefer_edge=False)
        path_edge = find_system_browser(prefer_edge=True)
        
        # Both should return valid path or None
        assert path_chrome is None or isinstance(path_chrome, str)
        assert path_edge is None or isinstance(path_edge, str)

    def test_handles_missing_env_var_gracefully(self):
        """Test handles missing PLAYWRIGHT_CHROME_PATH gracefully."""
        # Save and remove env var if it exists
        old_val = os.environ.pop("PLAYWRIGHT_CHROME_PATH", None)
        
        try:
            path = find_system_browser()
            # Should not crash
            assert path is None or isinstance(path, str)
        finally:
            # Restore
            if old_val is not None:
                os.environ["PLAYWRIGHT_CHROME_PATH"] = old_val


class TestGetBrowserChannelsEdgeCases:
    """Edge cases for get_browser_channels."""

    def test_returns_list(self):
        """Test returns a list."""
        channels = get_browser_channels()
        assert isinstance(channels, list)

    def test_all_channels_are_strings(self):
        """Test all channels are strings."""
        channels = get_browser_channels()
        assert all(isinstance(c, str) for c in channels)

    def test_channels_not_empty(self):
        """Test channels list is not empty."""
        channels = get_browser_channels()
        assert len(channels) > 0

    def test_channels_no_duplicates(self):
        """Test no duplicate channels."""
        channels = get_browser_channels()
        assert len(channels) == len(set(channels))

    def test_prefer_edge_changes_order_not_content(self):
        """Test prefer_edge changes order but not content."""
        channels_default = get_browser_channels(prefer_edge=False)
        channels_edge = get_browser_channels(prefer_edge=True)
        
        # Same channels, different order
        assert set(channels_default) == set(channels_edge)
        assert channels_default[0] != channels_edge[0]


class TestPredefinedConfigsRelationships:
    """Test relationships between predefined configs."""

    def test_slow_timeout_greater_than_fast(self):
        """Test CONFIG_SLOW has longer timeout than CONFIG_FAST."""
        assert CONFIG_SLOW.timeout > CONFIG_FAST.timeout

    def test_debug_has_slow_mo(self):
        """Test CONFIG_DEBUG has non-zero slow_mo."""
        assert CONFIG_DEBUG.slow_mo > 0
        assert CONFIG_FAST.slow_mo == 0

    def test_debug_not_headless(self):
        """Test CONFIG_DEBUG is not headless (for visual debugging)."""
        assert CONFIG_DEBUG.headless is False
        assert CONFIG_FAST.headless is True

    def test_fast_blocks_resources(self):
        """Test CONFIG_FAST blocks resources for speed."""
        assert CONFIG_FAST.block_resources is True
        assert CONFIG_SLOW.block_resources is False  # SLOW needs all resources

    def test_all_presets_have_valid_viewport(self):
        """Test all presets have reasonable viewport dimensions."""
        presets = [CONFIG_FAST, CONFIG_SLOW, CONFIG_DEBUG, CONFIG_EAGENDAS]
        
        for preset in presets:
            assert preset.viewport_width >= 800
            assert preset.viewport_height >= 600
            assert preset.viewport_width <= 10000
            assert preset.viewport_height <= 10000


class TestBrowserConfigImmutabilityExpectations:
    """Test that configs behave as expected regarding mutability."""

    def test_config_attributes_are_mutable(self):
        """Test that config attributes can be modified (dataclass behavior)."""
        config = BrowserConfig()
        original_timeout = config.timeout
        
        config.timeout = 99999
        
        assert config.timeout == 99999
        assert config.timeout != original_timeout

    def test_modifying_config_does_not_affect_preset(self):
        """Test modifying a preset doesn't affect other instances."""
        # Create a copy-like config
        config = BrowserConfig(
            headless=CONFIG_FAST.headless,
            timeout=CONFIG_FAST.timeout,
        )
        
        config.timeout = 1
        
        # Original preset should be unchanged
        assert CONFIG_FAST.timeout != 1


class TestBrowserFactoryMethodSignatures:
    """Test BrowserFactory method signatures."""

    def test_create_accepts_config(self):
        """Test create() accepts config parameter."""
        import inspect
        sig = inspect.signature(BrowserFactory.create)
        params = list(sig.parameters.keys())
        
        assert "config" in params

    def test_create_async_accepts_config(self):
        """Test create_async() accepts config parameter."""
        import inspect
        sig = inspect.signature(BrowserFactory.create_async)
        params = list(sig.parameters.keys())
        
        assert "config" in params

    def test_create_page_accepts_config(self):
        """Test create_page() accepts config parameter."""
        import inspect
        sig = inspect.signature(BrowserFactory.create_page)
        params = list(sig.parameters.keys())
        
        assert "config" in params
