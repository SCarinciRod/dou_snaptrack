# Utils package for dou_snaptrack

from dou_snaptrack.utils.exceptions import (
    BrowserError,
    BrowserLaunchError,
    BrowserNotFoundError,
    ConnectionError,
    DataError,
    DouSnapTrackError,
    DropdownError,
    ElementNotFoundError,
    NetworkError,
    PageLoadError,
    ParseError,
    ScrapingError,
    SubprocessError,
    TimeoutError,
    ValidationError,
    wrap_playwright_error,
)
from dou_snaptrack.utils.responses import (
    BatchResult,
    FetchResult,
    OperationResult,
    error_response,
    parse_subprocess_output,
    success_response,
)

__all__ = [
    # Exceptions
    "DouSnapTrackError",
    "BrowserError",
    "BrowserNotFoundError",
    "BrowserLaunchError",
    "ScrapingError",
    "PageLoadError",
    "ElementNotFoundError",
    "DropdownError",
    "NetworkError",
    "TimeoutError",
    "ConnectionError",
    "DataError",
    "ParseError",
    "ValidationError",
    "SubprocessError",
    "wrap_playwright_error",
    # Responses
    "OperationResult",
    "FetchResult",
    "BatchResult",
    "success_response",
    "error_response",
    "parse_subprocess_output",
]
