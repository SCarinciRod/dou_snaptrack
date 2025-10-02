"""
polling.py
Utilidades centrais para aguardar mudanças em dropdowns (<select> ou outros
que tenham opções acessíveis) de forma consistente.

Motivações:
 - Evitar duplicação de loops de polling
 - Oferecer uma API declarativa reutilizável no mapper, plan e cascade executor

Modelo atual: síncrono (Playwright sync). Versão async pode ser adicionada depois.
"""

from __future__ import annotations
import time
import hashlib
from typing import List, Dict, Any, Optional, Callable

from ..dropdown_utils import _read_select_options
from ..log_utils import get_logger

logger = get_logger(__name__)


def snapshot_options(select_handle) -> List[Dict[str, Any]]:
    """
    Lê opções de um <select>. Para dropdown custom, caller deve abrir e usar
    outra função de coleta antes de chamar este polling.
    """
    try:
        return _read_select_options(select_handle) or []
    except Exception:
        return []


def options_hash(options: List[Dict[str, Any]]) -> str:
    """
    Hash estável das opções (value,text) para detecção de mudança.
    """
    try:
        data = "|".join(f"{o.get('value')}::{o.get('text')}" for o in options)
        return hashlib.sha1(data.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def wait_for_options_change(
    frame,
    select_handle,
    before: List[Dict[str, Any]],
    timeout_ms: int = 3000,
    poll_interval_ms: int = 250,
    require_growth: bool = False,
    min_delta: int = 1,
    custom_reader: Optional[Callable[[], List[Dict[str, Any]]]] = None
) -> List[Dict[str, Any]]:
    """
    Aguarda mudança no conjunto de opções.

    Parâmetros:
      select_handle: handle do <select> (ou ignorado se custom_reader for usado)
      before: snapshot inicial
      timeout_ms: tempo máximo
      poll_interval_ms: intervalo de polling
      require_growth: se True, só retorna quando houver aumento no número de opções
      min_delta: crescimento mínimo exigido (se require_growth=True)
      custom_reader: função alternativa para ler opções (dropdown custom aberto)

    Retorna:
      Lista final de opções (ou a original se não houve mudança)
    """
    deadline = time.time() + timeout_ms / 1000.0
    base_len = len(before)
    base_hash = options_hash(before)

    reader = custom_reader or (lambda: snapshot_options(select_handle))

    while time.time() < deadline:
        try:
            current = reader()
        except Exception:
            current = []
        curr_hash = options_hash(current)

        grew = len(current) >= base_len + min_delta
        changed = curr_hash != base_hash

        if require_growth:
            if grew:
                return current
        else:
            if grew or changed:
                return current

        try:
            frame.wait_for_timeout(poll_interval_ms)
        except Exception:
            time.sleep(poll_interval_ms / 1000.0)

    return before  # Sem mudança significativa


def wait_repopulation(
    frame,
    select_handle,
    previous_count: int,
    timeout_ms: int = 6000,
    poll_interval_ms: int = 250,
    min_growth: int = 1
) -> bool:
    """
    Aguarda repopulação (crescimento) simples de um <select>.

    Retorna True se cresceu, False caso contrário.
    """
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        opts = snapshot_options(select_handle)
        if len(opts) >= previous_count + min_growth:
            return True
        try:
            frame.wait_for_timeout(poll_interval_ms)
        except Exception:
            time.sleep(poll_interval_ms / 1000.0)
    return False
