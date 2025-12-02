"""Utility library shared by dou-snaptrack.

This package contains helpers for page interaction, parsing, enrichment,
and services used by the main application. Keeping an explicit __init__
ensures packaging with setuptools find_packages.

Subpackages:
- dropdowns: Robust dropdown handling (native and custom)
- selection: Option selection and matching utilities
"""
from __future__ import annotations

# Re-export subpackages for convenience
from dou_utils import dropdowns, selection

__all__ = ["dropdowns", "selection"]
