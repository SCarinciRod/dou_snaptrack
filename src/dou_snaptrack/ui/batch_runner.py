# Compatibility module - re-exports from dou_snaptrack.ui.batch.runner
# This file exists for backward compatibility with existing imports
"""Batch runner module - now in dou_snaptrack.ui.batch/."""

from dou_snaptrack.ui.batch.runner import *  # noqa: F401, F403
from dou_snaptrack.ui.batch.runner import (
    run_batch_with_cfg,
    cleanup_batch_processes,
    clear_ui_lock,
    detect_other_execution,
    detect_other_ui,
    terminate_other_execution,
    register_this_ui_instance,
)

__all__ = [
    "run_batch_with_cfg",
    "cleanup_batch_processes",
    "clear_ui_lock",
    "detect_other_execution",
    "detect_other_ui",
    "terminate_other_execution",
    "register_this_ui_instance",
]
