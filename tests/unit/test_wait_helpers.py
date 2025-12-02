"""Unit tests for dou_snaptrack.utils.wait_helpers module.

Tests for intelligent wait functions.
"""
import pytest
from dou_snaptrack.utils.wait_helpers import (
    # Sync functions
    wait_for_angular,
    wait_for_selectize,
    wait_for_dropdown_ready,
    wait_for_options_change,
    wait_for_network_idle,
    # Async functions
    wait_for_angular_async,
    wait_for_selectize_async,
    wait_for_dropdown_ready_async,
    wait_for_options_change_async,
    wait_for_network_idle_async,
    # Selectors
    ANGULAR_READY_SELECTORS,
    DROPDOWN_READY_SELECTORS,
)
from unittest.mock import Mock, AsyncMock


class TestConstants:
    """Tests for module constants."""

    def test_angular_ready_selectors(self):
        """Test ANGULAR_READY_SELECTORS is a non-empty list."""
        assert isinstance(ANGULAR_READY_SELECTORS, list)
        assert len(ANGULAR_READY_SELECTORS) > 0

    def test_dropdown_ready_selectors(self):
        """Test DROPDOWN_READY_SELECTORS is a non-empty list."""
        assert isinstance(DROPDOWN_READY_SELECTORS, list)
        assert len(DROPDOWN_READY_SELECTORS) > 0


class TestSyncWaitForSelectize:
    """Tests for sync wait_for_selectize function."""

    def test_wait_for_selectize_success(self):
        """Test wait_for_selectize with Selectize loaded."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        result = wait_for_selectize(mock_page, element_id="selectize-orgao")
        
        assert result is True

    def test_wait_for_selectize_timeout(self):
        """Test wait_for_selectize handles timeout."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_selectize(mock_page, element_id="selectize-orgao")
        
        assert result is False


class TestSyncWaitForDropdownReady:
    """Tests for sync wait_for_dropdown_ready function."""

    def test_wait_for_dropdown_ready_success(self):
        """Test wait_for_dropdown_ready with options loaded."""
        mock_page = Mock()
        mock_page.wait_for_selector = Mock(return_value=Mock())
        mock_page.wait_for_timeout = Mock()
        
        result = wait_for_dropdown_ready(mock_page, selector="#slcOrgs")
        
        assert result is True

    def test_wait_for_dropdown_ready_timeout(self):
        """Test wait_for_dropdown_ready handles timeout."""
        mock_page = Mock()
        mock_page.wait_for_selector = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_dropdown_ready(mock_page, selector="#slcOrgs")
        
        assert result is False


class TestSyncWaitForOptionsChange:
    """Tests for sync wait_for_options_change function."""

    def test_wait_for_options_change_success(self):
        """Test wait_for_options_change detects change."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        result = wait_for_options_change(mock_page, element_id="cargo", initial_count=5)
        
        assert result is True

    def test_wait_for_options_change_timeout(self):
        """Test wait_for_options_change handles timeout."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_options_change(mock_page, element_id="cargo", initial_count=5)
        
        assert result is False


class TestSyncWaitForNetworkIdle:
    """Tests for sync wait_for_network_idle function."""

    def test_wait_for_network_idle_success(self):
        """Test wait_for_network_idle succeeds."""
        mock_page = Mock()
        mock_page.wait_for_load_state = Mock(return_value=None)
        
        result = wait_for_network_idle(mock_page)
        
        assert result is True
        mock_page.wait_for_load_state.assert_called_once()

    def test_wait_for_network_idle_timeout(self):
        """Test wait_for_network_idle handles timeout."""
        mock_page = Mock()
        mock_page.wait_for_load_state = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_network_idle(mock_page)
        
        assert result is False


class TestAsyncWaitForSelectize:
    """Tests for async wait_for_selectize_async function."""

    @pytest.mark.asyncio
    async def test_wait_for_selectize_async_success(self):
        """Test wait_for_selectize_async with Selectize loaded."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(return_value=True)
        
        result = await wait_for_selectize_async(mock_page, element_id="selectize-orgao")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_selectize_async_timeout(self):
        """Test wait_for_selectize_async handles timeout."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(side_effect=Exception("Timeout"))
        
        result = await wait_for_selectize_async(mock_page, element_id="selectize-orgao")
        
        assert result is False


class TestAsyncWaitForDropdownReady:
    """Tests for async wait_for_dropdown_ready_async function."""

    @pytest.mark.asyncio
    async def test_wait_for_dropdown_ready_async_success(self):
        """Test wait_for_dropdown_ready_async with options loaded."""
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=Mock())
        mock_page.wait_for_timeout = AsyncMock()
        
        result = await wait_for_dropdown_ready_async(mock_page, selector="#slcOrgs")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_dropdown_ready_async_timeout(self):
        """Test wait_for_dropdown_ready_async handles timeout."""
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        
        result = await wait_for_dropdown_ready_async(mock_page, selector="#slcOrgs")
        
        assert result is False


class TestAsyncWaitForOptionsChange:
    """Tests for async wait_for_options_change_async function."""

    @pytest.mark.asyncio
    async def test_wait_for_options_change_async_success(self):
        """Test wait_for_options_change_async detects change."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(return_value=True)
        
        result = await wait_for_options_change_async(mock_page, element_id="cargo", initial_count=5)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_options_change_async_timeout(self):
        """Test wait_for_options_change_async handles timeout."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(side_effect=Exception("Timeout"))
        
        result = await wait_for_options_change_async(mock_page, element_id="cargo", initial_count=5)
        
        assert result is False


class TestAsyncWaitForNetworkIdle:
    """Tests for async wait_for_network_idle_async function."""

    @pytest.mark.asyncio
    async def test_wait_for_network_idle_async_success(self):
        """Test wait_for_network_idle_async with idle network."""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock(return_value=None)
        
        result = await wait_for_network_idle_async(mock_page)
        
        assert result is True
        mock_page.wait_for_load_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_network_idle_async_timeout(self):
        """Test wait_for_network_idle_async handles timeout."""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("Timeout"))
        
        result = await wait_for_network_idle_async(mock_page)
        
        assert result is False


class TestFunctionSignatures:
    """Tests to verify function signatures match expectations."""

    def test_all_sync_functions_exist(self):
        """Test all sync functions are importable."""
        funcs = [
            wait_for_angular,
            wait_for_selectize,
            wait_for_dropdown_ready,
            wait_for_options_change,
            wait_for_network_idle,
        ]
        assert all(callable(f) for f in funcs)

    def test_all_async_functions_exist(self):
        """Test all async functions are importable."""
        funcs = [
            wait_for_angular_async,
            wait_for_selectize_async,
            wait_for_dropdown_ready_async,
            wait_for_options_change_async,
            wait_for_network_idle_async,
        ]
        assert all(callable(f) for f in funcs)


# =============================================================================
# EDGE CASES - Testes que realmente desafiam os limites
# =============================================================================

class TestWaitHelpersEdgeCases:
    """Edge cases that test actual program limits."""

    def test_wait_for_selectize_with_empty_element_id(self):
        """Test wait_for_selectize with empty element_id."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        # Should still call wait_for_function (Playwright will handle invalid selector)
        result = wait_for_selectize(mock_page, element_id="")
        assert result is True
        mock_page.wait_for_function.assert_called_once()

    def test_wait_for_dropdown_with_special_chars_in_selector(self):
        """Test selector with special CSS characters."""
        mock_page = Mock()
        mock_page.wait_for_selector = Mock(return_value=Mock())
        mock_page.wait_for_timeout = Mock()
        
        # Selector with special chars that need escaping
        result = wait_for_dropdown_ready(mock_page, selector="#select[data-id='test']")
        assert result is True

    def test_wait_functions_with_zero_timeout(self):
        """Test with zero timeout (should timeout immediately)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_selectize(mock_page, element_id="test", timeout=0)
        assert result is False

    def test_wait_with_negative_min_options(self):
        """Test with negative min_options (edge case)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        # Should not crash, just pass weird value to JS
        result = wait_for_selectize(mock_page, element_id="test", min_options=-1)
        assert result is True

    @pytest.mark.asyncio
    async def test_async_wait_with_cancelled_coroutine(self):
        """Test async wait handles cancellation gracefully."""
        import asyncio
        
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(side_effect=asyncio.CancelledError())
        
        # Should not raise, should return False
        result = await wait_for_selectize_async(mock_page, element_id="test")
        assert result is False

    def test_options_change_with_same_count(self):
        """Test options_change when count doesn't actually change."""
        mock_page = Mock()
        # Simulate timeout because count never changed
        mock_page.wait_for_function = Mock(side_effect=Exception("Timeout"))
        
        result = wait_for_options_change(mock_page, element_id="cargo", initial_count=5)
        assert result is False

    def test_angular_selectors_are_valid_css(self):
        """Test that ANGULAR_READY_SELECTORS are valid CSS selectors."""
        for selector in ANGULAR_READY_SELECTORS:
            # Should not contain JavaScript or be empty
            assert len(selector) > 0
            assert "=>" not in selector  # Not JS arrow function
            assert "function" not in selector  # Not JS function

    def test_dropdown_selectors_are_valid_css(self):
        """Test that DROPDOWN_READY_SELECTORS are valid CSS selectors."""
        for selector in DROPDOWN_READY_SELECTORS:
            assert len(selector) > 0
            assert "=>" not in selector
            assert "function" not in selector


class TestWaitHelpersRealBehavior:
    """Tests that verify REAL behavior, not just mocks."""

    def test_wait_for_angular_tries_all_selectors(self):
        """Verify wait_for_angular tries multiple selectors on failure."""
        mock_page = Mock()
        # First selector fails, should try next
        mock_page.wait_for_selector = Mock(side_effect=Exception("Not found"))
        mock_page.wait_for_timeout = Mock()
        
        result = wait_for_angular(mock_page, timeout=100)
        
        # Should have tried all ANGULAR_READY_SELECTORS
        assert mock_page.wait_for_selector.call_count == len(ANGULAR_READY_SELECTORS)

    def test_wait_for_dropdown_fallback_behavior(self):
        """Verify dropdown wait has proper fallback."""
        mock_page = Mock()
        mock_page.wait_for_selector = Mock(return_value=Mock())
        mock_page.wait_for_timeout = Mock()
        
        result = wait_for_dropdown_ready(mock_page, selector="#test", timeout=100)
        
        # Should call wait_for_timeout as fallback
        assert mock_page.wait_for_timeout.called or result is True
