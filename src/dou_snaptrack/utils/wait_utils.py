"""Utilitários para waits condicionais otimizados.

Substitui wait_for_timeout fixos por polling inteligente que para
assim que a condição é satisfeita, economizando tempo.
"""

from __future__ import annotations

import time
from collections.abc import Callable


def wait_for_condition(
    frame,
    condition_fn: Callable[[], bool],
    timeout_ms: int = 500,
    poll_ms: int = 50,
    error_msg: str = "Timeout esperando condição"
) -> bool:
    """Espera até condição ser satisfeita ou timeout.

    Args:
        frame: Playwright frame/page
        condition_fn: Função que retorna True quando condição satisfeita
        timeout_ms: Timeout máximo em milissegundos
        poll_ms: Intervalo de polling em milissegundos
        error_msg: Mensagem de erro se timeout

    Returns:
        True se condição satisfeita, False se timeout

    Example:
        >>> # Esperar até dropdown ter opções
        >>> wait_for_condition(
        ...     frame,
        ...     lambda: len(frame.locator('[role=option]').all()) > 0,
        ...     timeout_ms=500
        ... )
    """
    start = time.time()
    elapsed = 0.0

    while elapsed < timeout_ms:
        try:
            if condition_fn():
                return True
        except Exception:
            pass  # Condição ainda não pode ser avaliada

        frame.wait_for_timeout(poll_ms)
        elapsed = (time.time() - start) * 1000

    return False


def wait_for_options_loaded(frame, min_count: int = 1, timeout_ms: int = 500) -> bool:
    """Espera até dropdown ter opções carregadas.

    Caso de uso comum: após abrir dropdown, esperar opções aparecerem.
    """
    # Alguns dropdowns (ex.: Selectize) não usam [role=option].
    # Preferir os seletores centrais quando disponíveis.
    try:
        from dou_utils.selection import OPTION_SELECTORS  # type: ignore

        option_css = ", ".join(OPTION_SELECTORS)
    except Exception:
        option_css = "[role=option]"

    return wait_for_condition(
        frame,
        lambda: frame.locator(option_css).count() >= min_count,
        timeout_ms=timeout_ms,
        poll_ms=50,
        error_msg=f"Timeout esperando {min_count} opções",
    )


def wait_for_network_idle(frame, timeout_ms: int = 2000) -> bool:
    """Espera até não haver requests de rede por 500ms.

    Útil após selecionar dropdown que dispara AJAX.
    """
    try:
        frame.wait_for_load_state("networkidle", timeout=timeout_ms)
        return True
    except Exception:
        return False
