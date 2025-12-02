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


class TestOperationResultMutability:
    """Test mutability and side effects - these often hide bugs."""

    def test_data_mutation_after_creation(self):
        """Test that mutating data after creation affects result."""
        original_data = {"items": [1, 2, 3]}
        result = OperationResult.ok(original_data)
        
        # Mutate the original - this SHOULD affect result (no deep copy)
        original_data["items"].append(4)
        
        # Verify mutation is visible (this is expected behavior, but test documents it)
        assert result.data["items"] == [1, 2, 3, 4]

    def test_metadata_mutation(self):
        """Test metadata can be mutated after creation."""
        result = OperationResult.ok({"data": 1}, elapsed_ms=100)
        
        # Mutate metadata
        result.metadata["new_key"] = "new_value"
        
        # Should reflect in to_json
        json_str = result.to_json()
        assert "new_key" in json_str

    def test_from_json_returns_new_instance(self):
        """Verify from_json creates independent instance."""
        json_str = '{"success": true, "data": {"key": "value"}}'
        result1 = OperationResult.from_json(json_str)
        result2 = OperationResult.from_json(json_str)
        
        # Mutate one
        result1.data["key"] = "modified"
        
        # Other should be unaffected
        assert result2.data["key"] == "value"


class TestOperationResultInjection:
    """Test injection attacks and malicious input."""

    def test_json_injection_in_error_message(self):
        """Test that error messages with JSON-like content are escaped."""
        malicious = '{"success": true, "data": "hacked"}'
        result = OperationResult.fail(malicious)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        # Must remain a failure, not be "hacked" to success
        assert parsed["success"] is False
        assert parsed["error"] == malicious

    def test_null_bytes_in_data(self):
        """Test null bytes in data."""
        data_with_null = "before\x00after"
        result = OperationResult.ok({"text": data_with_null})
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        # Null bytes should be preserved or escaped
        assert "\x00" in parsed["data"]["text"] or "\\u0000" in json_str

    def test_unicode_edge_cases(self):
        """Test Unicode edge cases including surrogates."""
        # Various Unicode edge cases
        unicode_data = {
            "emoji": "🔥💯",
            "rtl": "مرحبا",
            "cjk": "中文日本語한국어",
            "math": "∑∫∂",
            "special": "​",  # zero-width space
        }
        result = OperationResult.ok(unicode_data)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["data"]["emoji"] == "🔥💯"
        assert parsed["data"]["rtl"] == "مرحبا"

    def test_very_long_error_message(self):
        """Test extremely long error message."""
        long_error = "E" * 100_000
        result = OperationResult.fail(long_error)
        json_str = result.to_json()
        
        # Should not truncate
        assert len(json_str) > 100_000

    def test_newlines_in_error(self):
        """Test multiline error messages are properly escaped."""
        multiline = "Line 1\nLine 2\rLine 3\r\nLine 4"
        result = OperationResult.fail(multiline)
        json_str = result.to_json()
        
        # JSON should have escaped newlines
        assert "\\n" in json_str or "\\r" in json_str
        
        # Round-trip should preserve content
        parsed = json.loads(json_str)
        assert parsed["error"] == multiline


class TestParseSubprocessStress:
    """Stress tests for parse_subprocess_output."""

    def test_very_long_output(self):
        """Test with very long subprocess output."""
        long_output = "LOG: " * 10000 + '\n{"success": true, "data": "found"}'
        result = parse_subprocess_output(long_output)
        
        assert result.success is True
        assert result.data == "found"

    def test_many_json_lines(self):
        """Test with many JSON lines (should return last)."""
        lines = [f'{{"success": false, "error": "attempt {i}"}}' for i in range(100)]
        lines.append('{"success": true, "data": "final"}')
        output = "\n".join(lines)
        
        result = parse_subprocess_output(output)
        assert result.success is True
        assert result.data == "final"

    def test_json_in_middle_of_line(self):
        """Test JSON embedded in log line (should NOT match)."""
        output = 'DEBUG: response was {"success": true} but continued\n{"success": false, "error": "real"}'
        result = parse_subprocess_output(output)
        
        # Should find the standalone JSON, not embedded one
        assert result.success is False

    def test_empty_output(self):
        """Test empty output."""
        result = parse_subprocess_output("")
        
        assert result.success is False
        assert "Nenhum JSON" in result.error

    def test_only_whitespace(self):
        """Test output with only whitespace."""
        result = parse_subprocess_output("   \n\t\n   ")
        
        assert result.success is False


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

    def test_exception_chaining(self):
        """Test exception chaining preserves cause."""
        from dou_snaptrack.utils.exceptions import BrowserError, BrowserLaunchError
        
        original = ValueError("Original error")
        try:
            try:
                raise original
            except ValueError as e:
                raise BrowserLaunchError("Launch failed") from e
        except BrowserLaunchError as e:
            assert e.__cause__ is original

    def test_wrap_playwright_error_with_empty_string(self):
        """Test wrap_playwright_error with empty error message."""
        from dou_snaptrack.utils.exceptions import wrap_playwright_error, ScrapingError
        
        error = Exception("")
        wrapped = wrap_playwright_error(error, "context")
        
        assert isinstance(wrapped, ScrapingError)

    def test_wrap_playwright_error_with_none_context(self):
        """Test wrap_playwright_error with no context."""
        from dou_snaptrack.utils.exceptions import wrap_playwright_error
        
        error = Exception("Timeout 30000ms exceeded")
        wrapped = wrap_playwright_error(error)  # no context
        
        assert wrapped is not None

    def test_exception_details_special_chars(self):
        """Test exception details with special characters."""
        from dou_snaptrack.utils.exceptions import PageLoadError
        
        exc = PageLoadError("http://example.com/path?query=<script>", "timeout: 'quoted'")
        str_repr = str(exc)
        
        # Should contain URL without crashing
        assert "example.com" in str_repr


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

    def test_config_with_extreme_viewport(self):
        """Test BrowserConfig with extreme viewport sizes."""
        from dou_snaptrack.utils.browser_factory import BrowserConfig
        
        # Very small
        config_small = BrowserConfig(viewport_width=1, viewport_height=1)
        assert config_small.viewport_width == 1
        
        # Very large
        config_large = BrowserConfig(viewport_width=10000, viewport_height=10000)
        assert config_large.viewport_width == 10000

    def test_config_blocked_patterns_mutation(self):
        """Test that blocked_patterns default is not shared between instances."""
        from dou_snaptrack.utils.browser_factory import BrowserConfig
        
        config1 = BrowserConfig()
        config2 = BrowserConfig()
        
        config1.blocked_patterns.append("**/*.test")
        
        # config2 should NOT have the new pattern
        assert "**/*.test" not in config2.blocked_patterns

    def test_find_system_browser_returns_valid_path_or_none(self):
        """Test find_system_browser returns absolute path or None."""
        from dou_snaptrack.utils.browser_factory import find_system_browser
        import os
        
        path = find_system_browser()
        
        if path is not None:
            assert os.path.isabs(path), f"Path {path} should be absolute"
            # Path should exist (since it was returned)
            assert os.path.exists(path), f"Path {path} should exist"


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

    def test_wait_constants_hierarchy(self):
        """Test wait constants have sensible hierarchy."""
        from dou_snaptrack import constants
        
        # Micro < Tiny < Short < Medium < Long
        assert constants.WAIT_MICRO < constants.WAIT_TINY
        assert constants.WAIT_TINY < constants.WAIT_SHORT
        assert constants.WAIT_SHORT < constants.WAIT_MEDIUM
        assert constants.WAIT_MEDIUM < constants.WAIT_LONG

    def test_urls_are_https(self):
        """Test that base URLs use HTTPS."""
        from dou_snaptrack import constants
        
        assert constants.BASE_DOU.startswith("https://")
        assert constants.EAGENDAS_URL.startswith("https://")

    def test_browser_paths_are_absolute(self):
        """Test browser paths are absolute Windows paths."""
        from dou_snaptrack import constants
        import re
        
        for path in constants.CHROME_PATHS + constants.EDGE_PATHS:
            # Should be absolute Windows path
            assert re.match(r'^[A-Z]:\\', path), f"Path {path} should be absolute Windows path"
            assert path.endswith('.exe'), f"Path {path} should end with .exe"
