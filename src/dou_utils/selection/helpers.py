"""
Synchronous selection helper functions.

Provides robust option selection for both native <select> and custom dropdowns.
"""
from __future__ import annotations

import time
from typing import Any

from .constants import SENTINELA_PREFIX

# Import dropdown utilities with fallback
try:
    from dou_utils.dropdowns import (
        collect_open_list_options,
        is_select as _is_native_select,
        open_dropdown_robust,
        read_select_options as _read_select_options_sync,
    )
except ImportError:
    # Minimal fallback implementations
    def _is_native_select(handle) -> bool:
        try:
            tag = handle.evaluate("el => el && el.tagName && el.tagName.toLowerCase()")
            return tag == "select"
        except Exception:
            return False

    def _read_select_options_sync(handle) -> list[dict[str, Any]]:
        try:
            return handle.evaluate("""
                el => Array.from(el.options || []).map((o,i) => ({
                    text: (o.textContent || '').trim(),
                    value: o.value,
                    dataValue: o.getAttribute('data-value'),
                    dataIndex: i
                }))
            """) or []
        except Exception:
            return []

    def open_dropdown_robust(frame, locator, strategy_order=None, delay_ms: int = 120) -> bool:
        try:
            locator.click(timeout=2000)
            frame.wait_for_timeout(delay_ms)
            return True
        except Exception:
            return False

    def collect_open_list_options(frame) -> list[dict[str, Any]]:
        return []


def is_sentinel(value: str | None, label: str | None) -> bool:
    """Check if value/label represents a placeholder sentinel.

    Args:
        value: Option value
        label: Option label/text

    Returns:
        True if this is a sentinel (placeholder) option
    """
    v = (value or "").strip().lower()
    lbl = (label or "").strip().lower()
    if not v and not lbl:
        return True
    return bool(lbl.startswith(SENTINELA_PREFIX) or v.startswith(SENTINELA_PREFIX))


def read_rich_options(frame, root_handle) -> list[dict[str, Any]]:
    """Return a list of option dicts for either native <select> or custom dropdowns.

    Args:
        frame: Playwright frame context
        root_handle: Element handle for the dropdown root

    Returns:
        List of option dictionaries
    """
    if not root_handle:
        return []
    if _is_native_select(root_handle):
        return _read_select_options_sync(root_handle)
    opened = open_dropdown_robust(frame, root_handle)
    return collect_open_list_options(frame) if opened else []


def _match_option(options: list[dict[str, Any]], key: str, key_type: str) -> dict[str, Any] | None:
    """Find an option matching the given key and type.

    Args:
        options: List of option dictionaries
        key: Value to match
        key_type: Which field to match ("text", "value", "dataValue", "dataIndex")

    Returns:
        Matching option dict or None
    """
    if key is None:
        return None
    k = str(key)
    kt = (key_type or "text")
    for o in options:
        if kt == "text" and (o.get("text") or "") == k:
            return o
        if kt == "value" and str(o.get("value")) == k:
            return o
        if kt == "dataValue" and str(o.get("dataValue")) == k:
            return o
        if kt == "dataIndex" and str(o.get("dataIndex")) == k:
            return o
    return None


def select_option_robust(frame, root_handle, key: str | None, key_type: str | None) -> bool:
    """Select an option by key/key_type on either native select or custom dropdown.

    Args:
        frame: Playwright frame context
        root_handle: Element handle for the dropdown
        key: Value to select by
        key_type: How to match ("text", "value", "dataValue", "dataIndex")

    Returns:
        True when selection happened and the page stabilized
    """
    from .robust_helpers import (
        close_dropdown,
        select_native_by_scan,
        select_native_by_type,
        try_click_option_contains,
        try_click_option_exact,
    )

    if not root_handle or key is None or key_type is None:
        return False
    page = frame.page

    if _is_native_select(root_handle):
        # Try direct selection by type
        if select_native_by_type(root_handle, str(key), key_type, page):
            return True

        # Fallback via options scan
        opts = _read_select_options_sync(root_handle)
        return select_native_by_scan(root_handle, str(key), key_type, opts, page, _match_option)

    # Custom dropdown
    if not open_dropdown_robust(frame, root_handle):
        return False

    options = collect_open_list_options(frame)
    target = _match_option(options, str(key), key_type or "text")
    name = (target or {}).get("text") or str(key)

    # Try exact match first, then contains
    if try_click_option_exact(page, name):
        return True
    if try_click_option_contains(page, name):
        return True

    close_dropdown(page)
    return False


def wait_repopulation(
    frame,
    root_handle,
    prev_count: int,
    timeout_ms: int = 15_000,
    poll_interval_ms: int = 250
) -> None:
    """Wait until the number of options for the target dropdown changes.

    Used after selecting a parent dropdown to wait for child dropdown to repopulate.

    Args:
        frame: Playwright frame context
        root_handle: Element handle for the dropdown to monitor
        prev_count: Previous option count
        timeout_ms: Maximum time to wait
        poll_interval_ms: Polling interval
    """
    page = frame.page
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            if _is_native_select(root_handle):
                cur = len(_read_select_options_sync(root_handle))
            else:
                open_dropdown_robust(frame, root_handle)
                cur = len(collect_open_list_options(frame))
            if cur != prev_count and cur > 0:
                return
        except Exception:
            pass
        try:
            page.wait_for_timeout(poll_interval_ms)
        except Exception:
            time.sleep(poll_interval_ms / 1000.0)
