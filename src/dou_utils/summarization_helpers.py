"""Summarization helpers to reduce complexity of _summarize_item.

This module contains extracted functions to handle text summarization
with multiple fallback strategies.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)


def extract_base_text(it: dict[str, Any]) -> str:
    """Extract base text from item for summarization.

    Args:
        it: Item dictionary

    Returns:
        Base text to summarize
    """
    return it.get("texto") or it.get("ementa") or ""


def get_fallback_from_title(it: dict[str, Any]) -> str | None:
    """Get fallback text from item title or header.

    Args:
        it: Item dictionary

    Returns:
        Fallback text or None
    """
    from dou_utils.bulletin_utils import _extract_doc_header_line, _final_clean_snippet

    try:
        head = _extract_doc_header_line(it)
        if head:
            return _final_clean_snippet(head)
    except Exception:
        pass

    t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
    return _final_clean_snippet(str(t)) if t else None


def prepare_text_for_summarization(base: str) -> str:
    """Clean and prepare text for summarization.

    Removes DOU metadata, strips legalese preamble, and extracts Article 1
    when applicable.

    Args:
        base: Base text

    Returns:
        Cleaned text
    """
    from dou_utils.bulletin_utils import (
        _remove_dou_metadata,
        _strip_legalese_preamble,
        _extract_article1_section,
    )

    try:
        clean = _remove_dou_metadata(base)
        clean = _strip_legalese_preamble(clean)
        a1 = _extract_article1_section(clean)
        base_eff = a1 or clean

        if not base_eff:
            # Fallback: try with original cleaned text
            clean2 = _strip_legalese_preamble(_remove_dou_metadata(base))
            base_eff = clean2 or base

        return base_eff
    except Exception as e:
        logger.debug(f"Failed to clean/extract article: {e}")
        return base


def derive_mode_from_doc_type(it: dict[str, Any], default_mode: str) -> str:
    """Derive summarization mode from document type.

    Uses 'lead' mode for normative acts and dispatches.

    Args:
        it: Item dictionary
        default_mode: Default mode to use

    Returns:
        Derived mode
    """
    derived_mode = (default_mode or "center").lower()

    try:
        tipo = (it.get("tipo_ato") or "").strip().lower()
        if any(tipo.startswith(prefix) for prefix in ["decreto", "portaria", "resolu", "despacho"]):
            derived_mode = "lead"
    except Exception as e:
        logger.debug(f"Failed to derive mode from tipo_ato: {e}")

    return derived_mode


def try_summarizer_with_signatures(
    summarizer_fn: Callable,
    text: str,
    max_lines: int,
    mode: str,
    keywords: list[str] | None,
) -> tuple[str | None, str]:
    """Try summarizer function with multiple signature fallbacks.

    Tries different parameter orders for backward compatibility.

    Args:
        summarizer_fn: Summarizer function
        text: Text to summarize
        max_lines: Maximum lines
        mode: Summarization mode
        keywords: Keywords to emphasize

    Returns:
        Tuple of (snippet, method_tag)
    """
    # Try preferred signature: (text, max_lines, mode, keywords)
    try:
        snippet = summarizer_fn(text, max_lines, mode, keywords)
        return snippet, "summarizer"
    except TypeError:
        pass

    # Try alternative: (text, max_lines, keywords, mode)
    try:
        snippet = summarizer_fn(text, max_lines, keywords, mode)  # type: ignore
        return snippet, "summarizer_alt"
    except TypeError:
        pass

    # Try legacy: (text, max_lines, mode)
    try:
        snippet = summarizer_fn(text, max_lines, mode)  # type: ignore
        return snippet, "summarizer_legacy"
    except Exception as e:
        logger.warning(f"Erro ao sumarizar: {e}")
        return None, ""


def apply_summarizer_with_fallbacks(
    summarizer_fn: Callable,
    base_text: str,
    max_lines: int,
    mode: str,
    keywords: list[str] | None,
) -> tuple[str | None, str]:
    """Apply summarizer with multiple text preparation fallbacks.

    Args:
        summarizer_fn: Summarizer function
        base_text: Base text to summarize
        max_lines: Maximum lines
        mode: Summarization mode
        keywords: Keywords to emphasize

    Returns:
        Tuple of (snippet, method_tag)
    """
    from dou_utils.bulletin_utils import _remove_dou_metadata, _strip_legalese_preamble

    # First attempt with prepared text
    snippet, method_tag = try_summarizer_with_signatures(summarizer_fn, base_text, max_lines, mode, keywords)

    if snippet:
        return snippet, method_tag

    # Fallback: try with alternative text preparation
    try:
        alt = _strip_legalese_preamble(_remove_dou_metadata(base_text)) if base_text else base_text
        if alt and alt != base_text:
            snippet, tag = try_summarizer_with_signatures(summarizer_fn, alt, max_lines, mode, keywords)
            if snippet:
                return snippet, tag or "summarizer_altbase"
    except Exception:
        pass

    return None, method_tag


def apply_default_summarizer(text: str, max_lines: int, mode: str, keywords: list[str] | None) -> str | None:
    """Apply default simple summarizer as final fallback.

    Args:
        text: Text to summarize
        max_lines: Maximum lines
        mode: Summarization mode
        keywords: Keywords to emphasize

    Returns:
        Summarized text or None
    """
    from dou_utils.bulletin_utils import _default_simple_summarizer

    try:
        return _default_simple_summarizer(text, max_lines, mode, keywords)
    except Exception:
        return None


def post_process_snippet(snippet: str, max_lines: int) -> str:
    """Post-process snippet by removing noise and capping sentences.

    Args:
        snippet: Snippet to process
        max_lines: Maximum lines

    Returns:
        Cleaned snippet
    """
    from dou_utils.bulletin_utils import _cap_sentences, _final_clean_snippet

    # Remove common noise patterns at start (ANEXO, NR, codes)
    with contextlib.suppress(Exception):
        snippet = re.sub(r"^(ANEXO(\s+[IVXLCDM]+)?|NR)\b[:\-\s]*", "", snippet, flags=re.I).strip()

    snippet = _cap_sentences(snippet, max_lines)
    snippet = _final_clean_snippet(snippet)

    return snippet
