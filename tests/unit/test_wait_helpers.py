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
