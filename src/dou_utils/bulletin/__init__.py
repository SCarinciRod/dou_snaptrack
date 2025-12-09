# Bulletin Generation Module
"""Bulletin generation and document formatting utilities."""

# Import actual exports only when accessed
__all__ = [
    "generate_bulletin",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "generate_bulletin":
        from .generator import generate_bulletin
        return generate_bulletin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
