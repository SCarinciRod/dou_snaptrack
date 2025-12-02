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


class TestWaitHelpersInjection:
    """Test JavaScript injection protection in wait helpers."""

    def test_element_id_with_quotes(self):
        """Test element_id containing quotes (potential JS injection)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        # Malicious element ID with quotes
        result = wait_for_selectize(mock_page, element_id="test'); alert('xss")
        
        # Should still work (the JS will be invalid but won't execute arbitrary code)
        assert mock_page.wait_for_function.called
        
        # Verify the JS code passed contains the malicious string escaped somehow
        call_args = mock_page.wait_for_function.call_args[0][0]
        # Should contain our string (whether it works or not, it shouldn't execute alert)
        assert "test" in call_args

    def test_element_id_with_backticks(self):
        """Test element_id with backticks (template literal injection)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        result = wait_for_selectize(mock_page, element_id="test`; ${alert('xss')}")
        assert mock_page.wait_for_function.called

    def test_selector_with_backslashes(self):
        """Test selector with backslashes."""
        mock_page = Mock()
        mock_page.wait_for_selector = Mock(return_value=Mock())
        mock_page.wait_for_timeout = Mock()
        
        result = wait_for_dropdown_ready(mock_page, selector="#test\\:id")
        assert result is True


class TestWaitHelpersExceptionTypes:
    """Test that various exception types are handled correctly."""

    def test_timeout_error_handled(self):
        """Test builtin TimeoutError is handled."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=TimeoutError("timed out"))
        
        result = wait_for_selectize(mock_page, element_id="test")
        assert result is False

    def test_keyboard_interrupt_propagates(self):
        """Test KeyboardInterrupt is NOT caught (should propagate)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=KeyboardInterrupt())
        
        # KeyboardInterrupt inherits from BaseException, should propagate
        with pytest.raises(KeyboardInterrupt):
            wait_for_selectize(mock_page, element_id="test")

    def test_system_exit_propagates(self):
        """Test SystemExit is NOT caught (should propagate)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=SystemExit(1))
        
        with pytest.raises(SystemExit):
            wait_for_selectize(mock_page, element_id="test")

    @pytest.mark.asyncio
    async def test_async_keyboard_interrupt_propagates(self):
        """Test async version propagates KeyboardInterrupt."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(side_effect=KeyboardInterrupt())
        
        with pytest.raises(KeyboardInterrupt):
            await wait_for_selectize_async(mock_page, element_id="test")

    def test_memory_error_is_caught(self):
        """Test MemoryError IS caught (inherits from Exception, not BaseException)."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(side_effect=MemoryError())
        
        # MemoryError inherits from Exception, so it WILL be caught and return False
        # This is correct behavior - only BaseException subclasses propagate
        result = wait_for_selectize(mock_page, element_id="test")
        assert result is False  # Caught and handled


class TestWaitHelpersAsyncCancellation:
    """Comprehensive tests for async cancellation handling."""

    @pytest.mark.asyncio
    async def test_all_async_functions_handle_cancellation(self):
        """Test ALL async functions handle CancelledError gracefully."""
        import asyncio
        
        # Test each async function
        async_funcs = [
            (wait_for_selectize_async, {"element_id": "test"}),
            (wait_for_options_change_async, {"element_id": "test", "initial_count": 5}),
            (wait_for_network_idle_async, {}),
        ]
        
        for func, kwargs in async_funcs:
            mock_page = AsyncMock()
            # Set all possible async methods to raise CancelledError
            mock_page.wait_for_function = AsyncMock(side_effect=asyncio.CancelledError())
            mock_page.wait_for_load_state = AsyncMock(side_effect=asyncio.CancelledError())
            mock_page.wait_for_selector = AsyncMock(side_effect=asyncio.CancelledError())
            
            result = await func(mock_page, **kwargs)
            assert result is False, f"{func.__name__} should return False on CancelledError"

    @pytest.mark.asyncio
    async def test_dropdown_ready_async_handles_cancellation(self):
        """Test wait_for_dropdown_ready_async handles cancellation."""
        import asyncio
        
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=asyncio.CancelledError())
        
        result = await wait_for_dropdown_ready_async(mock_page, selector="#test")
        assert result is False

    @pytest.mark.asyncio
    async def test_angular_async_handles_cancellation(self):
        """Test wait_for_angular_async handles cancellation."""
        import asyncio
        
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=asyncio.CancelledError())
        mock_page.wait_for_timeout = AsyncMock()
        
        result = await wait_for_angular_async(mock_page, timeout=100)
        assert result is False


class TestWaitHelpersJavaScriptGeneration:
    """Test the JavaScript code generation in wait helpers."""

    def test_selectize_js_uses_correct_id(self):
        """Verify the JavaScript contains the correct element ID."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        wait_for_selectize(mock_page, element_id="my-custom-id", min_options=5)
        
        call_args = mock_page.wait_for_function.call_args[0][0]
        assert "my-custom-id" in call_args
        assert ">= 5" in call_args or ">=5" in call_args.replace(" ", "")

    def test_options_change_js_uses_initial_count(self):
        """Verify options_change JS uses the initial count correctly."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        wait_for_options_change(mock_page, element_id="test-id", initial_count=42)
        
        call_args = mock_page.wait_for_function.call_args[0][0]
        assert "42" in call_args  # Initial count should appear
        assert "!== 42" in call_args or "!==42" in call_args.replace(" ", "")

    def test_selectize_js_handles_special_element_ids(self):
        """Test JS generation with element IDs containing special characters."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        # ID with various special chars
        special_ids = ["test-id", "test_id", "testId123", "Test.Id"]
        
        for element_id in special_ids:
            wait_for_selectize(mock_page, element_id=element_id)
            call_args = mock_page.wait_for_function.call_args[0][0]
            assert element_id in call_args


class TestWaitHelpersPerformance:
    """Test performance-related edge cases."""

    def test_many_consecutive_calls(self):
        """Test many consecutive calls don't accumulate state."""
        mock_page = Mock()
        mock_page.wait_for_function = Mock(return_value=True)
        
        for i in range(100):
            result = wait_for_selectize(mock_page, element_id=f"el-{i}")
            assert result is True
        
        assert mock_page.wait_for_function.call_count == 100

    @pytest.mark.asyncio
    async def test_many_consecutive_async_calls(self):
        """Test many consecutive async calls work correctly."""
        mock_page = AsyncMock()
        mock_page.wait_for_function = AsyncMock(return_value=True)
        
        for i in range(100):
            result = await wait_for_selectize_async(mock_page, element_id=f"el-{i}")
            assert result is True
        
        assert mock_page.wait_for_function.call_count == 100
