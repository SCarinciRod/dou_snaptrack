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
