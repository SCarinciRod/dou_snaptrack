"""
Adapter for E-Agendas document generation.

This module provides a thin wrapper for the eagendas_document utility that lives
in the dou_utils package. Keeping imports centralized here lets callers handle
the absence of features gracefully without crashing when lxml is corrupted.

Exposed symbols:
 - generate_eagendas_document_from_json: callable or None
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Default to None; import best-available implementation from dou_utils
generate_eagendas_document_from_json: Callable[..., Any] | None

try:  # E-Agendas document generation (docx)
    from dou_utils.eagendas_document import generate_eagendas_document_from_json as _gen  # type: ignore

    generate_eagendas_document_from_json = _gen
except Exception:
    # Se lxml estiver corrompido, o import falhará silenciosamente
    generate_eagendas_document_from_json = None
