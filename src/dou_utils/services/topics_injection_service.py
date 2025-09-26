"""
topics_injection_service.py
Injeta tópicos (assuntos) extraídos de DOCX em um batch_config existente,
fazendo matching fuzzy / aliases.

Fluxo:
 1. Recebe plan (dict) e topics_map { heading: [terms...] }
 2. Recebe lista de assuntos desejados (ex: ["Saúde", "Educação"])
 3. Faz best match para cada assunto usando tokens e aliases
 4. Gera entries:
      {
        "name": <heading>,
        "query": "palavra1 palavra2 ...",
        "summary_keywords": [...],
        "summary_lines": N (param),
        "summary_mode": M (param)
      }
 5. Injeta em plan["topics"]

Função:
  inject_topics_into_plan(plan_dict, topics_map, requested, summary_lines=5,
                          summary_mode="center", aliases=None) -> plan_dict
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return s


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s or ""))


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _best_match(name: str, keys: List[str], aliases: Dict[str, List[str]]) -> Tuple[Optional[str], float]:
    n = _norm(name)
    # Aliases
    for k, alts in aliases.items():
        variants = [k] + (alts or [])
        if n in [_norm(v) for v in variants]:
            return k, 0.99
    best, bests = None, 0.0
    for k in keys:
        nk = _norm(k)
        s = _similarity(n, nk)
        if n and (n in nk or nk in n):
            s = max(s, 0.98)
        if s > bests:
            bests, best = s, k
    return (best, bests) if bests >= 0.45 else (None, bests)


def _build_query(keywords: List[str]) -> str:
    # Simples: tokens unidos com espaço (efeito AND na busca local do DOU)
    return " ".join(sorted({w for w in keywords if w}))


def inject_topics_into_plan(
    plan: Dict,
    topics_map: Dict[str, List[str]],
    requested: List[str],
    summary_lines: int = 5,
    summary_mode: str = "center",
    aliases: Optional[Dict[str, List[str]]] = None
) -> Dict:
    aliases = aliases or {}
    if not topics_map:
        raise ValueError("topics_map vazio.")
    added = []
    keys = list(topics_map.keys())

    for name in requested:
        best, score = _best_match(name, keys, aliases)
        if not best:
            continue
        kws = topics_map.get(best, [])
        added.append({
            "name": best,
            "query": _build_query(kws),
            "summary_keywords": kws,
            "summary_lines": summary_lines,
            "summary_mode": summary_mode
        })

    if not added:
        raise ValueError("Nenhum tópico pôde ser mapeado (verifique nomes/aliases).")

    plan = dict(plan)
    plan["topics"] = added
    return plan
