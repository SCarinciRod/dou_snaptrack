# Compatibility module - re-exports from dou_snaptrack.cli.reporting.reporter
# This file exists for backward compatibility with existing imports
"""Reporting module - now in dou_snaptrack.cli.reporting/."""

from dou_snaptrack.cli.reporting.reporter import *  # noqa: F401, F403
from dou_snaptrack.cli.reporting.reporter import report_from_aggregated, split_and_report_by_n1
from dou_snaptrack.cli.reporting.consolidation import aggregate_jobs_by_date, aggregate_outputs_by_plan

__all__ = [
    "report_from_aggregated",
    "split_and_report_by_n1",
    "aggregate_jobs_by_date",
    "aggregate_outputs_by_plan",
]
