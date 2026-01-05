"""Scoring helpers for `summary_utils.summarize_text`.

This module was referenced by `dou_utils.text.summary_utils` but was missing in the
repository, causing the summarization pipeline to fall back (with warnings).

The functions below are intentionally lightweight (pure-Python, no deps) and are
designed to be stable across document types.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]*")
_WHITESPACE_RE = re.compile(r"\s+")


def _tokenize(s: str) -> list[str]:
    s = (s or "").strip().lower()
    if not s:
        return []
    return _WORD_RE.findall(s)


def compute_lexical_diversity(sentences: list[str]) -> list[float]:
    """Return a per-sentence lexical diversity score in [0, 1].

    Uses type/token ratio with a small-length correction to avoid overweighting
    very short sentences.
    """
    out: list[float] = []
    for s in sentences:
        toks = _tokenize(s)
        if not toks:
            out.append(0.0)
            continue
        unique = len(set(toks))
        total = len(toks)
        # type/token ratio, length-corrected (short sentences shouldn't dominate)
        ttr = unique / max(1, total)
        length_bonus = 1.0 - math.exp(-total / 12.0)
        out.append(max(0.0, min(1.0, ttr * length_bonus)))
    return out


def compute_position_scores(n: int, mode: str = "center") -> list[float]:
    """Return a per-position prior score in [0, 1].

    Modes:
    - lead/head: prefers earlier sentences.
    - tail: prefers later sentences.
    - center (default): prefers the middle.
    """
    n = int(n or 0)
    if n <= 0:
        return []

    m = (mode or "center").lower()
    scores: list[float] = [0.0] * n

    if m in ("lead", "head"):
        # Exponential decay from start.
        for i in range(n):
            scores[i] = math.exp(-i / 5.0)
    elif m in ("tail",):
        for i in range(n):
            scores[i] = math.exp(-(n - 1 - i) / 5.0)
    else:
        # Gaussian bump around the center.
        mu = (n - 1) / 2.0
        sigma = max(1.5, n / 6.0)
        for i in range(n):
            z = (i - mu) / sigma
            scores[i] = math.exp(-0.5 * z * z)

    # Normalize to [0, 1]
    mx = max(scores) if scores else 1.0
    if mx <= 0:
        return [0.0] * n
    return [s / mx for s in scores]


def compute_keyword_scores(sentences: list[str], keywords: set[str] | Iterable[str]) -> list[float]:
    """Return a per-sentence keyword match score in [0, 1]."""
    kw_set = set(keywords or [])
    if not kw_set:
        return [0.0 for _ in sentences]

    out: list[float] = []
    for s in sentences:
        toks = _tokenize(s)
        if not toks:
            out.append(0.0)
            continue
        hits = sum(1 for t in toks if t in kw_set)
        out.append(min(1.0, hits / max(3, len(kw_set))))
    return out


def compute_sentence_scores(
    sentences: list[str],
    lex_scores: list[float],
    pos_scores: list[float],
    keyword_scores: list[float],
    mode: str,
    priority_sentence: tuple[int, str] | None = None,
) -> list[float]:
    """Combine component scores into a final per-sentence score."""
    n = len(sentences)
    if not (len(lex_scores) == len(pos_scores) == len(keyword_scores) == n):
        # Defensive: align lengths
        lex_scores = (lex_scores + [0.0] * n)[:n]
        pos_scores = (pos_scores + [0.0] * n)[:n]
        keyword_scores = (keyword_scores + [0.0] * n)[:n]

    m = (mode or "center").lower()
    w_pos = 0.55 if m in ("center", "tail") else 0.45
    w_lex = 0.25
    w_kw = 0.20

    scores: list[float] = []
    for i in range(n):
        s = w_pos * pos_scores[i] + w_lex * lex_scores[i] + w_kw * keyword_scores[i]
        scores.append(s)

    # Ensure priority sentence gets a meaningful bump
    if priority_sentence is not None:
        pri_idx, _ = priority_sentence
        if 0 <= pri_idx < n:
            scores[pri_idx] = max(scores[pri_idx], (max(scores) if scores else 0.0) + 0.15)

    return scores


def select_top_sentences(
    scores: list[float],
    n_sentences: int,
    max_lines: int,
    priority_sentence: tuple[int, str] | None = None,
) -> list[int]:
    """Pick sentence indices maximizing score, preserving original order."""
    n = int(n_sentences or 0)
    k = max(1, int(max_lines or 1))
    if n <= 0 or not scores:
        return []

    # Start with top-k by score
    ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)
    picked = set(ranked[: min(k, n)])

    # Ensure priority sentence is included
    if priority_sentence is not None:
        pri_idx, _ = priority_sentence
        if 0 <= pri_idx < n:
            picked.add(pri_idx)

    # If we exceeded k due to priority, drop lowest-scoring non-priority
    if len(picked) > min(k, n):
        pri_idx = priority_sentence[0] if priority_sentence else -1
        picked_list = sorted(picked, key=lambda i: scores[i])  # ascending
        while len(picked_list) > min(k, n):
            drop = picked_list.pop(0)
            if drop == pri_idx:
                picked_list.append(drop)
                picked_list = sorted(picked_list, key=lambda i: scores[i])
                continue
        picked = set(picked_list)

    return sorted(picked)


def deduplicate_sentences(lines: list[str], max_lines: int) -> list[str]:
    """Remove near-duplicate lines while preserving order."""
    out: list[str] = []
    seen: set[str] = set()

    for line in lines:
        if not line:
            continue
        norm = _WHITESPACE_RE.sub(" ", line.strip().lower())
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(line.strip())
        if len(out) >= int(max_lines or 1):
            break

    return out


def select_top_sentences_from_text(
    sentences: list[str],
    max_lines: int,
    scores: list[float],
) -> list[str]:
    """Convenience helper returning sentence texts."""
    idx = select_top_sentences(scores, len(sentences), max_lines)
    return [sentences[i] for i in idx]
