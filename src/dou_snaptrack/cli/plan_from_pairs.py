# Compatibility module - re-exports from dou_snaptrack.cli.plan.from_pairs
# This file exists for backward compatibility with existing imports
"""Plan from pairs module - now in dou_snaptrack.cli.plan/."""

from dou_snaptrack.cli.plan.from_pairs import *  # noqa: F401, F403
from dou_snaptrack.cli.plan.from_pairs import build_plan_from_pairs

__all__ = ["build_plan_from_pairs"]
