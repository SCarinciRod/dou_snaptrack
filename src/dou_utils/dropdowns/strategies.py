"""
Robust dropdown opening & option selection strategies.

Provides:
 - open_dropdown_robust(frame, locator, config)
 - collect_open_list_options(frame)

This consolidates heuristics from original scripts (00_map_page, 05_cascade_cli, 00_map_pairs),
maintaining configurable order and logging.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import Any

from dou_utils.log_utils import get_logger

logger = get_logger(__name__)

DEFAULT_OPEN_STRATEGY_ORDER: tuple[str, ...] = (
    "already_open",
    "click",
    "force_click",
    "icon_click",
    "keyboard",
    "double_click",
)

ARROW_XPATH = "xpath=.//*[contains(@class,'arrow') or contains(@class,'icon') or contains(@class,'caret')]"

# Listbox selectors for detecting open dropdowns
LISTBOX_SELECTORS: tuple[str, ...] = (
    "[role=listbox]",
    "ul[role=listbox]",
    "div[role=listbox]",
    "ul[role=menu]",
    "div[role=menu]",
    ".ng-dropdown-panel",
    ".p-dropdown-items",
    ".select2-results__options",
    ".rc-virtual-list",
)

# Option selectors for collecting options
OPTION_SELECTORS: tuple[str, ...] = (
    "[role=option]",
    "li[role=option]",
    ".ng-option",
    ".p-dropdown-item",
    ".select2-results__option",
    "[data-value]",
    "[data-index]",
)


def _listbox_present(frame) -> bool:
    """Check if any listbox/menu is currently visible."""
    for sel in LISTBOX_SELECTORS:
        try:
            if frame.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    # Also check page-level (portals that mount outside frame)
    page = frame.page
    for sel in LISTBOX_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def open_dropdown_robust(
    frame,
    locator,
    strategy_order: Iterable[str] | None = None,
    delay_ms: int = 120
) -> bool:
    """Try multiple strategies to open a dropdown-like widget.
    
    Args:
        frame: Playwright frame context
        locator: Locator pointing to the dropdown trigger
        strategy_order: Sequence of strategy names to try. Supported:
            already_open, click, force_click, icon_click, keyboard, double_click
        delay_ms: Milliseconds to wait after each attempt
        
    Returns:
        True if dropdown was successfully opened, False otherwise
    """
    order = tuple(strategy_order) if strategy_order else DEFAULT_OPEN_STRATEGY_ORDER

    def _already_open():
        return _listbox_present(frame)

    def _click():
        locator.scroll_into_view_if_needed(timeout=2000)
        locator.click(timeout=2500)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _force_click():
        locator.click(timeout=2500, force=True)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _icon_click():
        arrow = locator.locator(ARROW_XPATH).first
        if arrow and arrow.count() > 0 and arrow.is_visible():
            arrow.click(timeout=2500)
            frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _keyboard():
        locator.focus()
        for key in ["Enter", "Space", "Alt+ArrowDown"]:
            try:
                frame.page.keyboard.press(key)
                frame.wait_for_timeout(delay_ms)
                if _listbox_present(frame):
                    return True
            except Exception:
                continue
        return _listbox_present(frame)

    def _double_click():
        locator.dblclick(timeout=2500)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    strategies = {
        "already_open": _already_open,
        "click": _click,
        "force_click": _force_click,
        "icon_click": _icon_click,
        "keyboard": _keyboard,
        "double_click": _double_click,
    }

    for name in order:
        fn = strategies.get(name)
        if not fn:
            continue
        try:
            if fn():
                return True
        except Exception as e:
            logger.debug("Dropdown open strategy failed", extra={"strategy": name, "err": str(e)})
    return _listbox_present(frame)


def collect_open_list_options(frame) -> list[dict[str, Any]]:
    """Collect available visible option nodes with rich attributes.
    
    Should be called after dropdown is confirmed open via open_dropdown_robust().
    Handles virtualized lists by scrolling to load all options.
    
    Args:
        frame: Playwright frame context
        
    Returns:
        List of option dictionaries with keys:
        - text: Option text content
        - value: value attribute
        - dataValue: data-value attribute
        - dataIndex: data-index or position
        - id: element id
        - dataId: data-id/data-key/data-code attribute
    """
    container = None
    
    # Find the listbox container
    for sel in LISTBOX_SELECTORS:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                container = loc.first
                break
        except Exception:
            continue
    
    if not container:
        page = frame.page
        for sel in LISTBOX_SELECTORS:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    container = loc.first
                    break
            except Exception:
                continue
    
    if not container:
        return []

    # Handle virtualization by scrolling
    try:
        for _ in range(40):
            changed = container.evaluate(
                "el => { const b=el.scrollTop; el.scrollTop=el.scrollHeight; return el.scrollTop !== b; }"
            )
            frame.wait_for_timeout(60)
            if not changed:
                break
    except Exception:
        for _ in range(10):
            with contextlib.suppress(Exception):
                frame.page.keyboard.press("End")
            frame.wait_for_timeout(60)

    # Collect options
    options = []
    for sel in OPTION_SELECTORS:
        try:
            opts = container.locator(sel)
            k = opts.count()
        except Exception:
            k = 0
        for i in range(k):
            o = opts.nth(i)
            try:
                if not o.is_visible():
                    continue
                text = (o.text_content() or "").strip()
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                oid = o.get_attribute("id")
                did = o.get_attribute("data-id") or o.get_attribute("data-key") or o.get_attribute("data-code")
                if text or val or dv or di or oid or did:
                    options.append({
                        "text": text,
                        "value": val,
                        "dataValue": dv,
                        "dataIndex": di,
                        "id": oid,
                        "dataId": did
                    })
            except Exception:
                continue
    
    # Deduplicate
    seen = set()
    uniq = []
    for o in options:
        key = (o.get("id"), o.get("dataId"), o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)

    # Close dropdown
    with contextlib.suppress(Exception):
        frame.page.keyboard.press("Escape")
        frame.wait_for_timeout(80)
    
    return uniq
