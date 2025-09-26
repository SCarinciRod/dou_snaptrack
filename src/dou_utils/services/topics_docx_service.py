"""
topics_docx_service.py
Extrai tópicos e listas (bullets ou numerados) de um DOCX para futura
injeção em batch_config como 'topics'.

Heurística:
 - Cabeçalhos = parágrafos em negrito OU com forte proporção de letras maiúsculas
 - Itens = linhas com prefixos de bullet ou listas numeradas/romanas

Função principal:
  extract_topics_from_docx(path) -> Dict[str, List[str]]
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import re
from docx import Document

BULLET_PREFIXES = ("-", "–", "—", "•", "·", "*")


def _is_header(text: str, has_bold: bool) -> bool:
    if not text:
        return False
    t = text.strip()
    if t.startswith(BULLET_PREFIXES):
        return False
    if has_bold:
        return True
    # heurística uppercase
    up = re.sub(r"[^A-ZÁÉÍÓÚÂÊÔÃÕÇ ]", "", t)
    return len(up) >= max(8, int(len(t) * 0.6))


def extract_topics_from_docx(docx_path: str | Path) -> Dict[str, List[str]]:
    p = Path(docx_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo DOCX não encontrado: {p}")
    if p.suffix.lower() != ".docx":
        raise ValueError("Extensão inválida. Use .docx")

    doc = Document(str(p))
    topics: Dict[str, List[str]] = {}
    current = None
    for para in doc.paragraphs:
        txt = re.sub(r"\s+", " ", (para.text or "").strip())
        if not txt:
            continue
        has_bold = any((r.bold and re.sub(r"\s+", " ", r.text.strip())) for r in para.runs)
        if _is_header(txt, has_bold):
            current = txt
            topics.setdefault(current, [])
            continue
        if current and (
            txt.startswith(BULLET_PREFIXES) or
            re.match(r"^(\(?\d+\)?[.)]|[ivxlcdm]+\.)\s+", txt, re.I)
        ):
            cleaned = re.sub(r"^(\(?\d+\)?[.)]|[ivxlcdm]+\.)\s+", "", txt)
            cleaned = cleaned.lstrip("".join(BULLET_PREFIXES)).strip()
            if cleaned and cleaned not in topics[current]:
                topics[current].append(cleaned)
    return topics
