"""
DEPRECATED: This module is deprecated. Use dou_utils.selection instead.

Migration guide:
    # Old:
    from dou_utils.selectors import DROPDOWN_ROOT_SELECTORS, LISTBOX_SELECTORS, OPTION_SELECTORS
    
    # New:
    from dou_utils.selection import DROPDOWN_ROOT_SELECTORS, LISTBOX_SELECTORS, OPTION_SELECTORS

This module re-exports from the new location for backward compatibility.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "dou_utils.selectors is deprecated. Use dou_utils.selection instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from dou_utils.selection import (
    DROPDOWN_ROOT_SELECTORS,
    LISTBOX_SELECTORS,
    OPTION_SELECTORS,
    all_selectors,
)

__all__ = [
    "DROPDOWN_ROOT_SELECTORS",
    "LISTBOX_SELECTORS",
    "OPTION_SELECTORS",
    "all_selectors",
]
