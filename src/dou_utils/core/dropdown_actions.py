"""
dropdown_actions.py
Ações comuns sobre dropdowns (abrir, selecionar, coletar opções).

Reúne:
 - Estratégias de abertura (delegando para dropdown_strategies.open_dropdown_robust)
 - Seleção em <select> nativos
 - Coleta de opções de dropdown custom (collect_open_list_options)
"""

from __future__ import annotations

from typing import Any

from ..dropdowns import (
    collect_open_list_options,
    is_select as _is_select,
    open_dropdown_robust,
    read_select_options as _read_select_options,
)
from ..log_utils import get_logger

logger = get_logger(__name__)


def open_dropdown(frame, handle, strategy_order=None, delay_ms: int = 120) -> bool:
    try:
        return open_dropdown_robust(frame, handle, strategy_order=strategy_order, delay_ms=delay_ms)
    except Exception as e:
        logger.debug("Falha open_dropdown", extra={"err": str(e)})
        return False


def select_in_native(handle, value_or_text: str) -> bool:
    """
    Seleciona uma opção por value ou text em um <select>.
    """
    if not _is_select(handle):
        return False
    try:
        opts = _read_select_options(handle)
        target_val = None
        for o in opts:
            if (o.get("value") or "") == value_or_text or (o.get("text") or "") == value_or_text:
                target_val = o.get("value") or o.get("text")
                break
        if target_val is None:
            return False
        handle.select_option(value=target_val)
        return True
    except Exception:
        return False


def select_by_text(handle, text: str) -> bool:
    if not _is_select(handle):
        return False
    try:
        opts = _read_select_options(handle)
        for o in opts:
            if (o.get("text") or "") == text:
                handle.select_option(value=o.get("value") or o.get("text"))
                return True
        return False
    except Exception:
        return False


def select_by_value(handle, value: str) -> bool:
    if not _is_select(handle):
        return False
    try:
        handle.select_option(value=value)
        return True
    except Exception:
        return False


def collect_native_options(handle) -> list[dict[str, Any]]:
    if not _is_select(handle):
        return []
    try:
        return _read_select_options(handle) or []
    except Exception:
        return []


def ensure_open_then_collect_custom(frame, handle) -> list[dict[str, Any]]:
    if _is_select(handle):
        return collect_native_options(handle)
    opened = open_dropdown(frame, handle)
    if not opened:
        return []
    try:
        opts = collect_open_list_options(frame)
    except Exception:
        opts = []
    return opts
