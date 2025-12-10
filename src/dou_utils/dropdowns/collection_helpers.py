"""Helper functions for dropdown option collection.

This module contains extracted functions from collect_open_list_options to reduce complexity.
"""

from __future__ import annotations

import contextlib
from typing import Any


def find_listbox_container(frame, listbox_selectors: tuple[str, ...]):
    """Find the listbox container element.

    Args:
        frame: Playwright frame context
        listbox_selectors: Tuple of selector strings

    Returns:
        Container element or None
    """
    # Try frame first
    for sel in listbox_selectors:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue

    # Try page as fallback
    page = frame.page
    for sel in listbox_selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue

    return None


def scroll_to_load_all_options(container, frame) -> None:
    """Scroll container to load all virtualized options.

    Args:
        container: Container element
        frame: Playwright frame context
    """
    try:
        # Try JavaScript scroll first (more reliable for virtualized lists)
        for _ in range(40):
            changed = container.evaluate(
                "el => { const b=el.scrollTop; el.scrollTop=el.scrollHeight; return el.scrollTop !== b; }"
            )
            frame.wait_for_timeout(60)
            if not changed:
                break
    except Exception:
        # Fallback to keyboard navigation
        for _ in range(10):
            with contextlib.suppress(Exception):
                frame.page.keyboard.press("End")
            frame.wait_for_timeout(60)


def extract_option_data(option_element, index: int) -> dict[str, Any]:
    """Extract data from a single option element.

    Args:
        option_element: Playwright locator for option
        index: Option index

    Returns:
        Dictionary with option data
    """
    if not option_element.is_visible():
        return {}

    text = (option_element.text_content() or "").strip()
    val = option_element.get_attribute("value")
    dv = option_element.get_attribute("data-value")
    di = (option_element.get_attribute("data-index") or
          option_element.get_attribute("data-option-index") or
          str(index))
    oid = option_element.get_attribute("id")
    did = (option_element.get_attribute("data-id") or
           option_element.get_attribute("data-key") or
           option_element.get_attribute("data-code"))

    # Only include if at least one attribute is present
    if text or val or dv or di or oid or did:
        return {
            "text": text,
            "value": val,
            "dataValue": dv,
            "dataIndex": di,
            "id": oid,
            "dataId": did
        }
    return {}


def collect_options_from_container(container, option_selectors: tuple[str, ...]) -> list[dict[str, Any]]:
    """Collect all option elements from container.

    Args:
        container: Container element
        option_selectors: Tuple of selector strings

    Returns:
        List of option dictionaries
    """
    options = []
    for sel in option_selectors:
        try:
            opts = container.locator(sel)
            k = opts.count()
        except Exception:
            k = 0

        for i in range(k):
            o = opts.nth(i)
            try:
                option_data = extract_option_data(o, i)
                if option_data:
                    options.append(option_data)
            except Exception:
                continue

    return options


def deduplicate_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate options based on key attributes.

    Args:
        options: List of option dictionaries

    Returns:
        Deduplicated list
    """
    seen = set()
    uniq = []
    for o in options:
        key = (o.get("id"), o.get("dataId"), o.get("text"),
               o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)
    return uniq


def close_dropdown(frame) -> None:
    """Close dropdown by pressing Escape.

    Args:
        frame: Playwright frame context
    """
    with contextlib.suppress(Exception):
        frame.page.keyboard.press("Escape")
        frame.wait_for_timeout(80)
