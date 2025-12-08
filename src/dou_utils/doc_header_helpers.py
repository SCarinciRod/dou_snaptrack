"""Helper functions for document header extraction.

This module contains extracted functions from split_doc_header to reduce complexity.
"""

from __future__ import annotations

import re
from typing import Any

# Patterns (imported from text_cleaning.py context)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_NEWLINE_PATTERN = re.compile(r"[\r\n]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_HEADER_DATE_PATTERN = re.compile(r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b")


def prepare_text_window(text: str, max_window: int = 4000, max_lines: int = 50) -> tuple[str, list[str]]:
    """Prepare text window for header detection.
    
    Args:
        text: Input text
        max_window: Maximum window size in characters
        max_lines: Maximum number of lines to consider
        
    Returns:
        Tuple of (blob, head_candidates)
    """
    raw = _HTML_TAG_PATTERN.sub(" ", text)
    raw_window = raw[:max_window]
    lines = _NEWLINE_PATTERN.split(raw_window)
    
    head_candidates = []
    for ln in lines[:max_lines]:
        s = ln.strip()
        if s:
            head_candidates.append(s)
    
    blob = "\n".join(head_candidates)
    return blob, head_candidates


def get_document_types() -> list[str]:
    """Get list of document types to search for.
    
    Returns:
        List of document types sorted by length (longest first)
    """
    doc_alt = [
        "PORTARIA CONJUNTA", "INSTRUÇÃO NORMATIVA", "INSTRUCAO NORMATIVA", "DECRETO-LEI",
        "MEDIDA PROVISÓRIA", "MEDIDA PROVISORIA", "ORDEM DE SERVIÇO", "ORDEM DE SERVICO",
        "RESOLUÇÃO", "RESOLUCAO", "DELIBERAÇÃO", "DELIBERACAO", "RETIFICAÇÃO", "RETIFICACAO",
        "COMUNICADO", "MENSAGEM", "EXTRATO", "PARECER", "DESPACHO", "EDITAL", "DECRETO",
        "PORTARIA", "LEI", "ATO", "AVISO"
    ]
    return sorted(doc_alt, key=len, reverse=True)


def find_document_type_index(blob: str, doc_types: list[str]) -> int | None:
    """Find index of first document type occurrence.
    
    Args:
        blob: Text blob to search in
        doc_types: List of document types
        
    Returns:
        Index of first occurrence or None
    """
    start_idx = None
    upper_blob = blob.upper()
    for dt in doc_types:
        i = upper_blob.find(dt)
        if i != -1 and (start_idx is None or i < start_idx):
            start_idx = i
    return start_idx


def find_uppercase_line_header(head_candidates: list[str], raw: str) -> tuple[str | None, str]:
    """Find header based on uppercase proportion heuristic.
    
    Args:
        head_candidates: List of candidate header lines
        raw: Raw text
        
    Returns:
        Tuple of (header, body)
    """
    for s in head_candidates:
        letters = [ch for ch in s if ch.isalpha()]
        if not letters:
            continue
        upp = sum(1 for ch in letters if ch.isupper())
        if upp / max(1, len(letters)) >= 0.6 and len(s) >= 10:
            header = s
            idx = raw.find(s)
            if idx != -1:
                tail = raw[idx + len(s):]
                tail = re.sub(r'^[\s\-:—]+', '', tail)
                body = tail
                return header, body
            return header, raw
    return None, ""


def extract_header_lines(after: str) -> list[str]:
    """Extract header lines until first period or end.
    
    Args:
        after: Text after document type
        
    Returns:
        List of header lines
    """
    header_lines = []
    remain = after
    
    while True:
        ln = remain.split("\n", 1)[0]
        header_lines.append(ln.strip())
        
        # Stop if found period
        if "." in ln:
            break
        
        # Add next line only if it seems part of header
        tail = remain[len(ln) + (1 if "\n" in remain else 0):]
        if not tail:
            break
        
        nxt = tail.split("\n", 1)[0].strip()
        if _HEADER_DATE_PATTERN.search(nxt):
            remain = tail
            continue
        
        # If next line is still mostly uppercase, consider it too
        letters = [ch for ch in nxt if ch.isalpha()]
        upp = sum(1 for ch in letters if ch.isupper()) if letters else 0
        if letters and upp / len(letters) >= 0.6:
            remain = tail
            continue
        break
    
    return header_lines


def extract_body_from_raw(header: str, raw: str) -> str:
    """Extract body text by removing header from raw text.
    
    Args:
        header: Header text
        raw: Raw text
        
    Returns:
        Body text
    """
    # Use prefix for robust case-insensitive matching
    pattern = re.escape(header[:80])
    m_body = re.search(pattern, raw, flags=re.I)
    if m_body:
        tail2 = raw[m_body.end():]
        body = re.sub(r'^[\s\-:—]+', '', tail2)
    else:
        body = raw
    return body
