"""
Selection utilities package for DOU Playwright automation.

This package provides option selection and matching utilities including:
- Selectors for dropdown roots, listboxes, and options
- Sentinel value detection
- Async/sync selection helpers
- Robust option matching by various key types

Main exports:
- DROPDOWN_ROOT_SELECTORS, LISTBOX_SELECTORS, OPTION_SELECTORS: CSS selectors
- is_sentinel: Check if value is a placeholder sentinel
- select_option_robust: Select option with fallback strategies
- read_rich_options: Get options from native or custom dropdowns
- wait_repopulation: Wait for dropdown to repopulate after parent selection

Example usage:
    from dou_utils.selection import is_sentinel, select_option_robust
    
    if not is_sentinel(value, label):
        select_option_robust(frame, handle, value, "value")
"""
from __future__ import annotations

from .async_helpers import (
    collect_dropdowns,
    option_data,
    select_level,
    select_option,
)
from .constants import (
    DROPDOWN_ROOT_SELECTORS,
    LISTBOX_SELECTORS,
    OPTION_SELECTORS,
    SENTINELA_PREFIX,
    all_selectors,
)
from .helpers import (
    is_sentinel,
    read_rich_options,
    select_option_robust,
    wait_repopulation,
)

__all__ = [
    # Constants
    "DROPDOWN_ROOT_SELECTORS",
    "LISTBOX_SELECTORS",
    "OPTION_SELECTORS",
    "SENTINELA_PREFIX",
    "all_selectors",
    # Sync helpers
    "is_sentinel",
    "read_rich_options",
    "select_option_robust",
    "wait_repopulation",
    # Async helpers
    "collect_dropdowns",
    "option_data",
    "select_level",
    "select_option",
]
