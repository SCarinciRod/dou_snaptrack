# Text Processing Module
"""Text cleaning, summarization and scoring utilities."""

__all__ = [
    "summarize_text",
    "clean_text_for_summary",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "summarize_text":
        from dou_utils.text.summarize import summarize_text
        return summarize_text
    if name == "clean_text_for_summary":
        from dou_utils.text.summary_utils import clean_text_for_summary
        return clean_text_for_summary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
