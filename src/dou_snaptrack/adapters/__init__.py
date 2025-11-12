from __future__ import annotations

"""Adapters subpackage.

Provides thin bridges to optional dou_utils services/utilities. This file ensures
the subpackage is recognized in all execution contexts (including subprocesses).
"""

# Re-export commonly used symbols for convenience (optional)
try:  # pragma: no cover - convenience only
    from .services import get_edition_runner  # type: ignore F401
except Exception:
    pass
try:  # pragma: no cover
    from .utils import generate_bulletin, summarize_text  # type: ignore F401
except Exception:
    pass
