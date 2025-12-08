"""Helper functions for robust option selection.

This module contains extracted functions from select_option_robust to reduce complexity.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any


def select_native_by_type(root_handle, key: str, key_type: str, page) -> bool:
    """Select option in native select by key type.
    
    Args:
        root_handle: Element handle for select
        key: Value to select
        key_type: Type of selection ("value", "dataIndex")
        page: Playwright page
        
    Returns:
        True if selection succeeded
    """
    if key_type == "value":
        try:
            root_handle.select_option(value=str(key))
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
        except Exception:
            pass
    
    if key_type == "dataIndex":
        try:
            root_handle.select_option(index=int(key))
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
        except Exception:
            pass
    
    return False


def select_native_by_scan(root_handle, key: str, key_type: str, opts: list[dict[str, Any]], page, match_fn) -> bool:
    """Select option in native select by scanning options.
    
    Args:
        root_handle: Element handle for select
        key: Value to select
        key_type: Type of selection
        opts: List of option dictionaries
        page: Playwright page
        match_fn: Function to match option
        
    Returns:
        True if selection succeeded
    """
    target = match_fn(opts, str(key), key_type)
    if target is None:
        return False
    
    try:
        if key_type == "text":
            root_handle.select_option(label=target.get("text") or "")
        elif target.get("value") not in (None, ""):
            root_handle.select_option(value=str(target.get("value")))
        else:
            root_handle.select_option(index=int(target.get("dataIndex") or 0))
        page.wait_for_load_state("networkidle", timeout=60_000)
        return True
    except Exception:
        pass
    
    return False


def try_click_option_exact(page, name: str) -> bool:
    """Try to click option by exact name match.
    
    Args:
        page: Playwright page
        name: Option name to match
        
    Returns:
        True if click succeeded
    """
    try:
        opt = page.get_by_role("option", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4_000)
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    return False


def try_click_option_contains(page, name: str) -> bool:
    """Try to click option by contains match.
    
    Args:
        page: Playwright page
        name: Option name to match
        
    Returns:
        True if click succeeded
    """
    try:
        opt = page.get_by_role("option", name=re.compile(re.escape(name), re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4_000)
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    return False


def close_dropdown(page) -> None:
    """Close dropdown by pressing Escape.
    
    Args:
        page: Playwright page
    """
    with contextlib.suppress(Exception):
        page.keyboard.press("Escape")
