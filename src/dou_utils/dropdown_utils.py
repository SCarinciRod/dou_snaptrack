"""
DEPRECATED: This module is deprecated. Use dou_utils.dropdowns instead.

Migration guide:
    # Old:
    from dou_utils.dropdown_utils import _is_select, _read_select_options
    
    # New:
    from dou_utils.dropdowns import is_select, read_select_options

This module re-exports from the new location for backward compatibility.
"""
import warnings

warnings.warn(
    "dou_utils.dropdown_utils is deprecated. Use dou_utils.dropdowns instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from dou_utils.dropdowns import is_select as _is_select, read_select_options as _read_select_options

__all__ = ["_is_select", "_read_select_options"]
