# Compatibility module - re-exports from dou_snaptrack.cli.plan.live
# This file exists for backward compatibility with existing imports
"""Plan live module - now in dou_snaptrack.cli.plan/."""

from dou_snaptrack.cli.plan.live import *  # noqa: F401, F403
from dou_snaptrack.cli.plan.live import (
    build_plan_live,
    _collect_dropdown_roots,
    _read_dropdown_options,
    _select_roots,
    _build_keys,
    _filter_opts,
    DROPDOWN_ROOT_SELECTORS,
    LEVEL_IDS,
    LISTBOX_SELECTORS,
    OPTION_SELECTORS,
    normalize_text,
)

__all__ = [
    "build_plan_live",
    "_collect_dropdown_roots",
    "_read_dropdown_options",
    "_select_roots",
    "_build_keys",
    "_filter_opts",
    "DROPDOWN_ROOT_SELECTORS",
    "LEVEL_IDS",
    "LISTBOX_SELECTORS",
    "OPTION_SELECTORS",
    "normalize_text",
]
