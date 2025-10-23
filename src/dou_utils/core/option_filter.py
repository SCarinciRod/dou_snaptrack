"""
option_filter.py

Funções utilitárias para filtrar listas de opções de dropdown.

Regras implementadas:
 - Remoção de sentinelas (via função fornecida)
 - Filtro por pick list (lista de valores/textos exatos)
 - Filtro por regex (case-insensitive)
 - Limite de quantidade
 - Suporte a matching acento-insensível (fold de diacríticos) quando
   o padrão fornecido não contém acentos explícitos.

Observação:
 - Mantida compatibilidade com chamadas existentes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any


def _strip_accents(s: str) -> str:
    """
    Remove diacríticos para comparação acento-insensível.
    """
    if not s:
        return s
    nf = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nf if unicodedata.category(ch) != "Mn")


def _pattern_has_accents(pat: str) -> bool:
    """
    Retorna True se o padrão possuir caracteres acentuados.
    Usado para decidir se tentamos fallback accent-fold.
    """
    return any(
        unicodedata.category(ch) == "Mn" or 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç'.find(ch) >= 0
        for ch in unicodedata.normalize("NFC", pat)
    )


def filter_options(
    options: list[dict[str, Any]],
    select_regex: str | None = None,
    pick_list: str | None = None,
    limit: int | None = None,
    drop_sentinels: bool = True,
    is_sentinel_fn: Callable[[dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """
    Filtra opções seguindo ordem de precedência:
      1. Remoção de sentinelas (se drop_sentinels=True)
      2. pick_list (se fornecido) - aceita se texto OU value estiver na lista
      3. select_regex (se fornecido) - regex case-insensitive.
         - Se o padrão não contiver acentos, faz fallback em versão sem acentos do texto/value.
      4. Sem filtros => retorna todas (exceto sentinelas).
      5. Aplica limit no final (após seleção).

    Retorna nova lista (não muta a original).
    """
    if not options:
        return []

    picks = None
    if pick_list:
        picks = {p.strip() for p in pick_list.split(",") if p.strip()}

    rx = re.compile(select_regex, re.IGNORECASE) if select_regex else None
    rx_has_accents = _pattern_has_accents(select_regex) if select_regex else False

    out: list[dict[str, Any]] = []

    for o in options:
        text = (o.get("text") or "").strip()
        value = (o.get("value") or "").strip()

        # 1. Sentinelas
        if drop_sentinels and is_sentinel_fn and is_sentinel_fn(o):
            continue

        # 2. Pick list (prioritário)
        if picks is not None:
            if (text not in picks) and (value not in picks):
                continue
            out.append(o)
        # 3. Regex
        elif rx:
            original_match = bool(rx.search(text) or rx.search(value))
            if original_match:
                out.append(o)
            else:
                # fallback acento-insensível somente se padrão não tem acentos
                if not rx_has_accents:
                    text_fold = _strip_accents(text)
                    value_fold = _strip_accents(value)
                    if rx.search(text_fold) or rx.search(value_fold):
                        out.append(o)
        else:
            # 4. Sem filtros
            out.append(o)

        if limit and len(out) >= limit:
            break

    return out
