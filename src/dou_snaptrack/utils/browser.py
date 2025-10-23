from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple, Any, Dict
import re
import os

# use import absoluto para maior robustez
from dou_snaptrack.constants import BASE_DOU

# Delegar helpers para dou_utils.page_utils (fonte única de verdade)
try:
    from dou_utils.page_utils import (
        goto as _page_goto,
        close_cookies as _page_close_cookies,
        try_visualizar_em_lista as _page_try_visualizar_em_lista,
    )
except Exception:
    _page_goto = None
    _page_close_cookies = None
    _page_try_visualizar_em_lista = None

COOKIE_BUTTON_TEXTS = ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]

def fmt_date(date_str: Optional[str] = None) -> str:
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")

def build_dou_url(date_dd_mm_yyyy: str, secao: str) -> str:
    return f"{BASE_DOU}?data={date_dd_mm_yyyy}&secao={secao}"

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
    # Garantir loop Proactor no Windows antes de iniciar Playwright
    try:
        import sys as _sys, asyncio as _asyncio
        if _sys.platform.startswith("win"):
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
            _asyncio.set_event_loop(_asyncio.new_event_loop())
    except Exception:
        pass
    from playwright.sync_api import sync_playwright  # type: ignore
    from pathlib import Path

    p = sync_playwright().start()
    launch_args: Dict[str, Any] = dict(headless=not headful, slow_mo=slowmo)

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
                or "Navigation" in msg and "failed" in msg.lower()
            )
            if attempt < retries and transient:
                try:
                    # Pequeno backoff e reset suave do page
                    page.wait_for_timeout(400)
                    try:
                        page.goto("about:blank", timeout=5_000)
                    except Exception:
                        pass
                    page.wait_for_timeout(300)
                except Exception:
                    pass
                continue
            # Sem mais tentativas ou erro não transitório
            break
    # Se chegou aqui, propaga o último erro
    raise last_err if last_err else RuntimeError("Falha ao navegar")
