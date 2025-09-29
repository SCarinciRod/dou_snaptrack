from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple
import re

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
    # Import lazy para evitar depender de Playwright quando não usado (ex.: plan/report)
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=not headful, slow_mo=slowmo)
    return p, browser

def new_context(browser, viewport=(1366, 900)):
    return browser.new_context(ignore_https_errors=True, viewport={"width": viewport[0], "height": viewport[1]})

def goto(page, url: str) -> None:
    if _page_goto:
        return _page_goto(page, url)
    # fallback mínimo
    print(f"[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)
    close_cookies(page)
