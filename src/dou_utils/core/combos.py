"""
combos.py
Utilidades centrais para geração de combos entre níveis (N1, N2, N3).

Abstrai:
 - Cartesian product controlado
 - Limites de quantidade (max_combos)
 - dynamicN2 (gera apenas N1, posterga expansão de N2)
 - Normalização de estrutura

Futuras extensões:
 - Suporte a pesos, ordenações, sampling
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional


def generate_cartesian(
    level1: List[Dict[str, Any]],
    level2: List[Dict[str, Any]],
    level3: Optional[List[Dict[str, Any]]] = None,
    max_combos: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Gera produto cartesiano limitado (N1 x N2 [x N3]).
    """
    out: List[Dict[str, Any]] = []
    if not level1:
        return out
    if not level2:
        # Apenas N1
        for o1 in level1:
            out.append({
                "key1": o1.get("value"),
                "label1": o1.get("text")
            })
            if max_combos and len(out) >= max_combos:
                break
        return out

    use_level3 = bool(level3)
    if not use_level3:
        for o1 in level1:
            for o2 in level2:
                out.append({
                    "key1": o1.get("value"),
                    "label1": o1.get("text"),
                    "key2": o2.get("value"),
                    "label2": o2.get("text"),
                })
                if max_combos and len(out) >= max_combos:
                    return out
        return out
    else:
        for o1 in level1:
            for o2 in level2:
                for o3 in level3 or []:
                    out.append({
                        "key1": o1.get("value"),
                        "label1": o1.get("text"),
                        "key2": o2.get("value"),
                        "label2": o2.get("text"),
                        "key3": o3.get("value"),
                        "label3": o3.get("text"),
                    })
                    if max_combos and len(out) >= max_combos:
                        return out
        return out


def build_dynamic_n2(level1: List[Dict[str, Any]], max_combos: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retorna combos apenas com N1 marcados para expansão posterior.
    """
    out = []
    for o1 in level1:
        out.append({
            "key1": o1.get("value"),
            "label1": o1.get("text"),
            "_dynamicN2": True
        })
        if max_combos and len(out) >= max_combos:
            break
    return out


def build_combos_plan(
    date: str,
    secao: str,
    defaults: Dict[str, Any],
    query: Optional[str],
    combos: List[Dict[str, Any]],
    dynamic_n2: bool = False
) -> Dict[str, Any]:
    """
    Empacota a resposta padronizada para um plan.
    """
    return {
        "data": date,
        "secaoDefault": secao,
        "defaults": defaults or {},
        "query": query,
        "dynamicN2": bool(dynamic_n2),
        "combos": combos
    }
