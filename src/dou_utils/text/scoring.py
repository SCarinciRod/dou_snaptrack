"""Scoring helpers for text summarization.

This module contains scoring logic extracted from summarize_text to reduce complexity.
"""

from __future__ import annotations

import re
import unicodedata

# Patterns for scoring (imported from summary_utils)
_MONEY_PATTERN = re.compile(r"R\$\s*[\d.,]+|[\d.,]+\s*(?:reais?|milhões?|bilhões?)", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", re.IGNORECASE)
_DOU_HEADER_SENTENCE = re.compile(
    r"(?:Diário Oficial|Brasão|Imprensa Nacional|Edição\s+\d+|Seção\s+\d+|Página\s+\d+)",
    re.IGNORECASE
)
_ENUMERATION_PATTERN = re.compile(r"^\s*(?:\d+[.)\-]|[A-Z][.)\-]|[IVXLCDM]+[.)\-])\s+", re.MULTILINE)


def tokenize_sentence(sentence: str) -> list[str]:
    """Tokenize a sentence into normalized tokens.

    Args:
        sentence: Input sentence

    Returns:
        List of tokens (3+ chars, lowercased, ascii-normalized)
    """
    raw = unicodedata.normalize("NFKD", sentence).encode("ascii", "ignore").decode("ascii")
    return [w for w in re.findall(r"[a-z0-9]+", raw.lower()) if len(w) >= 3]


def compute_lexical_diversity(sentences: list[str]) -> list[float]:
    """Compute lexical diversity score for each sentence.

    Args:
        sentences: List of sentences

    Returns:
        List of lexical diversity scores (unique tokens / total tokens)
    """
    lex = []
    for s in sentences:
        toks = tokenize_sentence(s)
        unique = len(set(toks))
        lex.append(unique / (1 + len(toks)))
    return lex


def compute_position_scores(n_sentences: int, mode: str) -> list[float]:
    """Compute position-based scores for sentences.

    Args:
        n_sentences: Number of sentences
        mode: Scoring mode ('lead' or 'center')

    Returns:
        List of position scores
    """
    pos = []
    for i in range(n_sentences):
        if mode == "lead":
            pos.append(1.0 - (i / n_sentences) * 0.85)
        else:  # center mode
            x = (i - (n_sentences - 1) / 2) / (n_sentences / 2)
            pos.append(1.0 - (x * x))
    return pos


def compute_keyword_scores(sentences: list[str], keywords: set[str]) -> list[int]:
    """Compute keyword match scores for sentences.

    Args:
        sentences: List of sentences
        keywords: Set of keywords to match

    Returns:
        List of keyword match counts
    """
    if not keywords:
        return [0] * len(sentences)

    # OTIMIZAÇÃO: compilar regex uma vez em vez de O(s * k) substring checks
    valid_keywords = [k for k in keywords if k]
    if not valid_keywords:
        return [0] * len(sentences)

    pattern = "|".join(re.escape(k) for k in valid_keywords)
    keyword_rx = re.compile(pattern, re.I)

    return [len(keyword_rx.findall(s)) for s in sentences]


def get_scoring_weights(mode: str) -> tuple[float, float, float]:
    """Get scoring weights based on mode.

    Args:
        mode: Scoring mode

    Returns:
        Tuple of (keyword_weight, lexical_weight, position_weight)
    """
    if mode == "keywords-first":
        return 1.6, 1.0, 0.6
    elif mode == "lead":
        return 1.0, 0.8, 1.6
    else:  # center or default
        return 1.4, 1.0, 1.2


def apply_length_penalties(score: float, sentence: str, keyword_hits: int) -> float:
    """Apply penalties based on sentence length.

    Args:
        score: Current score
        sentence: Sentence text
        keyword_hits: Number of keyword matches

    Returns:
        Adjusted score
    """
    if len(sentence) > 450:
        score -= 0.4
    if len(sentence) < 40 and keyword_hits == 0:
        score -= 0.5
    return score


def apply_content_bonuses(score: float, sentence: str, priority_idx: list[int] | None, current_idx: int) -> float:
    """Apply bonuses for priority content.

    Args:
        score: Current score
        sentence: Sentence text
        priority_idx: Index of priority sentence (if any)
        current_idx: Current sentence index

    Returns:
        Adjusted score
    """
    # Priority sentence bonus
    if priority_idx and current_idx == priority_idx[0]:
        score += 0.9

    # Money/value bonus
    if _MONEY_PATTERN.search(sentence):
        score += 0.4

    # Date bonus
    if _DATE_PATTERN.search(sentence):
        score += 0.2

    return score


def apply_metadata_penalties(score: float, sentence: str) -> float:
    """Apply penalties for DOU metadata and headers.

    Args:
        score: Current score
        sentence: Sentence text

    Returns:
        Adjusted score
    """
    # Strong penalty for DOU header patterns
    if _DOU_HEADER_SENTENCE.search(sentence):
        score -= 2.0

    # Penalty for metadata terms
    s_low = sentence.lower()
    metadata_count = sum([
        "edição" in s_low or "edicao" in s_low,
        "seção" in s_low or "secao" in s_low,
        "página" in s_low or "pagina" in s_low,
        "publicado em" in s_low,
        "brasão" in s_low or "brasao" in s_low
    ])
    if metadata_count >= 2:
        score -= 1.5

    # Penalty for enumeration/list items
    if _ENUMERATION_PATTERN.search(sentence):
        score -= 0.7

    return score


def compute_sentence_scores(
    sentences: list[str],
    lex_scores: list[float],
    pos_scores: list[float],
    keyword_scores: list[int],
    mode: str,
    priority_idx: list[int] | None,
) -> list[tuple[float, int, str]]:
    """Compute final scores for all sentences.

    Args:
        sentences: List of sentences
        lex_scores: Lexical diversity scores
        pos_scores: Position scores
        keyword_scores: Keyword match scores
        mode: Scoring mode
        priority_idx: Index of priority sentence (if any)

    Returns:
        List of tuples (score, index, sentence)
    """
    w_k, w_l, w_p = get_scoring_weights(mode)
    scores = []

    for i, s in enumerate(sentences):
        # Base score from weighted components
        score = (w_k * keyword_scores[i]) + (w_l * lex_scores[i]) + (w_p * pos_scores[i])

        # Apply length penalties
        score = apply_length_penalties(score, s, keyword_scores[i])

        # Apply content bonuses
        score = apply_content_bonuses(score, s, priority_idx, i)

        # Apply metadata penalties
        score = apply_metadata_penalties(score, s)

        scores.append((score, i, s))

    return scores


def select_top_sentences(
    scores: list[tuple[float, int, str]],
    n_sentences: int,
    max_lines: int,
    priority_idx: list[int] | None,
) -> list[int]:
    """Select top scoring sentences with priority inclusion.

    Args:
        scores: List of (score, index, sentence) tuples
        n_sentences: Total number of sentences
        max_lines: Maximum lines to select
        priority_idx: Index of priority sentence (if any)

    Returns:
        List of selected sentence indices
    """
    # Sort by score (descending), then by position
    scores.sort(key=lambda t: (-t[0], t[1]))
    picked_idx = sorted(i for _, i, _ in scores[:max_lines])

    # Ensure priority sentence is included
    if priority_idx and priority_idx[0] not in picked_idx:
        picked_idx = sorted(([*picked_idx, priority_idx[0]])[:max_lines])

    # Fill remaining slots with nearby sentences
    if len(picked_idx) < max_lines:
        need = max_lines - len(picked_idx)
        pool = [i for i in range(n_sentences) if i not in picked_idx]
        anchor = scores[0][1]
        pool.sort(key=lambda i: abs(i - anchor))
        picked_idx.extend(pool[:need])
        picked_idx = sorted(set(picked_idx))[:max_lines]

    return picked_idx


def deduplicate_sentences(sentences: list[str], max_lines: int) -> list[str]:
    """Remove duplicate sentences while preserving order.

    Args:
        sentences: List of sentences
        max_lines: Maximum lines to keep

    Returns:
        Deduplicated list of sentences
    """
    final, seen = [], set()
    for ln in sentences:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(ln)
        if len(final) >= max_lines:
            break
    return final
