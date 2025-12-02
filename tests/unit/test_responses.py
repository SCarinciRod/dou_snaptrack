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
