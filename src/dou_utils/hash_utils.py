"""
Central hashing utilities.
"""

from __future__ import annotations

import hashlib


def stable_sha1(*parts: str) -> str:
    data = "||".join(p or "" for p in parts)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()
