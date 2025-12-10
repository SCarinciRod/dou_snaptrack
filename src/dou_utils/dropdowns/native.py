"""
Native <select> element utilities.

Provides functions for detecting and reading options from native HTML <select> elements.
"""
from __future__ import annotations

from typing import Any


def is_select(locator) -> bool:
    """Check if the locator points to a native <select> element.

    Args:
        locator: Playwright locator or element handle

    Returns:
        True if the element is a <select>, False otherwise
    """
    try:
        name = locator.evaluate("el => el.tagName")
        return (name or "").lower() == "select"
    except Exception:
        return False


def read_select_options(locator) -> list[dict[str, Any]]:
    """Read options from a native <select> element.

    Returns a list of option dictionaries with rich metadata including
    disabled and selected states.

    Args:
        locator: Playwright locator pointing to a <select> element

    Returns:
        List of option dictionaries with keys:
        - text: Option text content
        - value: Option value attribute
        - dataValue: data-value attribute if present
        - disabled: Whether option is disabled
        - selected: Whether option is selected
        - dataIndex: Zero-based index in options list
    """
    try:
        return locator.evaluate("""
            el => Array.from(el.options || []).map((o,i) => ({
                text: (o.textContent || '').trim(),
                value: o.value,
                dataValue: o.getAttribute('data-value'),
                disabled: !!o.disabled,
                selected: !!o.selected,
                dataIndex: i
            }))
        """) or []
    except Exception:
        return []


# Aliases for backward compatibility
_is_select = is_select
_read_select_options = read_select_options
