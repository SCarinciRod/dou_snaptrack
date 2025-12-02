"""
Factory centralizada para criação de browsers Playwright.

Este módulo fornece uma interface unificada para criar browsers e contextos,
centralizando configurações e eliminando código duplicado.

Uso básico (sync):
    >>> from dou_snaptrack.utils.browser_factory import BrowserFactory
    >>> with BrowserFactory.create() as browser:
    ...     page = browser.new_page()
    ...     page.goto("https://example.com")

Uso básico (async):
    >>> async with BrowserFactory.create_async() as browser:
    ...     page = await browser.new_page()
    ...     await page.goto("https://example.com")

Configuração customizada:
    >>> config = BrowserConfig(headless=False, timeout=60000)
    >>> with BrowserFactory.create(config=config) as browser:
    ...     page = browser.new_page()
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dou_snaptrack.constants import (
    BROWSER_CHANNELS,
    CHROME_PATHS,
    EDGE_PATHS,
    TIMEOUT_PAGE_DEFAULT,
    TIMEOUT_PAGE_SLOW,
)
from dou_snaptrack.utils.exceptions import BrowserNotFoundError

if TYPE_CHECKING:
    from playwright.async_api import (
        Browser as AsyncBrowser,
        BrowserContext as AsyncBrowserContext,
        Playwright as AsyncPlaywright,
    )
    from playwright.sync_api import (
        Browser as SyncBrowser,
        BrowserContext as SyncBrowserContext,
        Playwright as SyncPlaywright,
    )


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================


@dataclass
class BrowserConfig:
    """
    Configuração para criação de browser.

    Attributes:
        headless: Rodar sem janela visível.
        timeout: Timeout padrão em ms para operações.
        viewport_width: Largura da viewport.
        viewport_height: Altura da viewport.
        ignore_https_errors: Ignorar erros de certificado SSL.
        block_resources: Bloquear imagens, fontes e trackers.
        slow_mo: Delay entre ações (para debug).
        prefer_edge: Preferir Edge sobre Chrome.
    """

    headless: bool = True
    timeout: int = TIMEOUT_PAGE_DEFAULT
    viewport_width: int = 1366
    viewport_height: int = 900
    ignore_https_errors: bool = True
    block_resources: bool = False
    slow_mo: int = 0
    prefer_edge: bool = False

    # Recursos a bloquear quando block_resources=True
    blocked_patterns: list[str] = field(
        default_factory=lambda: [
            "**/*.png",
            "**/*.jpg",
            "**/*.jpeg",
            "**/*.gif",
            "**/*.svg",
            "**/*.ico",
            "**/*.woff",
            "**/*.woff2",
            "**/*.ttf",
            "**/*google-analytics*",
            "**/*googletagmanager*",
            "**/*facebook*",
            "**/*doubleclick*",
        ]
    )


# Configurações pré-definidas
CONFIG_FAST = BrowserConfig(headless=True, block_resources=True, timeout=TIMEOUT_PAGE_DEFAULT)
CONFIG_SLOW = BrowserConfig(headless=True, timeout=TIMEOUT_PAGE_SLOW)
CONFIG_DEBUG = BrowserConfig(headless=False, slow_mo=100, timeout=TIMEOUT_PAGE_SLOW)
CONFIG_EAGENDAS = BrowserConfig(headless=True, timeout=TIMEOUT_PAGE_SLOW)  # E-Agendas é lento


# =============================================================================
# DETECÇÃO DE BROWSER
# =============================================================================


def find_system_browser(prefer_edge: bool = False) -> str | None:
    """
    Encontra o caminho de um browser instalado no sistema.

    Args:
        prefer_edge: Se True, tenta Edge antes de Chrome.

    Returns:
        Caminho do executável ou None se não encontrado.
    """
    paths = (EDGE_PATHS + CHROME_PATHS) if prefer_edge else (CHROME_PATHS + EDGE_PATHS)

    for path in paths:
        if Path(path).exists():
            return path

    # Verificar variáveis de ambiente
    for env_var in ("PLAYWRIGHT_CHROME_PATH", "CHROME_PATH"):
        exe = os.environ.get(env_var)
        if exe and Path(exe).exists():
            return exe

    return None


def get_browser_channels(prefer_edge: bool = False) -> list[str]:
    """
    Retorna lista de channels para tentar, na ordem de preferência.

    Args:
        prefer_edge: Se True, Edge vem primeiro.

    Returns:
        Lista de channels ("chrome", "msedge").
    """
    if prefer_edge:
        return ["msedge", "chrome"]
    return list(BROWSER_CHANNELS)


# =============================================================================
# FACTORY (SYNC)
# =============================================================================


class BrowserFactory:
    """
    Factory para criação de browsers Playwright (sync e async).

    Centraliza a lógica de:
    - Detecção de browser do sistema
    - Fallback entre channels
    - Configuração de contexto
    - Bloqueio de recursos
    """

    @staticmethod
    @contextmanager
    def create(
        config: BrowserConfig | None = None,
    ) -> Generator[SyncBrowserContext, None, None]:
        """
        Cria um contexto de browser configurado (sync).

        Context manager que garante cleanup automático.

        Args:
            config: Configuração do browser. Usa padrão se não fornecida.

        Yields:
            BrowserContext configurado.

        Raises:
            BrowserNotFoundError: Nenhum browser compatível encontrado.
            BrowserLaunchError: Falha ao iniciar o browser.

        Example:
            >>> with BrowserFactory.create() as ctx:
            ...     page = ctx.new_page()
            ...     page.goto("https://example.com")
        """
        from playwright.sync_api import sync_playwright

        config = config or BrowserConfig()
        prefer_edge = config.prefer_edge or os.environ.get("DOU_PREFER_EDGE", "").lower() in (
            "1",
            "true",
            "yes",
        )

        p: SyncPlaywright = sync_playwright().start()
        browser: SyncBrowser | None = None
        context: SyncBrowserContext | None = None

        try:
            # Tentar channels do sistema
            channels = get_browser_channels(prefer_edge)
            launch_args = {"headless": config.headless, "slow_mo": config.slow_mo}

            for channel in channels:
                try:
                    browser = p.chromium.launch(channel=channel, **launch_args)
                    break
                except Exception:
                    continue

            # Fallback para executável direto
            if not browser:
                exe = find_system_browser(prefer_edge)
                if exe:
                    try:
                        browser = p.chromium.launch(executable_path=exe, **launch_args)
                    except Exception:
                        pass

            # Último fallback - binário do Playwright
            if not browser:
                try:
                    browser = p.chromium.launch(**launch_args)
                except Exception as e:
                    raise BrowserNotFoundError(
                        f"Nenhum browser disponível. Instale Chrome ou Edge. Erro: {e}"
                    ) from e

            # Criar contexto
            context = browser.new_context(
                ignore_https_errors=config.ignore_https_errors,
                viewport={"width": config.viewport_width, "height": config.viewport_height},
            )
            context.set_default_timeout(config.timeout)

            # Configurar bloqueio de recursos
            if config.block_resources:
                for pattern in config.blocked_patterns:
                    context.route(pattern, lambda route: route.abort())

            yield context

        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            try:
                p.stop()
            except Exception:
                pass

    @staticmethod
    @asynccontextmanager
    async def create_async(
        config: BrowserConfig | None = None,
    ):
        """
        Cria um contexto de browser configurado (async).

        Context manager assíncrono que garante cleanup automático.

        Args:
            config: Configuração do browser. Usa padrão se não fornecida.

        Yields:
            BrowserContext assíncrono configurado.

        Example:
            >>> async with BrowserFactory.create_async() as ctx:
            ...     page = await ctx.new_page()
            ...     await page.goto("https://example.com")
        """
        from playwright.async_api import async_playwright

        config = config or BrowserConfig()
        prefer_edge = config.prefer_edge or os.environ.get("DOU_PREFER_EDGE", "").lower() in (
            "1",
            "true",
            "yes",
        )

        p: AsyncPlaywright = await async_playwright().start()
        browser: AsyncBrowser | None = None
        context: AsyncBrowserContext | None = None

        try:
            # Tentar channels do sistema
            channels = get_browser_channels(prefer_edge)
            launch_args = {"headless": config.headless, "slow_mo": config.slow_mo}

            for channel in channels:
                try:
                    browser = await p.chromium.launch(channel=channel, **launch_args)
                    break
                except Exception:
                    continue

            # Fallback para executável direto
            if not browser:
                exe = find_system_browser(prefer_edge)
                if exe:
                    try:
                        browser = await p.chromium.launch(executable_path=exe, **launch_args)
                    except Exception:
                        pass

            # Último fallback - binário do Playwright
            if not browser:
                try:
                    browser = await p.chromium.launch(**launch_args)
                except Exception as e:
                    raise BrowserNotFoundError(
                        f"Nenhum browser disponível. Instale Chrome ou Edge. Erro: {e}"
                    ) from e

            # Criar contexto
            context = await browser.new_context(
                ignore_https_errors=config.ignore_https_errors,
                viewport={"width": config.viewport_width, "height": config.viewport_height},
            )
            context.set_default_timeout(config.timeout)

            # Configurar bloqueio de recursos
            if config.block_resources:
                for pattern in config.blocked_patterns:
                    await context.route(pattern, lambda route: route.abort())

            yield context

        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            try:
                await p.stop()
            except Exception:
                pass

    @staticmethod
    def create_page(
        config: BrowserConfig | None = None,
    ) -> Generator[Any, None, None]:
        """
        Atalho para criar browser + página diretamente.

        Útil quando só precisa de uma página.

        Example:
            >>> with BrowserFactory.create_page() as page:
            ...     page.goto("https://example.com")
        """
        with BrowserFactory.create(config) as ctx:
            page = ctx.new_page()
            yield page
