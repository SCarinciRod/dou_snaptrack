"""
Dropdown utilities package for DOU Playwright automation.

This package provides robust dropdown handling including:
- Native <select> element utilities
- Custom dropdown opening strategies (ARIA, click, keyboard)
- Option collection from virtualized lists

Main exports:
- open_dropdown_robust: Try multiple strategies to open a dropdown
- collect_open_list_options: Collect visible options after opening
- is_select: Check if an element is a native <select>
- read_select_options: Read options from native <select>

Example usage:
    from dou_utils.dropdowns import open_dropdown_robust, collect_open_list_options

    if open_dropdown_robust(frame, locator):
        options = collect_open_list_options(frame)
"""
from __future__ import annotations

from .native import is_select, read_select_options
from .strategies import (
    DEFAULT_OPEN_STRATEGY_ORDER,
    collect_open_list_options,
    open_dropdown_robust,
)

__all__ = [
    "DEFAULT_OPEN_STRATEGY_ORDER",
    "collect_open_list_options",
    "is_select",
    "open_dropdown_robust",
    "read_select_options",
]
