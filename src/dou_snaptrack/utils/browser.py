from __future__ import annotations

import contextlib
import os
import re
from datetime import datetime
from typing import Any

# use import absoluto para maior robustez
from dou_snaptrack.constants import BASE_DOU, EAGENDAS_URL

# Delegar helpers para dou_utils.page_utils (fonte única de verdade)
try:
    from dou_utils.page_utils import (
        close_cookies as _page_close_cookies,
        goto as _page_goto,
        try_visualizar_em_lista as _page_try_visualizar_em_lista,
    )
except Exception:
    _page_goto = None
    _page_close_cookies = None
    _page_try_visualizar_em_lista = None

COOKIE_BUTTON_TEXTS = ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]

def fmt_date(date_str: str | None = None) -> str:
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")

def build_dou_url(date_dd_mm_yyyy: str, secao: str) -> str:
    return f"{BASE_DOU}?data={date_dd_mm_yyyy}&secao={secao}"

def build_url(site: str, path: str | None = None, **params) -> str:
    """Constrói URL para diferentes sites do projeto.

    Args:
        site: Nome do site ('dou' ou 'eagendas')
        path: Caminho adicional na URL (opcional)
        **params: Parâmetros de query string

    Returns:
        URL completa

    Examples:
        build_url('dou', date='01-01-2025', secao='DO1')
        build_url('eagendas', path='/agendas/list')
    """
    if site.lower() in ('dou', 'diario'):
        base = BASE_DOU
    elif site.lower() in ('eagendas', 'e-agendas', 'agendas'):
        base = EAGENDAS_URL
    else:
        raise ValueError(f"Site desconhecido: {site}")

    url = base.rstrip('/')
    if path:
        url = f"{url}/{path.lstrip('/')}"

    if params:
        query = '&'.join(f"{k}={v}" for k, v in params.items() if v is not None)
        url = f"{url}?{query}" if '?' not in url else f"{url}&{query}"

    return url


# ============================================================================
# VERSÕES ASYNC (para compatibilidade com Streamlit/asyncio)
# ============================================================================

async def goto_async(page, url: str, timeout_ms: int = 90_000) -> None:
    """Versão async de goto."""
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    await page.wait_for_timeout(500)
    # Fechar cookies
    for texto in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if await btn.count() > 0:
                first = btn.first
                if await first.is_visible():
                    await first.click(timeout=1500)
                    await page.wait_for_timeout(150)
        except Exception:
            pass


async def try_visualizar_em_lista_async(page) -> bool:
    """Versão async de try_visualizar_em_lista."""
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if await btn.count() > 0:
            first = btn.first
            if await first.is_visible():
                await first.click()
                await page.wait_for_load_state("networkidle", timeout=60_000)
                return True
    except Exception:
        pass
    return False


# ============================================================================
# VERSÕES SYNC (mantidas para retrocompatibilidade)
# ============================================================================

def close_cookies(page) -> None:
    if _page_close_cookies:
        return _page_close_cookies(page)
    # fallback mínimo
    for texto in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(150)
        except Exception:
            pass

def try_visualizar_em_lista(page) -> bool:
    if _page_try_visualizar_em_lista:
        return _page_try_visualizar_em_lista(page)
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    return False

def launch_browser(headful: bool = False, slowmo: int = 0):
    """Lança Chromium priorizando o Chrome instalado no sistema (channel),
    evitando download de browsers em ambientes com SSL restrito.

    Ordem de tentativa:
    1) channel="chrome" (usa Chrome estável instalado no Windows)
    2) executable_path via env PLAYWRIGHT_CHROME_PATH ou CHROME_PATH
    3) fallback padrão (usa binário do ms-playwright, pode exigir download)
    """
    from pathlib import Path

    from playwright.sync_api import sync_playwright  # type: ignore

    p = sync_playwright().start()
    launch_args: dict[str, Any] = {"headless": not headful, "slow_mo": slowmo}

    # 1) Tentar canais do sistema na ordem preferida
    prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1","true","yes")
    channels = ("msedge","chrome") if prefer_edge else ("chrome","msedge")
    for ch in channels:
        try:
            browser = p.chromium.launch(channel=ch, **launch_args)  # type: ignore
            return p, browser
        except Exception:
            continue

    # 2) Tentar usar caminho explícito do Chrome via env
    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if not exe:
        # caminhos comuns no Windows
        candidates = [
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ] if prefer_edge else [
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                exe = c
                break
    if exe and Path(exe).exists():
        try:
            browser = p.chromium.launch(executable_path=exe, **launch_args)  # type: ignore
            return p, browser
        except Exception:
            pass

    # 3) Fallback padrão (pode exigir download do ms-playwright)
    browser = p.chromium.launch(**launch_args)  # type: ignore
    return p, browser

def new_context(browser, viewport=(1366, 900)):
    return browser.new_context(ignore_https_errors=True, viewport={"width": viewport[0], "height": viewport[1]})

def goto(page, url: str, retries: int = 2) -> None:
    if _page_goto:
        # Se a implementação de dou_utils existir, delega (pode ter retry interno)
        return _page_goto(page, url)
    # fallback com retry/backoff
    print(f"[Abrindo] {url}")
    # Permitir override por env
    try:
        retries_env = int(os.environ.get("DOU_GOTO_RETRIES", "").strip() or retries)
        retries = max(0, min(5, retries_env))
    except Exception:
        pass
    last_err = None
    for attempt in range(retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Prefer readiness by selector
            try:
                page.wait_for_selector("header, .conteudo, #conteudo, iframe", timeout=30_000)
            except Exception:
                # Fallback to a shorter networkidle wait
                page.wait_for_load_state("networkidle", timeout=30_000)
            close_cookies(page)
            return
        except Exception as e:
            last_err = e
            msg = str(e)
            # Repetir em erros transitórios comuns
            transient = (
                "ERR_CONNECTION_RESET" in msg
                or "net::ERR_" in msg
                or "timeout" in msg.lower()
                or ("Navigation" in msg and "failed" in msg.lower())
            )
            if attempt < retries and transient:
                try:
                    # Pequeno backoff e reset suave do page
                    page.wait_for_timeout(400)
                    with contextlib.suppress(Exception):
                        page.goto("about:blank", timeout=5_000)
                    page.wait_for_timeout(300)
                except Exception:
                    pass
                continue
            # Sem mais tentativas ou erro não transitório
            break
    # Se chegou aqui, propaga o último erro
    raise last_err if last_err else RuntimeError("Falha ao navegar")
