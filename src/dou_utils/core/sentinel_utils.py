"""
sentinel_utils.py
Funções unificadas para detecção de placeholders / sentinelas em dropdowns.

Critérios:
 - Texto vazio ou None
 - Prefixos comuns: "selecionar", "selecione", "todos", "todas"
 - Valores '0' ou apenas dígitos curtos sem label significativo
 - Normalização insensível a acentos e caixa

Uso:
  from dou_utils.core.sentinel_utils import is_placeholder_text, is_sentinel_option

Futuro:
 - Poderemos estender com dicionário configurável via SETTINGS.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Regex de prefixos/sentinelas
_PREFIX_PAT = re.compile(r"^\s*(selecionar|selecione|todos|todas)\b", re.IGNORECASE)
_ONLY_NUM_PAT = re.compile(r"^\d{1,2}$")


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def is_placeholder_text(text: str | None) -> bool:
    """
    Retorna True se o texto aparenta ser placeholder/sentinela.
    """
    if not text:
        return True
    raw = text.strip()
    norm = _normalize(raw)
    if not norm:
        return True
    if _PREFIX_PAT.search(norm):
        return True
    if norm in {"", "0", "-", "--"}:
        return True
    # valores numéricos simples sem contexto costumam ser placeholders
    if _ONLY_NUM_PAT.match(norm):
        return True
    return False


def is_sentinel_option(opt: dict[str, Any] | None) -> bool:
    """
    Avalia um dicionário de opção (com chaves esperadas 'text' e/ou 'value').

    Ex:
        if is_sentinel_option(o): continue
    """
    if not opt or not isinstance(opt, dict):
        return True
    txt = opt.get("text")
    val = opt.get("value")
    # Se ambos parecem placeholders → sentinela
    if is_placeholder_text(txt) and is_placeholder_text(val):
        return True
    # Se texto vazio e value placeholder
    if is_placeholder_text(txt):
        return True
    return False
