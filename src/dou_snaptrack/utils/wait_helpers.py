"""
Utilitários de espera para Playwright.

Este módulo fornece funções de espera inteligentes que substituem
wait_for_timeout por esperas condicionais quando possível.

Exemplo:
    >>> from dou_snaptrack.utils.wait_helpers import wait_for_dropdown_ready
    >>> await wait_for_dropdown_ready(page, "#selectize-orgao")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dou_snaptrack.constants import (
    TIMEOUT_ELEMENT_FAST,
    TIMEOUT_ELEMENT_NORMAL,
    TIMEOUT_ELEMENT_SLOW,
    WAIT_ANGULAR_INIT,
    WAIT_ANGULAR_LOAD,
    WAIT_MEDIUM,
    WAIT_SHORT,
)

if TYPE_CHECKING:
    from playwright.async_api import Page as AsyncPage
    from playwright.sync_api import Page as SyncPage


# =============================================================================
# SELETORES COMUNS
# =============================================================================

# Seletores para detectar que dropdown está pronto
DROPDOWN_READY_SELECTORS = [
    ".selectize-dropdown-content:not(:empty)",
    "[role='listbox']:not(:empty)",
    ".select2-results:not(:empty)",
    "select option:not([value=''])",
]

# Seletores para detectar que AngularJS inicializou
ANGULAR_READY_SELECTORS = [
    "[ng-app]",
    ".ng-scope",
    "[data-ng-app]",
]

# Seletores para detectar que Selectize inicializou
SELECTIZE_READY_JS = """
(selector) => {
    const el = document.querySelector(selector);
    return el && el.selectize && Object.keys(el.selectize.options || {}).length > 0;
}
"""


# =============================================================================
# VERSÕES ASYNC
# =============================================================================


async def wait_for_angular_async(page: AsyncPage, timeout: int = WAIT_ANGULAR_INIT) -> bool:
    """
    Aguarda AngularJS inicializar.

    Args:
        page: Página Playwright async.
        timeout: Timeout em milissegundos.

    Returns:
        True se Angular foi detectado, False caso contrário.
    """
    try:
        for selector in ANGULAR_READY_SELECTORS:
            try:
                await page.wait_for_selector(selector, state="attached", timeout=timeout)
                return True
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: aguardar tempo fixo
    await page.wait_for_timeout(timeout)
    return False


async def wait_for_selectize_async(
    page: AsyncPage,
    element_id: str,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
    min_options: int = 1,
) -> bool:
    """
    Aguarda Selectize inicializar e popular com opções.

    Args:
        page: Página Playwright async.
        element_id: ID do elemento Selectize (sem #).
        timeout: Timeout em milissegundos.
        min_options: Número mínimo de opções para considerar pronto.

    Returns:
        True se Selectize está pronto, False caso timeout.
    """
    js_check = f"""
    () => {{
        const el = document.getElementById('{element_id}');
        return el && el.selectize && Object.keys(el.selectize.options || {{}}).length >= {min_options};
    }}
    """
    try:
        await page.wait_for_function(js_check, timeout=timeout)
        return True
    except Exception:
        return False


async def wait_for_dropdown_ready_async(
    page: AsyncPage,
    selector: str,
    timeout: int = TIMEOUT_ELEMENT_NORMAL,
) -> bool:
    """
    Aguarda dropdown estar visível e com opções.

    Args:
        page: Página Playwright async.
        selector: Seletor CSS do dropdown.
        timeout: Timeout em milissegundos.

    Returns:
        True se dropdown está pronto, False caso timeout.
    """
    try:
        # Primeiro aguarda elemento existir
        await page.wait_for_selector(selector, state="attached", timeout=timeout)

        # Depois aguarda uma das condições de dropdown pronto
        for ready_selector in DROPDOWN_READY_SELECTORS:
            try:
                await page.wait_for_selector(ready_selector, state="visible", timeout=timeout // 2)
                return True
            except Exception:
                continue

        # Fallback: aguardar estabilização
        await page.wait_for_timeout(WAIT_SHORT)
        return True
    except Exception:
        return False


async def wait_for_options_change_async(
    page: AsyncPage,
    element_id: str,
    initial_count: int,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
) -> bool:
    """
    Aguarda número de opções do Selectize mudar.

    Útil após selecionar um dropdown pai para aguardar filhos carregarem.

    Args:
        page: Página Playwright async.
        element_id: ID do elemento Selectize (sem #).
        initial_count: Contagem inicial de opções.
        timeout: Timeout em milissegundos.

    Returns:
        True se contagem mudou, False caso timeout.
    """
    js_check = f"""
    () => {{
        const el = document.getElementById('{element_id}');
        if (!el || !el.selectize) return false;
        return Object.keys(el.selectize.options || {{}}).length !== {initial_count};
    }}
    """
    try:
        await page.wait_for_function(js_check, timeout=timeout)
        return True
    except Exception:
        return False


async def wait_for_network_idle_async(
    page: AsyncPage,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
) -> bool:
    """
    Aguarda rede ficar ociosa (sem requests pendentes).

    Args:
        page: Página Playwright async.
        timeout: Timeout em milissegundos.

    Returns:
        True se rede está ociosa, False caso timeout.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    except Exception:
        return False


# =============================================================================
# VERSÕES SYNC
# =============================================================================


def wait_for_angular(page: SyncPage, timeout: int = WAIT_ANGULAR_INIT) -> bool:
    """
    Aguarda AngularJS inicializar (versão sync).

    Args:
        page: Página Playwright sync.
        timeout: Timeout em milissegundos.

    Returns:
        True se Angular foi detectado, False caso contrário.
    """
    try:
        for selector in ANGULAR_READY_SELECTORS:
            try:
                page.wait_for_selector(selector, state="attached", timeout=timeout)
                return True
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: aguardar tempo fixo
    page.wait_for_timeout(timeout)
    return False


def wait_for_selectize(
    page: SyncPage,
    element_id: str,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
    min_options: int = 1,
) -> bool:
    """
    Aguarda Selectize inicializar e popular com opções (versão sync).

    Args:
        page: Página Playwright sync.
        element_id: ID do elemento Selectize (sem #).
        timeout: Timeout em milissegundos.
        min_options: Número mínimo de opções para considerar pronto.

    Returns:
        True se Selectize está pronto, False caso timeout.
    """
    js_check = f"""
    () => {{
        const el = document.getElementById('{element_id}');
        return el && el.selectize && Object.keys(el.selectize.options || {{}}).length >= {min_options};
    }}
    """
    try:
        page.wait_for_function(js_check, timeout=timeout)
        return True
    except Exception:
        return False


def wait_for_dropdown_ready(
    page: SyncPage,
    selector: str,
    timeout: int = TIMEOUT_ELEMENT_NORMAL,
) -> bool:
    """
    Aguarda dropdown estar visível e com opções (versão sync).

    Args:
        page: Página Playwright sync.
        selector: Seletor CSS do dropdown.
        timeout: Timeout em milissegundos.

    Returns:
        True se dropdown está pronto, False caso timeout.
    """
    try:
        # Primeiro aguarda elemento existir
        page.wait_for_selector(selector, state="attached", timeout=timeout)

        # Depois aguarda uma das condições de dropdown pronto
        for ready_selector in DROPDOWN_READY_SELECTORS:
            try:
                page.wait_for_selector(ready_selector, state="visible", timeout=timeout // 2)
                return True
            except Exception:
                continue

        # Fallback: aguardar estabilização
        page.wait_for_timeout(WAIT_SHORT)
        return True
    except Exception:
        return False


def wait_for_options_change(
    page: SyncPage,
    element_id: str,
    initial_count: int,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
) -> bool:
    """
    Aguarda número de opções do Selectize mudar (versão sync).

    Útil após selecionar um dropdown pai para aguardar filhos carregarem.

    Args:
        page: Página Playwright sync.
        element_id: ID do elemento Selectize (sem #).
        initial_count: Contagem inicial de opções.
        timeout: Timeout em milissegundos.

    Returns:
        True se contagem mudou, False caso timeout.
    """
    js_check = f"""
    () => {{
        const el = document.getElementById('{element_id}');
        if (!el || !el.selectize) return false;
        return Object.keys(el.selectize.options || {{}}).length !== {initial_count};
    }}
    """
    try:
        page.wait_for_function(js_check, timeout=timeout)
        return True
    except Exception:
        return False


def wait_for_network_idle(
    page: SyncPage,
    timeout: int = TIMEOUT_ELEMENT_SLOW,
) -> bool:
    """
    Aguarda rede ficar ociosa (sem requests pendentes) (versão sync).

    Args:
        page: Página Playwright sync.
        timeout: Timeout em milissegundos.

    Returns:
        True se rede está ociosa, False caso timeout.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    except Exception:
        return False
