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
    # Cache TTL constants
    CACHE_TTL_SHORT,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_LONG,
    CACHE_TTL_SESSION,
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
