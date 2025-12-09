# Compatibility module - re-exports from dou_snaptrack.ui.collectors.subprocess_utils
# This file exists for backward compatibility with existing imports
"""Subprocess utilities module - now in dou_snaptrack.ui.collectors/."""

from dou_snaptrack.ui.collectors.subprocess_utils import *  # noqa: F401, F403
from dou_snaptrack.ui.collectors.subprocess_utils import (
    execute_script_and_read_result,
    write_result,
)

__all__ = ["execute_script_and_read_result", "write_result"]
