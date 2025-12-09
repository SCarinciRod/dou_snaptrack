"""Worker process helpers for batch execution.

This module contains extracted functions from _worker_process to reduce complexity.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Any

from ...constants import TIMEOUT_PAGE_DEFAULT


def setup_asyncio_for_windows() -> None:
    """Configure asyncio event loop for Windows platform."""
    try:
        import asyncio as _asyncio
        import sys as _sys

        if _sys.platform.startswith("win"):
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
            _asyncio.set_event_loop(_asyncio.new_event_loop())
    except Exception:
        pass


def setup_worker_logging(payload: dict[str, Any]) -> Any:
    """Set up logging redirection for worker process.

    Args:
        payload: Worker payload containing log_file path

    Returns:
        File handle for log file or None
    """
    _log_fp = None
    try:
        log_file = payload.get("log_file")
        # Avoid redirecting stdout when running inline (thread) in main process
        import multiprocessing as _mp

        is_main_proc = _mp.current_process().name == "MainProcess"
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            _log_fp = open(log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
            if not is_main_proc:
                sys.stdout = _log_fp  # type: ignore
                sys.stderr = _log_fp  # type: ignore
            print(f"[Worker {os.getpid()}] logging to {log_file}")
    except Exception:
        _log_fp = None
    return _log_fp


def get_browser_channels(prefer_edge: bool) -> tuple[str, ...]:
    """Get browser channel preferences.

    Args:
        prefer_edge: Whether to prefer Edge over Chrome

    Returns:
        Tuple of channel names in order of preference
    """
    return ("msedge", "chrome") if prefer_edge else ("chrome", "msedge")


def get_fallback_browser_paths(prefer_edge: bool) -> tuple[str, ...]:
    """Get fallback browser executable paths.

    Args:
        prefer_edge: Whether to prefer Edge over Chrome

    Returns:
        Tuple of executable paths in order of preference
    """
    if prefer_edge:
        return (
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        )
    else:
        return (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        )


def launch_browser_with_fallback(playwright, prefer_edge: bool, launch_opts: dict[str, Any]) -> Any:
    """Launch browser with fallback strategies.

    Args:
        playwright: Playwright instance
        prefer_edge: Whether to prefer Edge over Chrome
        launch_opts: Launch options dictionary

    Returns:
        Browser instance
    """
    # Try channels first
    channels = get_browser_channels(prefer_edge)
    browser = None
    for ch in channels:
        try:
            browser = playwright.chromium.launch(channel=ch, **launch_opts)
            break
        except Exception:
            browser = None

    if browser is not None:
        return browser

    # Fallback to explicit executable paths
    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if not exe:
        for path in get_fallback_browser_paths(prefer_edge):
            if Path(path).exists():
                exe = path
                break

    if exe:
        try:
            return playwright.chromium.launch(executable_path=exe, **launch_opts)
        except Exception:
            return playwright.chromium.launch(**launch_opts)
    else:
        return playwright.chromium.launch(**launch_opts)


def create_route_blocker():
    """Create a route blocking function for heavy resources.

    Returns:
        Function that can be used with context.route()
    """

    def _route_block_heavy(route):
        try:
            req = route.request
            rtype = getattr(req, "resource_type", lambda: "")()
            if rtype in ("image", "media", "font"):
                return route.abort()

            url = req.url
            ul = url.lower()

            # Block common static heavy types
            if any(
                ul.endswith(ext)
                for ext in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".mp4",
                    ".mp3",
                    ".avi",
                    ".mov",
                    ".woff",
                    ".woff2",
                    ".ttf",
                    ".otf",
                )
            ):
                return route.abort()

            # Block trackers and analytics
            if any(
                host in ul
                for host in (
                    "googletagmanager.com",
                    "google-analytics.com",
                    "doubleclick.net",
                    "hotjar.com",
                    "facebook.com/tr",
                    "stats.g.doubleclick.net",
                )
            ):
                return route.abort()
        except Exception:
            pass
        return route.continue_()

    return _route_block_heavy


def setup_browser_context(browser, block_resources: bool = True) -> Any:
    """Set up browser context with resource blocking.

    Args:
        browser: Browser instance
        block_resources: Whether to block heavy resources

    Returns:
        Browser context
    """
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1024, "height": 768})

    if block_resources:
        try:
            context.route("**/*", create_route_blocker())
        except Exception:
            pass

    return context


def extract_job_parameters(job: dict[str, Any], defaults: dict[str, Any], job_index: int) -> dict[str, Any]:
    """Extract and validate job parameters.

    Args:
        job: Job configuration
        defaults: Default configuration
        job_index: Job index in batch

    Returns:
        Dictionary of extracted parameters
    """

    def _get(key, default_key=None, default_value=None):
        if default_key is None:
            default_key = key
        return job.get(key, defaults.get(default_key, default_value))

    return {
        "data": job.get("data"),
        "secao": job.get("secao", defaults.get("secaoDefault", "DO1")),
        "key1_type": job.get("key1_type") or defaults.get("key1_type") or "text",
        "key1": job.get("key1"),
        "key2_type": job.get("key2_type") or defaults.get("key2_type") or "text",
        "key2": job.get("key2"),
        "label1": job.get("label1"),
        "label2": job.get("label2"),
        "max_links": int(_get("max_links", "max_links", 30) or 30),
        "do_scrape_detail": bool(_get("scrape_detail", "scrape_detail", True)),
        "detail_timeout": int(_get("detail_timeout", "detail_timeout", 60_000) or 60_000),
        "fallback_date": bool(_get("fallback_date_if_missing", "fallback_date_if_missing", True)),
        "max_scrolls": int(_get("max_scrolls", "max_scrolls", 20) or 20),
        "scroll_pause_ms": int(_get("scroll_pause_ms", "scroll_pause_ms", 150) or 150),
        "stable_rounds": int(_get("stable_rounds", "stable_rounds", 1) or 1),
        "detail_parallel": int(_get("detail_parallel", "detail_parallel", 1) or 1),
        "bulletin": job.get("bulletin") or defaults.get("bulletin"),
        "bulletin_out_pat": job.get("bulletin_out") or defaults.get("bulletin_out") or None,
        "repeat_delay_ms": int(job.get("repeat_delay_ms", defaults.get("repeat_delay_ms", 0))),
    }


def apply_fast_mode_optimizations(params: dict[str, Any]) -> None:
    """Apply fast mode optimizations to job parameters.

    Args:
        params: Job parameters dictionary (modified in place)
    """
    params["max_scrolls"] = min(params["max_scrolls"], 15)
    params["scroll_pause_ms"] = min(params["scroll_pause_ms"], 150)
    params["stable_rounds"] = min(params["stable_rounds"], 1)
    params["do_scrape_detail"] = False
    params["bulletin"] = None
    params["bulletin_out_pat"] = None


def get_or_create_page(page_cache: dict[tuple[str, str], Any], context, data: str, secao: str) -> tuple[Any, bool]:
    """Get cached page or create new one.

    Args:
        page_cache: Cache dictionary
        context: Browser context
        data: Date string
        secao: Section string

    Returns:
        Tuple of (page, keep_open_flag)
    """
    k = (str(data), str(secao))
    page = page_cache.get(k)

    if page is None:
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_PAGE_DEFAULT)
        page.set_default_navigation_timeout(TIMEOUT_PAGE_DEFAULT)
        page_cache[k] = page

    return page, True


def cleanup_page_cache(page_cache: dict[tuple[str, str], Any]) -> None:
    """Close all cached pages.

    Args:
        page_cache: Cache dictionary
    """
    for p in page_cache.values():
        with contextlib.suppress(Exception):
            p.close()


def recreate_page_after_failure(
    page_cache: dict[tuple[str, str], Any], context, cur_page, data: str, secao: str
) -> Any:
    """Recreate page after failure.

    Args:
        page_cache: Cache dictionary
        context: Browser context
        cur_page: Current (broken) page
        data: Date string
        secao: Section string

    Returns:
        New page instance
    """
    # Drop broken page
    with contextlib.suppress(Exception):
        if cur_page:
            cur_page.close()

    # Create new page
    new_page = context.new_page()
    new_page.set_default_timeout(TIMEOUT_PAGE_DEFAULT)
    new_page.set_default_navigation_timeout(TIMEOUT_PAGE_DEFAULT)
    page_cache[(str(data), str(secao))] = new_page

    return new_page
