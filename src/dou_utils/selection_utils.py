"""
DEPRECATED: This module is deprecated. Use dou_utils.selection instead.

Migration guide:
    # Old:
    from dou_utils.selection_utils import is_sentinel, select_option_robust, read_rich_options
    
    # New:
    from dou_utils.selection import is_sentinel, select_option_robust, read_rich_options

This module re-exports from the new location for backward compatibility.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "dou_utils.selection_utils is deprecated. Use dou_utils.selection instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
# Also re-export dropdown utilities that were exposed here
from dou_utils.dropdowns import (
    collect_open_list_options,
    open_dropdown_robust,
)
from dou_utils.selection import (
    SENTINELA_PREFIX,
    collect_dropdowns,
    is_sentinel,
    option_data,
    select_level,
    select_option,
    select_option_robust,
    wait_repopulation,
)
from dou_utils.selection.helpers import read_rich_options

__all__ = [
    "SENTINELA_PREFIX",
    "collect_dropdowns",
    "collect_open_list_options",
    "is_sentinel",
    "open_dropdown_robust",
    "option_data",
    "read_rich_options",
    "select_level",
    "select_option",
    "select_option_robust",
    "wait_repopulation",
]
