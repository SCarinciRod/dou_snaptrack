"""Unit tests for dou_snaptrack.utils.responses module.

Tests for OperationResult, FetchResult, and BatchResult dataclasses.
"""
import json
import pytest
from dou_snaptrack.utils.responses import (
    OperationResult,
    FetchResult,
    BatchResult,
    success_response,
    error_response,
    parse_subprocess_output,
)


class TestOperationResult:
    """Tests for OperationResult dataclass."""

    def test_ok_creates_success_result(self):
        """Test that ok() creates a successful result."""
        result = OperationResult.ok({"key": "value"})
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_ok_with_list_data(self):
        """Test ok() with list data."""
        result = OperationResult.ok([1, 2, 3])
        
        assert result.success is True
        assert result.data == [1, 2, 3]

    def test_ok_with_none_data(self):
        """Test ok() with None data (still success)."""
        result = OperationResult.ok(None)
        
        assert result.success is True
        assert result.data is None

    def test_ok_with_metadata(self):
        """Test ok() with metadata."""
        result = OperationResult.ok({"items": []}, elapsed_ms=150)
        
        assert result.success is True
        assert result.metadata.get("elapsed_ms") == 150

    def test_fail_creates_failure_result(self):
        """Test that fail() creates a failure result."""
        result = OperationResult.fail("Something went wrong")
        
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.data is None

    def test_to_json_success(self):
        """Test JSON serialization of successful result."""
        result = OperationResult.ok({"items": [1, 2, 3]})
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["success"] is True
        assert parsed["data"]["items"] == [1, 2, 3]

    def test_to_json_failure(self):
        """Test JSON serialization of failure result."""
        result = OperationResult.fail("Error message")
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["success"] is False
        assert parsed["error"] == "Error message"

    def test_to_json_unicode(self):
        """Test JSON serialization preserves Unicode."""
        result = OperationResult.ok({"name": "Órgão Público"})
        json_str = result.to_json()
        
        assert "Órgão" in json_str

    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = '{"success": true, "data": {"key": "value"}}'
        result = OperationResult.from_json(json_str)
        
        assert result.success is True
        assert result.data["key"] == "value"


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_ok_with_options(self):
        """Test ok_with_options creates fetch result."""
        result = FetchResult.ok_with_options(
            n1_options=["Órgão A", "Órgão B"],
            n2_mapping={"Órgão A": ["Sub 1", "Sub 2"]}
        )
        
        assert result.success is True
        assert result.data["n1_options"] == ["Órgão A", "Órgão B"]
        assert result.data["n2_mapping"]["Órgão A"] == ["Sub 1", "Sub 2"]

    def test_inherits_from_operation_result(self):
        """Test FetchResult inherits from OperationResult."""
        assert issubclass(FetchResult, OperationResult)

    def test_fail_creates_failure(self):
        """Test fail() creates failure result."""
        result = FetchResult.fail("Timeout fetching data")
        
        assert result.success is False
        assert result.error == "Timeout fetching data"


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_ok_with_stats(self):
        """Test ok_with_stats creates batch result."""
        result = BatchResult.ok_with_stats(
            total=10,
            success_count=8,
            failed_count=2
        )
        
        assert result.success is True
        assert result.data["total"] == 10
        assert result.data["success_count"] == 8
        assert result.data["failed_count"] == 2

    def test_ok_with_items(self):
        """Test ok_with_stats with items list."""
        items = [{"url": "http://a.com", "status": "ok"}]
        result = BatchResult.ok_with_stats(
            total=1,
            success_count=1,
            failed_count=0,
            items=items
        )
        
        assert result.data["items"] == items

    def test_fail_creates_failure(self):
        """Test fail() creates failure result."""
        result = BatchResult.fail("Batch processing error")
        
        assert result.success is False
        assert result.error == "Batch processing error"

    def test_inherits_from_operation_result(self):
        """Test BatchResult inherits from OperationResult."""
        assert issubclass(BatchResult, OperationResult)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_success_response(self):
        """Test success_response helper."""
        json_str = success_response({"key": "value"})
        parsed = json.loads(json_str)
        
        assert parsed["success"] is True
        assert parsed["data"]["key"] == "value"

    def test_error_response(self):
        """Test error_response helper."""
        json_str = error_response("Error occurred")
        parsed = json.loads(json_str)
        
        assert parsed["success"] is False
        assert parsed["error"] == "Error occurred"

    def test_parse_subprocess_output_success(self):
        """Test parse_subprocess_output with valid JSON."""
        output = 'Some log line\n{"success": true, "data": "result"}'
        result = parse_subprocess_output(output)
        
        assert result.success is True
        assert result.data == "result"

    def test_parse_subprocess_output_no_json(self):
        """Test parse_subprocess_output with no JSON."""
        output = "Just some logs\nNo JSON here"
        result = parse_subprocess_output(output)
        
        assert result.success is False
        assert "Nenhum JSON" in result.error


# =============================================================================
# EDGE CASES AND BOUNDARY TESTS - Testes de limites reais
# =============================================================================

class TestOperationResultEdgeCases:
    """Edge cases that test actual program limits."""

    def test_from_json_with_invalid_json_raises(self):
        """MUST raise JSONDecodeError on invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            OperationResult.from_json("not valid json")

    def test_from_json_with_empty_string_raises(self):
        """MUST raise on empty string."""
        with pytest.raises(json.JSONDecodeError):
            OperationResult.from_json("")

    def test_ok_with_non_serializable_data(self):
        """Test ok() with non-JSON-serializable data (like a set)."""
        result = OperationResult.ok({1, 2, 3})  # set is not JSON serializable
        
        # Should create result, but to_json() should fail
        assert result.success is True
        with pytest.raises(TypeError):
            result.to_json()

    def test_to_json_with_circular_reference(self):
        """Test to_json() with circular reference - MUST fail."""
        data = {"key": "value"}
        data["self"] = data  # circular reference
        result = OperationResult.ok(data)
        
        with pytest.raises(ValueError):
            result.to_json()

    def test_from_json_missing_success_field(self):
        """Test from_json() with missing 'success' field defaults to False."""
        json_str = '{"data": "some data"}'
        result = OperationResult.from_json(json_str)
        
        # Should default to success=False, not raise
        assert result.success is False

    def test_parse_subprocess_output_with_multiple_json_lines(self):
        """Test parse_subprocess_output picks LAST JSON line."""
        output = '''[INFO] Starting...
{"success": false, "error": "first error"}
[INFO] Retrying...
{"success": true, "data": "final result"}'''
        result = parse_subprocess_output(output)
        
        # Should get the LAST JSON, not the first
        assert result.success is True
        assert result.data == "final result"

    def test_parse_subprocess_output_with_malformed_json_in_middle(self):
        """Test parse_subprocess_output skips malformed JSON."""
        output = '''[INFO] Log line
{"broken json
{"success": true, "data": "valid"}'''
        result = parse_subprocess_output(output)
        
        assert result.success is True
        assert result.data == "valid"

    def test_very_large_data(self):
        """Test with very large data to check memory/performance limits."""
        large_list = list(range(10000))
        result = OperationResult.ok(large_list)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert len(parsed["data"]) == 10000
        assert parsed["data"][9999] == 9999

    def test_deeply_nested_data(self):
        """Test with deeply nested structure."""
        nested = {"level": 0}
        current = nested
        for i in range(50):
            current["child"] = {"level": i + 1}
            current = current["child"]
        
        result = OperationResult.ok(nested)
        json_str = result.to_json()
        
        # Should serialize without stack overflow
        assert "level" in json_str

    def test_special_characters_in_error(self):
        """Test error messages with special characters."""
        special_error = 'Error: path "C:\\Users\\Test" not found\nLine 2: <html>'
        result = OperationResult.fail(special_error)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        # JSON must properly escape these
        assert "C:\\\\Users" in json_str or "C:\\Users" in parsed["error"]


class TestExceptionEdgeCases:
    """Test exception classes with edge cases."""

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        from dou_snaptrack.utils.exceptions import DouSnapTrackError
        
        exc = DouSnapTrackError("")
        assert str(exc) == ""

    def test_exception_with_none_details(self):
        """Test exception with None in details dict."""
        from dou_snaptrack.utils.exceptions import DouSnapTrackError
        
        exc = DouSnapTrackError("msg", details={"key": None})
        # Should not crash when converting to string
        str_repr = str(exc)
        assert "msg" in str_repr


class TestBrowserFactoryEdgeCases:
    """Test browser factory with edge cases."""

    def test_config_with_zero_timeout(self):
        """Test BrowserConfig with zero timeout."""
        from dou_snaptrack.utils.browser_factory import BrowserConfig
        
        config = BrowserConfig(timeout=0)
        assert config.timeout == 0  # Should allow zero (immediate timeout)

    def test_config_with_negative_timeout(self):
        """Test BrowserConfig with negative timeout - should allow (Playwright handles)."""
        from dou_snaptrack.utils.browser_factory import BrowserConfig
        
        config = BrowserConfig(timeout=-1)
        assert config.timeout == -1  # Playwright uses -1 for no timeout


class TestConstantsEdgeCases:
    """Test that constants are within expected ranges."""

    def test_timeout_constants_reasonable_range(self):
        """Timeouts should be between 1ms and 15 minutes."""
        from dou_snaptrack import constants
        
        timeouts = [
            constants.TIMEOUT_PAGE_DEFAULT,
            constants.TIMEOUT_PAGE_LONG,
            constants.TIMEOUT_ELEMENT_DEFAULT,
            constants.TIMEOUT_ELEMENT_SHORT,
            constants.TIMEOUT_NAVIGATION,
        ]
        
        for t in timeouts:
            assert 1 <= t <= 900_000, f"Timeout {t} out of reasonable range (1ms to 15min)"

    def test_cache_ttl_not_negative(self):
        """Cache TTLs must be positive."""
        from dou_snaptrack import constants
        
        ttls = [
            constants.CACHE_TTL_SHORT,
            constants.CACHE_TTL_MEDIUM,
            constants.CACHE_TTL_LONG,
        ]
        
        for ttl in ttls:
            assert ttl > 0, f"Cache TTL {ttl} must be positive"

    def test_subprocess_timeout_reasonable(self):
        """Subprocess timeout should not exceed 30 minutes."""
        from dou_snaptrack import constants
        
        assert constants.TIMEOUT_SUBPROCESS_LONG <= 1800, "Subprocess timeout > 30min is unreasonable"
