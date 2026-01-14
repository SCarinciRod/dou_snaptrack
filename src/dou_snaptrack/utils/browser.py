from __future__ import annotations

import contextlib
import os
import re
from datetime import datetime

# use import absoluto para maior robustez
from dou_snaptrack.constants import BASE_DOU

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
