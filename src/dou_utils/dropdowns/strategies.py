"""
Robust dropdown opening & option selection strategies.

Provides:
 - open_dropdown_robust(frame, locator, config)
 - collect_open_list_options(frame)

This consolidates heuristics from original scripts (00_map_page, 05_cascade_cli, 00_map_pairs),
maintaining configurable order and logging.
"""
from __future__ import annotations

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
    from .collection_helpers import (
        close_dropdown,
        collect_options_from_container,
        deduplicate_options,
        find_listbox_container,
        scroll_to_load_all_options,
    )

    # Find the listbox container
    container = find_listbox_container(frame, LISTBOX_SELECTORS)
    if not container:
        return []

    # Handle virtualization by scrolling
    scroll_to_load_all_options(container, frame)

    # Collect and deduplicate options
    options = collect_options_from_container(container, OPTION_SELECTORS)
    uniq = deduplicate_options(options)

    # Close dropdown
    close_dropdown(frame)

    return uniq
