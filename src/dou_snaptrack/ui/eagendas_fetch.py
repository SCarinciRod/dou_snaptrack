# Compatibility module - re-exports from dou_snaptrack.ui.pages.eagendas_fetch
# This file exists for backward compatibility with existing imports
"""E-Agendas fetch module - now in dou_snaptrack.ui.pages/."""

from dou_snaptrack.ui.pages.eagendas_fetch import *  # noqa: F401, F403
from dou_snaptrack.ui.pages.eagendas_fetch import fetch_hierarchy

__all__ = ["fetch_hierarchy"]
