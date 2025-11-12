from __future__ import annotations

"""Adapter utilities bridging dou_snaptrack to dou_utils.

This module provides thin wrappers/import shims for optional utilities that live
in the dou_utils package. Keeping imports centralized here lets callers handle
the absence of features gracefully (e.g., summarization or bulletin generation)
without crashing worker subprocesses.

Exposed symbols:
 - generate_bulletin: callable or None
 - summarize_text: callable or None
"""

from collections.abc import Callable
from typing import Any

# Default to None; import best-available implementations from dou_utils
generate_bulletin: Callable[..., Any] | None
summarize_text: Callable[..., Any] | None

try:  # bulletin generation (docx / md / html)
    from dou_utils.bulletin_utils import generate_bulletin as _gen  # type: ignore

    generate_bulletin = _gen
except Exception:
    generate_bulletin = None

try:  # robust summarization wrapper
    from dou_utils.summarize import summarize_text as _sum  # type: ignore

    summarize_text = _sum
except Exception:
    summarize_text = None
