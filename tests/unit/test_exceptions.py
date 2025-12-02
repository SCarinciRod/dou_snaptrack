"""Unit tests for dou_snaptrack.utils.exceptions module.

Tests for custom exception hierarchy.
"""
import pytest
from dou_snaptrack.utils.exceptions import (
    DouSnapTrackError,
    BrowserError,
    BrowserNotFoundError,
    BrowserLaunchError,
    ScrapingError,
    ElementNotFoundError,
    PageLoadError,
    DropdownError,
    NetworkError,
    TimeoutError as DouTimeoutError,
    ConnectionError as DouConnectionError,
    DataError,
    ValidationError,
    ParseError,
    SubprocessError,
    wrap_playwright_error,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_browser_error_inherits_from_base(self):
        """Test BrowserError inherits from DouSnapTrackError."""
        assert issubclass(BrowserError, DouSnapTrackError)

    def test_browser_not_found_inherits_from_browser_error(self):
        """Test BrowserNotFoundError inherits from BrowserError."""
        assert issubclass(BrowserNotFoundError, BrowserError)
        assert issubclass(BrowserNotFoundError, DouSnapTrackError)

    def test_browser_launch_error_inherits_from_browser_error(self):
        """Test BrowserLaunchError inherits from BrowserError."""
        assert issubclass(BrowserLaunchError, BrowserError)

    def test_scraping_error_inherits_from_base(self):
        """Test ScrapingError inherits from DouSnapTrackError."""
        assert issubclass(ScrapingError, DouSnapTrackError)

    def test_element_not_found_inherits_from_scraping_error(self):
        """Test ElementNotFoundError inherits from ScrapingError."""
        assert issubclass(ElementNotFoundError, ScrapingError)

    def test_page_load_error_inherits_from_scraping_error(self):
        """Test PageLoadError inherits from ScrapingError."""
        assert issubclass(PageLoadError, ScrapingError)

    def test_dropdown_error_inherits_from_scraping_error(self):
        """Test DropdownError inherits from ScrapingError."""
        assert issubclass(DropdownError, ScrapingError)

    def test_network_error_inherits_from_base(self):
        """Test NetworkError inherits from DouSnapTrackError."""
        assert issubclass(NetworkError, DouSnapTrackError)

    def test_timeout_error_inherits_from_network_error(self):
        """Test TimeoutError inherits from NetworkError."""
        assert issubclass(DouTimeoutError, NetworkError)

    def test_connection_error_inherits_from_network_error(self):
        """Test ConnectionError inherits from NetworkError."""
        assert issubclass(DouConnectionError, NetworkError)

    def test_data_error_inherits_from_base(self):
        """Test DataError inherits from DouSnapTrackError."""
        assert issubclass(DataError, DouSnapTrackError)

    def test_validation_error_inherits_from_data_error(self):
        """Test ValidationError inherits from DataError."""
        assert issubclass(ValidationError, DataError)

    def test_parse_error_inherits_from_data_error(self):
        """Test ParseError inherits from DataError."""
        assert issubclass(ParseError, DataError)

    def test_subprocess_error_inherits_from_base(self):
        """Test SubprocessError inherits from DouSnapTrackError."""
        assert issubclass(SubprocessError, DouSnapTrackError)

    def test_all_inherit_from_python_exception(self):
        """Test all custom exceptions inherit from Python's Exception."""
        exceptions = [
            DouSnapTrackError, BrowserError, BrowserNotFoundError, BrowserLaunchError,
            ScrapingError, ElementNotFoundError, PageLoadError, DropdownError,
            NetworkError, DouTimeoutError, DouConnectionError,
            DataError, ValidationError, ParseError, SubprocessError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, Exception)
            assert not issubclass(exc_class, BaseException) or issubclass(exc_class, Exception)


class TestExceptionConstruction:
    """Tests for exception construction and messages."""

    def test_base_exception_with_message(self):
        """Test DouSnapTrackError accepts message."""
        exc = DouSnapTrackError("Base error message")
        assert "Base error message" in str(exc)

    def test_browser_not_found_default_message(self):
        """Test BrowserNotFoundError with default message."""
        exc = BrowserNotFoundError()
        assert "browser" in str(exc).lower()

    def test_element_not_found_with_selector(self):
        """Test ElementNotFoundError with selector info."""
        exc = ElementNotFoundError("#slcOrgs")
        assert "#slcOrgs" in str(exc)

    def test_page_load_error_with_url(self):
        """Test PageLoadError with URL."""
        exc = PageLoadError("http://example.com", "timeout")
        assert "example.com" in str(exc)

    def test_timeout_with_duration(self):
        """Test TimeoutError with timeout info."""
        exc = DouTimeoutError("navigation", 30000)
        assert "30000" in str(exc)

    def test_connection_error_with_url(self):
        """Test ConnectionError with URL."""
        exc = DouConnectionError("http://example.com", "refused")
        assert "example.com" in str(exc)

    def test_validation_error_with_field(self):
        """Test ValidationError with field info."""
        exc = ValidationError("date", "invalid", "DD-MM-YYYY")
        assert "date" in str(exc)

    def test_parse_error_with_type(self):
        """Test ParseError with data type."""
        exc = ParseError("JSON", "syntax error")
        assert "JSON" in str(exc)

    def test_subprocess_error_with_exit_code(self):
        """Test SubprocessError with exit code."""
        exc = SubprocessError("python script.py", 1, "error output")
        assert "1" in str(exc)


class TestExceptionCatching:
    """Tests for catching exceptions at different levels."""

    def test_catch_specific_browser_error(self):
        """Test catching specific BrowserNotFoundError."""
        with pytest.raises(BrowserNotFoundError):
            raise BrowserNotFoundError("Chrome not installed")

    def test_catch_browser_error_catches_children(self):
        """Test catching BrowserError catches BrowserNotFoundError."""
        with pytest.raises(BrowserError):
            raise BrowserNotFoundError("Chrome not installed")

    def test_catch_base_catches_all(self):
        """Test catching DouSnapTrackError catches all custom exceptions."""
        with pytest.raises(DouSnapTrackError):
            raise BrowserNotFoundError("Chrome not installed")

        with pytest.raises(DouSnapTrackError):
            raise ElementNotFoundError("Selector not found")

        with pytest.raises(DouSnapTrackError):
            raise DouTimeoutError("op", 1000)

    def test_catch_scraping_error_catches_children(self):
        """Test catching ScrapingError catches ElementNotFoundError."""
        with pytest.raises(ScrapingError):
            raise ElementNotFoundError("#dropdown")

        with pytest.raises(ScrapingError):
            raise PageLoadError("http://example.com")

    def test_catch_network_error_catches_children(self):
        """Test catching NetworkError catches TimeoutError and ConnectionError."""
        with pytest.raises(NetworkError):
            raise DouTimeoutError("op", 1000)

        with pytest.raises(NetworkError):
            raise DouConnectionError("http://example.com")

    def test_catch_data_error_catches_children(self):
        """Test catching DataError catches ValidationError and ParseError."""
        with pytest.raises(DataError):
            raise ValidationError("field", "value")

        with pytest.raises(DataError):
            raise ParseError("JSON")


class TestExceptionNotCatching:
    """Tests to ensure exceptions don't catch unrelated types."""

    def test_browser_error_not_catches_scraping(self):
        """Test BrowserError doesn't catch ScrapingError."""
        with pytest.raises(ScrapingError):
            try:
                raise ElementNotFoundError("#selector")
            except BrowserError:
                pytest.fail("BrowserError should not catch ScrapingError")

    def test_network_error_not_catches_data_error(self):
        """Test NetworkError doesn't catch DataError."""
        with pytest.raises(DataError):
            try:
                raise ParseError("json")
            except NetworkError:
                pytest.fail("NetworkError should not catch DataError")

    def test_custom_not_catches_builtin(self):
        """Test custom exceptions don't catch unrelated builtin exceptions."""
        with pytest.raises(ValueError):
            try:
                raise ValueError("builtin error")
            except DouSnapTrackError:
                pytest.fail("DouSnapTrackError should not catch ValueError")


class TestWrapPlaywrightError:
    """Tests for wrap_playwright_error helper."""

    def test_timeout_error_wrapped(self):
        """Test timeout errors are wrapped correctly."""
        error = Exception("Timeout 30000ms exceeded")
        wrapped = wrap_playwright_error(error, "loading page")
        
        assert isinstance(wrapped, DouTimeoutError)

    def test_connection_error_wrapped(self):
        """Test connection errors are wrapped correctly."""
        error = Exception("net::ERR_CONNECTION_REFUSED")
        wrapped = wrap_playwright_error(error, "http://example.com")
        
        assert isinstance(wrapped, DouConnectionError)

    def test_selector_error_wrapped(self):
        """Test selector errors are wrapped correctly."""
        error = Exception("Selector '#missing' not found")
        wrapped = wrap_playwright_error(error, "#missing")
        
        assert isinstance(wrapped, ElementNotFoundError)

    def test_unknown_error_wrapped_as_scraping(self):
        """Test unknown errors are wrapped as ScrapingError."""
        error = Exception("Unknown error occurred")
        wrapped = wrap_playwright_error(error, "some operation")
        
        assert isinstance(wrapped, ScrapingError)

    def test_wrap_preserves_original_message(self):
        """Test wrapped exception contains original message."""
        original_msg = "Very specific error message XYZ123"
        error = Exception(original_msg)
        wrapped = wrap_playwright_error(error, "context")
        
        # Original message should be somewhere in the wrapped exception
        assert "XYZ123" in str(wrapped) or "context" in str(wrapped)


# =============================================================================
# EDGE CASES AND STRESS TESTS
# =============================================================================


class TestExceptionEdgeCases:
    """Edge cases that test exception limits."""

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        exc = DouSnapTrackError("")
        assert str(exc) == ""

    def test_exception_with_none_details(self):
        """Test exception with None in details dict."""
        exc = DouSnapTrackError("msg", details={"key": None})
        str_repr = str(exc)
        assert "msg" in str_repr

    def test_exception_with_very_long_message(self):
        """Test exception with extremely long message."""
        long_msg = "E" * 100_000
        exc = DouSnapTrackError(long_msg)
        
        # Should not truncate
        assert len(str(exc)) >= 100_000

    def test_exception_with_unicode_message(self):
        """Test exception with Unicode characters."""
        unicode_msg = "Erro: ação não encontrada 中文 🔥"
        exc = DouSnapTrackError(unicode_msg)
        
        assert "中文" in str(exc)
        assert "🔥" in str(exc)

    def test_exception_with_newlines(self):
        """Test exception with newlines in message."""
        msg = "Line 1\nLine 2\nLine 3"
        exc = DouSnapTrackError(msg)
        
        assert "\n" in str(exc)

    def test_exception_details_large_dict(self):
        """Test exception with large details dict."""
        large_details = {f"key_{i}": f"value_{i}" for i in range(1000)}
        exc = DouSnapTrackError("msg", details=large_details)
        
        # Should handle large dict without crashing
        str_repr = str(exc)
        assert "msg" in str_repr

    def test_subprocess_error_truncates_stderr(self):
        """Test SubprocessError truncates very long stderr."""
        long_stderr = "E" * 10_000
        exc = SubprocessError("cmd", 1, long_stderr)
        
        # Message should be reasonable length (stderr truncated to 500)
        assert len(str(exc)) < 10_000


class TestExceptionChaining:
    """Test exception chaining and __cause__."""

    def test_exception_chaining_preserves_cause(self):
        """Test 'from' clause preserves original exception."""
        original = ValueError("Original error")
        try:
            try:
                raise original
            except ValueError as e:
                raise BrowserLaunchError("Launch failed") from e
        except BrowserLaunchError as e:
            assert e.__cause__ is original

    def test_exception_chaining_multiple_levels(self):
        """Test multi-level exception chaining."""
        level1 = ValueError("Level 1")
        try:
            try:
                try:
                    raise level1
                except ValueError:
                    raise BrowserError("Level 2") from level1
            except BrowserError as e:
                raise DouSnapTrackError("Level 3") from e
        except DouSnapTrackError as e:
            assert e.__cause__.__cause__ is level1


class TestExceptionAttributeAccess:
    """Test exception attribute access edge cases."""

    def test_page_load_error_has_url_attribute(self):
        """Test PageLoadError stores URL as attribute."""
        exc = PageLoadError("http://example.com/path", "reason")
        assert hasattr(exc, "url")
        assert exc.url == "http://example.com/path"

    def test_element_not_found_has_selector_attribute(self):
        """Test ElementNotFoundError stores selector as attribute."""
        exc = ElementNotFoundError("#my-selector")
        assert hasattr(exc, "selector")
        assert exc.selector == "#my-selector"

    def test_timeout_error_has_timeout_ms_attribute(self):
        """Test TimeoutError stores timeout_ms as attribute."""
        exc = DouTimeoutError("operation", 5000)
        assert hasattr(exc, "timeout_ms")
        assert exc.timeout_ms == 5000

    def test_subprocess_error_has_exit_code_attribute(self):
        """Test SubprocessError stores exit_code as attribute."""
        exc = SubprocessError("cmd", 42, "")
        assert hasattr(exc, "exit_code")
        assert exc.exit_code == 42

    def test_connection_error_has_url_attribute(self):
        """Test ConnectionError stores URL as attribute."""
        exc = DouConnectionError("http://example.com")
        assert hasattr(exc, "url")
        assert exc.url == "http://example.com"


class TestWrapPlaywrightErrorEdgeCases:
    """Edge cases for wrap_playwright_error."""

    def test_wrap_with_empty_error_message(self):
        """Test wrapping exception with empty message."""
        error = Exception("")
        wrapped = wrap_playwright_error(error, "context")
        
        assert isinstance(wrapped, ScrapingError)

    def test_wrap_with_none_context(self):
        """Test wrapping with no context provided."""
        error = Exception("Timeout 30000ms exceeded")
        wrapped = wrap_playwright_error(error)
        
        assert isinstance(wrapped, DouTimeoutError)

    def test_wrap_with_empty_context(self):
        """Test wrapping with empty context."""
        error = Exception("Timeout 30000ms exceeded")
        wrapped = wrap_playwright_error(error, "")
        
        assert isinstance(wrapped, DouTimeoutError)

    def test_wrap_case_insensitivity(self):
        """Test error detection is case-insensitive."""
        # Different cases should all be detected
        timeout_variants = [
            "TIMEOUT 30000ms",
            "Timeout error",
            "timeout exceeded",
            "TimeOut occurred",
        ]
        
        for msg in timeout_variants:
            error = Exception(msg)
            wrapped = wrap_playwright_error(error)
            assert isinstance(wrapped, DouTimeoutError), f"Failed for: {msg}"

    def test_wrap_connection_variants(self):
        """Test various connection error formats are detected."""
        connection_variants = [
            "net::ERR_CONNECTION_REFUSED",
            "net::ERR_NAME_NOT_RESOLVED",
            "connection refused",
            "Connection reset",
            "NET::ERR_FAILED",
        ]
        
        for msg in connection_variants:
            error = Exception(msg)
            wrapped = wrap_playwright_error(error)
            assert isinstance(wrapped, DouConnectionError), f"Failed for: {msg}"

    def test_wrap_locator_variants(self):
        """Test various locator/selector error formats."""
        selector_variants = [
            "Selector '#test' not found",
            "Locator failed",
            "selector resolution failed",
            "LOCATOR timeout",
        ]
        
        for msg in selector_variants:
            error = Exception(msg)
            wrapped = wrap_playwright_error(error)
            assert isinstance(wrapped, ElementNotFoundError), f"Failed for: {msg}"


class TestExceptionPickling:
    """Test that exceptions can be pickled (important for multiprocessing)."""

    def test_base_exception_picklable(self):
        """Test DouSnapTrackError can be pickled."""
        import pickle
        
        exc = DouSnapTrackError("test message", details={"key": "value"})
        pickled = pickle.dumps(exc)
        unpickled = pickle.loads(pickled)
        
        assert str(unpickled) == str(exc)
        assert unpickled.message == exc.message

    def test_subclass_exception_picklable(self):
        """Test subclass exceptions can be pickled."""
        import pickle
        
        exceptions_to_test = [
            BrowserNotFoundError("test"),
            PageLoadError("http://example.com", "reason"),
            DouTimeoutError("operation", 5000),
            SubprocessError("cmd", 1, "stderr"),
        ]
        
        for exc in exceptions_to_test:
            pickled = pickle.dumps(exc)
            unpickled = pickle.loads(pickled)
            assert type(unpickled) == type(exc)
