"""
DEPRECATED: This module is deprecated. Use dou_utils.dropdowns instead.

Migration guide:
    # Old:
    from dou_utils.dropdown_strategies import open_dropdown_robust, collect_open_list_options

    # New:
    from dou_utils.dropdowns import open_dropdown_robust, collect_open_list_options

This module re-exports from the new location for backward compatibility.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "dou_utils.dropdown_strategies is deprecated. Use dou_utils.dropdowns instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from dou_utils.dropdowns import (
    DEFAULT_OPEN_STRATEGY_ORDER,
    collect_open_list_options,
    open_dropdown_robust,
)
from dou_utils.dropdowns.strategies import ARROW_XPATH, LISTBOX_SELECTORS, OPTION_SELECTORS

__all__ = [
    "ARROW_XPATH",
    "DEFAULT_OPEN_STRATEGY_ORDER",
    "LISTBOX_SELECTORS",
    "OPTION_SELECTORS",
    "collect_open_list_options",
    "open_dropdown_robust",
]
