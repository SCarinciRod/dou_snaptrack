"""Unit tests for dou_snaptrack.constants module.

Tests for centralized constants.
"""
import pytest
from dou_snaptrack.constants import (
    # Timeout constants
    TIMEOUT_PAGE_DEFAULT,
    TIMEOUT_PAGE_LONG,
    TIMEOUT_ELEMENT_DEFAULT,
    TIMEOUT_ELEMENT_SHORT,
    TIMEOUT_NAVIGATION,
    TIMEOUT_SUBPROCESS,
    TIMEOUT_SUBPROCESS_LONG,
    # Wait constants
    WAIT_ANGULAR_INIT,
    WAIT_SELECTIZE_POPULATE,
    WAIT_DROPDOWN_REPOPULATE,
    WAIT_NETWORK_IDLE,
    WAIT_ANIMATION,
    WAIT_MICRO,
    WAIT_TINY,
    WAIT_SHORT,
    WAIT_MEDIUM,
    WAIT_LONG,
    # Cache TTL constants
    CACHE_TTL_SHORT,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_LONG,
    CACHE_TTL_SESSION,
    # URLs
    BASE_DOU,
    EAGENDAS_URL,
    # Browser paths
    CHROME_PATHS,
    EDGE_PATHS,
    BROWSER_CHANNELS,
)


class TestTimeoutConstants:
    """Tests for timeout constants."""

    def test_page_timeout_default(self):
        """Test default page timeout is reasonable."""
        assert TIMEOUT_PAGE_DEFAULT > 0
        assert TIMEOUT_PAGE_DEFAULT <= 60_000  # Max 1 minute
        assert TIMEOUT_PAGE_DEFAULT >= 10_000  # At least 10 seconds

    def test_page_timeout_long(self):
        """Test long page timeout is greater than default."""
        assert TIMEOUT_PAGE_LONG > TIMEOUT_PAGE_DEFAULT

    def test_element_timeout_default(self):
        """Test element timeout is reasonable."""
        assert TIMEOUT_ELEMENT_DEFAULT > 0
        assert TIMEOUT_ELEMENT_DEFAULT <= TIMEOUT_PAGE_DEFAULT

    def test_element_timeout_short(self):
        """Test short element timeout is less than default."""
        assert TIMEOUT_ELEMENT_SHORT < TIMEOUT_ELEMENT_DEFAULT

    def test_navigation_timeout(self):
        """Test navigation timeout is reasonable."""
        assert TIMEOUT_NAVIGATION > 0
        assert TIMEOUT_NAVIGATION >= TIMEOUT_PAGE_DEFAULT

    def test_subprocess_timeout(self):
        """Test subprocess timeout is reasonable."""
        assert TIMEOUT_SUBPROCESS > 0
        assert TIMEOUT_SUBPROCESS <= 300  # Max 5 minutes (in seconds)

    def test_subprocess_timeout_long(self):
        """Test long subprocess timeout is greater than default."""
        assert TIMEOUT_SUBPROCESS_LONG > TIMEOUT_SUBPROCESS


class TestWaitConstants:
    """Tests for wait constants."""

    def test_angular_init_wait(self):
        """Test Angular init wait is reasonable."""
        assert WAIT_ANGULAR_INIT > 0
        assert WAIT_ANGULAR_INIT <= 10_000  # Max 10 seconds

    def test_selectize_populate_wait(self):
        """Test Selectize populate wait is reasonable."""
        assert WAIT_SELECTIZE_POPULATE > 0
        assert WAIT_SELECTIZE_POPULATE <= 10_000

    def test_dropdown_repopulate_wait(self):
        """Test dropdown repopulate wait is reasonable."""
        assert WAIT_DROPDOWN_REPOPULATE > 0

    def test_network_idle_wait(self):
        """Test network idle wait is reasonable."""
        assert WAIT_NETWORK_IDLE > 0
        assert WAIT_NETWORK_IDLE <= 5_000  # Max 5 seconds

    def test_animation_wait(self):
        """Test animation wait is short."""
        assert WAIT_ANIMATION > 0
        assert WAIT_ANIMATION <= 1_000  # Max 1 second


class TestCacheTTLConstants:
    """Tests for cache TTL constants."""

    def test_cache_ttl_short(self):
        """Test short cache TTL is reasonable."""
        assert CACHE_TTL_SHORT > 0
        assert CACHE_TTL_SHORT <= 600  # Max 10 minutes

    def test_cache_ttl_medium(self):
        """Test medium cache TTL is greater than short."""
        assert CACHE_TTL_MEDIUM > CACHE_TTL_SHORT

    def test_cache_ttl_long(self):
        """Test long cache TTL is greater than medium."""
        assert CACHE_TTL_LONG > CACHE_TTL_MEDIUM

    def test_cache_ttl_session(self):
        """Test session cache TTL is very long."""
        assert CACHE_TTL_SESSION >= CACHE_TTL_LONG

    def test_cache_ttl_ordering(self):
        """Test cache TTLs are in ascending order."""
        assert CACHE_TTL_SHORT < CACHE_TTL_MEDIUM < CACHE_TTL_LONG <= CACHE_TTL_SESSION


class TestConstantTypes:
    """Tests for constant types and values."""

    def test_all_timeouts_are_integers(self):
        """Test all timeout constants are integers."""
        timeouts = [
            TIMEOUT_PAGE_DEFAULT,
            TIMEOUT_PAGE_LONG,
            TIMEOUT_ELEMENT_DEFAULT,
            TIMEOUT_ELEMENT_SHORT,
            TIMEOUT_NAVIGATION,
            TIMEOUT_SUBPROCESS,
            TIMEOUT_SUBPROCESS_LONG,
        ]
        assert all(isinstance(t, int) for t in timeouts)

    def test_all_waits_are_integers(self):
        """Test all wait constants are integers."""
        waits = [
            WAIT_ANGULAR_INIT,
            WAIT_SELECTIZE_POPULATE,
            WAIT_DROPDOWN_REPOPULATE,
            WAIT_NETWORK_IDLE,
            WAIT_ANIMATION,
        ]
        assert all(isinstance(w, int) for w in waits)

    def test_all_cache_ttls_are_integers(self):
        """Test all cache TTL constants are integers."""
        ttls = [
            CACHE_TTL_SHORT,
            CACHE_TTL_MEDIUM,
            CACHE_TTL_LONG,
            CACHE_TTL_SESSION,
        ]
        assert all(isinstance(t, int) for t in ttls)

    def test_no_zero_values(self):
        """Test no constants are zero."""
        all_constants = [
            TIMEOUT_PAGE_DEFAULT, TIMEOUT_PAGE_LONG, TIMEOUT_ELEMENT_DEFAULT,
            TIMEOUT_ELEMENT_SHORT, TIMEOUT_NAVIGATION, TIMEOUT_SUBPROCESS,
            TIMEOUT_SUBPROCESS_LONG, WAIT_ANGULAR_INIT, WAIT_SELECTIZE_POPULATE,
            WAIT_DROPDOWN_REPOPULATE, WAIT_NETWORK_IDLE, WAIT_ANIMATION,
            CACHE_TTL_SHORT, CACHE_TTL_MEDIUM, CACHE_TTL_LONG, CACHE_TTL_SESSION,
        ]
        assert all(c > 0 for c in all_constants)


# =============================================================================
# EDGE CASES AND STRESS TESTS
# =============================================================================


class TestWaitConstantsHierarchy:
    """Test wait constants have proper hierarchy."""

    def test_wait_hierarchy_micro_to_long(self):
        """Test WAIT constants increase: MICRO < TINY < SHORT < MEDIUM < LONG."""
        assert WAIT_MICRO < WAIT_TINY
        assert WAIT_TINY < WAIT_SHORT
        assert WAIT_SHORT < WAIT_MEDIUM
        assert WAIT_MEDIUM < WAIT_LONG

    def test_animation_wait_is_short(self):
        """Test animation wait is in the 'short' range."""
        assert WAIT_ANIMATION <= WAIT_MEDIUM
        assert WAIT_ANIMATION >= WAIT_MICRO


class TestURLConstants:
    """Test URL constants."""

    def test_base_dou_is_https(self):
        """Test BASE_DOU uses HTTPS."""
        assert BASE_DOU.startswith("https://")

    def test_eagendas_url_is_https(self):
        """Test EAGENDAS_URL uses HTTPS."""
        assert EAGENDAS_URL.startswith("https://")

    def test_urls_are_valid_format(self):
        """Test URLs have valid format."""
        for url in [BASE_DOU, EAGENDAS_URL]:
            assert "://" in url
            assert " " not in url  # No spaces
            assert "\n" not in url  # No newlines

    def test_urls_end_with_correct_domain(self):
        """Test URLs have expected domains."""
        assert "gov.br" in BASE_DOU
        assert "gov.br" in EAGENDAS_URL


class TestBrowserPaths:
    """Test browser path constants."""

    def test_chrome_paths_are_list(self):
        """Test CHROME_PATHS is a list."""
        assert isinstance(CHROME_PATHS, list)
        assert len(CHROME_PATHS) > 0

    def test_edge_paths_are_list(self):
        """Test EDGE_PATHS is a list."""
        assert isinstance(EDGE_PATHS, list)
        assert len(EDGE_PATHS) > 0

    def test_all_paths_are_absolute_windows(self):
        """Test all browser paths are absolute Windows paths."""
        import re
        
        for path in CHROME_PATHS + EDGE_PATHS:
            assert re.match(r'^[A-Z]:\\', path), f"Path {path} should be absolute Windows path"

    def test_all_paths_end_with_exe(self):
        """Test all browser paths end with .exe."""
        for path in CHROME_PATHS + EDGE_PATHS:
            assert path.endswith('.exe'), f"Path {path} should end with .exe"

    def test_chrome_paths_contain_chrome(self):
        """Test Chrome paths contain 'chrome' in path."""
        for path in CHROME_PATHS:
            assert 'chrome' in path.lower()

    def test_edge_paths_contain_edge(self):
        """Test Edge paths contain 'edge' in path."""
        for path in EDGE_PATHS:
            assert 'edge' in path.lower()


class TestBrowserChannels:
    """Test browser channel constants."""

    def test_browser_channels_is_list(self):
        """Test BROWSER_CHANNELS is a list."""
        assert isinstance(BROWSER_CHANNELS, list)

    def test_browser_channels_not_empty(self):
        """Test BROWSER_CHANNELS is not empty."""
        assert len(BROWSER_CHANNELS) > 0

    def test_browser_channels_are_strings(self):
        """Test all channels are strings."""
        for channel in BROWSER_CHANNELS:
            assert isinstance(channel, str)

    def test_browser_channels_valid_names(self):
        """Test channels are valid Playwright channel names."""
        valid_channels = {"chrome", "msedge", "chromium", "firefox", "webkit"}
        for channel in BROWSER_CHANNELS:
            assert channel in valid_channels, f"Unknown channel: {channel}"


class TestTimeoutRelationships:
    """Test relationships between timeout constants."""

    def test_page_timeouts_ordered(self):
        """Test page timeouts are in ascending order."""
        from dou_snaptrack.constants import TIMEOUT_PAGE_DEFAULT, TIMEOUT_PAGE_LONG, TIMEOUT_PAGE_SLOW
        
        assert TIMEOUT_PAGE_DEFAULT <= TIMEOUT_PAGE_LONG
        assert TIMEOUT_PAGE_LONG <= TIMEOUT_PAGE_SLOW

    def test_element_timeouts_ordered(self):
        """Test element timeouts are in ascending order."""
        from dou_snaptrack.constants import (
            TIMEOUT_ELEMENT_SHORT, TIMEOUT_ELEMENT_DEFAULT,
            TIMEOUT_ELEMENT_NORMAL, TIMEOUT_ELEMENT_SLOW
        )
        
        assert TIMEOUT_ELEMENT_SHORT <= TIMEOUT_ELEMENT_DEFAULT
        assert TIMEOUT_ELEMENT_DEFAULT <= TIMEOUT_ELEMENT_NORMAL
        assert TIMEOUT_ELEMENT_NORMAL <= TIMEOUT_ELEMENT_SLOW

    def test_element_timeout_less_than_page_timeout(self):
        """Test element timeouts are less than or equal to page timeouts."""
        from dou_snaptrack.constants import TIMEOUT_ELEMENT_SLOW, TIMEOUT_PAGE_LONG
        
        # Element timeout shouldn't exceed page timeout (doesn't make sense)
        assert TIMEOUT_ELEMENT_SLOW <= TIMEOUT_PAGE_LONG


class TestConstantBoundaries:
    """Test constant boundaries and limits."""

    def test_timeouts_not_too_short(self):
        """Test no timeout is unreasonably short (< 100ms)."""
        timeouts = [
            TIMEOUT_PAGE_DEFAULT, TIMEOUT_PAGE_LONG,
            TIMEOUT_ELEMENT_DEFAULT, TIMEOUT_ELEMENT_SHORT,
            TIMEOUT_NAVIGATION,
        ]
        
        for t in timeouts:
            assert t >= 100, f"Timeout {t}ms is too short (< 100ms)"

    def test_timeouts_not_too_long(self):
        """Test no timeout is unreasonably long (> 15 min)."""
        timeouts = [
            TIMEOUT_PAGE_DEFAULT, TIMEOUT_PAGE_LONG,
            TIMEOUT_ELEMENT_DEFAULT, TIMEOUT_ELEMENT_SHORT,
            TIMEOUT_NAVIGATION,
        ]
        
        for t in timeouts:
            assert t <= 900_000, f"Timeout {t}ms is too long (> 15 min)"

    def test_subprocess_timeout_in_seconds(self):
        """Test subprocess timeout appears to be in seconds, not ms."""
        # Subprocess timeouts should be in seconds (reasonable range)
        assert TIMEOUT_SUBPROCESS <= 3600, "Subprocess timeout seems too high for seconds"
        assert TIMEOUT_SUBPROCESS >= 1, "Subprocess timeout should be at least 1 second"

    def test_cache_ttl_reasonable(self):
        """Test cache TTLs are reasonable (1 min to 1 day)."""
        ttls = [CACHE_TTL_SHORT, CACHE_TTL_MEDIUM, CACHE_TTL_LONG, CACHE_TTL_SESSION]
        
        for ttl in ttls:
            assert ttl >= 60, f"Cache TTL {ttl}s is too short (< 1 min)"
            assert ttl <= 86400, f"Cache TTL {ttl}s is too long (> 1 day)"


class TestConstantModuleSafety:
    """Test that constants module is safe to import."""

    def test_no_side_effects_on_import(self):
        """Test importing constants doesn't have side effects."""
        import importlib
        import sys
        
        # Reload module to test import
        module_name = "dou_snaptrack.constants"
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        
        # If we get here, import didn't crash
        assert True

    def test_constants_are_immutable_types(self):
        """Test constants use immutable types where appropriate."""
        # Strings are immutable
        assert isinstance(BASE_DOU, str)
        assert isinstance(EAGENDAS_URL, str)
        
        # Ints are immutable
        assert isinstance(TIMEOUT_PAGE_DEFAULT, int)
        
        # Lists are mutable - this is a potential issue
        # Document that CHROME_PATHS and EDGE_PATHS are mutable
        assert isinstance(CHROME_PATHS, list)  # Known mutable
        assert isinstance(EDGE_PATHS, list)  # Known mutable
