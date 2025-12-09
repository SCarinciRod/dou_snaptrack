# Compatibility module - re-exports from dou_utils.bulletin.generator
# This file exists for backward compatibility with existing imports
"""Bulletin utilities - now in dou_utils.bulletin.generator."""

from dou_utils.bulletin.generator import *  # noqa: F401, F403
from dou_utils.bulletin.generator import (
    generate_bulletin,
    _extract_doc_header_line,
    _final_clean_snippet,
    _remove_dou_metadata,
    _strip_legalese_preamble,
    _extract_article1_section,
    _default_simple_summarizer,
    _cap_sentences,
    _summarize_item,
)

__all__ = [
    "generate_bulletin",
    "_extract_doc_header_line",
    "_final_clean_snippet",
    "_remove_dou_metadata",
    "_strip_legalese_preamble",
    "_extract_article1_section",
    "_default_simple_summarizer",
    "_cap_sentences",
    "_summarize_item",
]
