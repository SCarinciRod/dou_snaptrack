"""
PATCH CRÍTICO para _summarize_item em bulletin_utils.py

O problema: A versão original de _summarize_item está cortando o texto antes de passar para summarizer_fn.
A solução: Substituir por versão simplificada que apenas passa o texto sem modificações.
"""
from collections.abc import Callable
from typing import Any


def _summarize_item_fixed(
    it: dict[str, Any],
    summarizer_fn: Callable | None,
    summarize: bool,
    keywords: list[str] | None,
    max_lines: int,
    mode: str
) -> str | None:
    """Versão corrigida que NÃO corta o texto antes de sumarizar."""
    if not summarize or not summarizer_fn:
        return None

    base = it.get("texto") or it.get("ementa") or ""
    if not base:
        return None

    # Modo derivado por tipo de ato
    derived_mode = (mode or "center").lower()
    try:
        tipo = (it.get("tipo_ato") or "").strip().lower()
        if tipo.startswith("decreto") or tipo.startswith("portaria") or tipo.startswith("resolu") or tipo.startswith("despacho"):
            derived_mode = "lead"
    except Exception:
        pass

    snippet = None
    try:
        # Chamada preferida: (text, max_lines, mode, keywords)
        snippet = summarizer_fn(base, max_lines, derived_mode, keywords)
        if not snippet or not snippet.strip():
            return None
    except TypeError:
        # Alternativas
        try:
            snippet = summarizer_fn(base, max_lines, keywords, derived_mode)  # type: ignore
            if not snippet or not snippet.strip():
                return None
        except TypeError:
            try:
                snippet = summarizer_fn(base, max_lines, derived_mode)  # type: ignore
                if not snippet or not snippet.strip():
                    return None
            except Exception:
                return None
    except Exception:
        return None

    return snippet


# Aplicar patch automaticamente ao importar
def apply_patch():
    """Aplica o patch à função _summarize_item."""
    try:
        from dou_utils.bulletin import generator
        generator._summarize_item = _summarize_item_fixed
        print("[PATCH] _summarize_item substituída por versão corrigida")
    except Exception as e:
        print(f"[PATCH ERROR] Falha ao aplicar patch: {e}")


# Auto-aplicar quando importado
apply_patch()
