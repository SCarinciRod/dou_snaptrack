# Compatibility module - re-exports from dou_utils.text.summarize
# This file exists for backward compatibility with existing imports
"""Summarization utilities - now in dou_utils.text.summarize."""

from dou_utils.text.summarize import *  # noqa: F401, F403
from dou_utils.text.summarize import summarize_text

__all__ = ["summarize_text"]
