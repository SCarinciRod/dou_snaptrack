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
    "BatchResult",
    "BrowserError",
    "BrowserLaunchError",
    "BrowserNotFoundError",
    "ConnectionError",
    "DataError",
    # Exceptions
    "DouSnapTrackError",
    "DropdownError",
    "ElementNotFoundError",
    "FetchResult",
    "NetworkError",
    # Responses
    "OperationResult",
    "PageLoadError",
    "ParseError",
    "ScrapingError",
    "SubprocessError",
    "TimeoutError",
    "ValidationError",
    "error_response",
    "parse_subprocess_output",
    "success_response",
    "wrap_playwright_error",
]
