# Compatibility module - re-exports from dou_snaptrack.ui.pages.dou_fetch
# This file exists for backward compatibility with existing imports
"""DOU fetch module - now in dou_snaptrack.ui.pages/."""

from dou_snaptrack.ui.pages.dou_fetch import *  # noqa: F401, F403
from dou_snaptrack.ui.pages.dou_fetch import (
    find_system_browser_exe,
    fetch_n1_options,
    fetch_n2_options,
)

__all__ = ["find_system_browser_exe", "fetch_n1_options", "fetch_n2_options"]
