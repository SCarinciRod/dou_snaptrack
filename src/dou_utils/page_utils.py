# page_utils.py
# Funções utilitárias para navegação e manipulação de páginas com Playwright

import contextlib
import re


def goto(page, url):
    print(f"\n[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    # avoid long networkidle; give a short settling time instead
    with contextlib.suppress(Exception):
        page.wait_for_load_state("load", timeout=10000)
    page.wait_for_timeout(200)
    close_cookies(page)

def close_cookies(page):
    for texto in ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                with contextlib.suppress(Exception):
                    page.wait_for_timeout(150)
        except Exception:
            pass

def try_visualizar_em_lista(page):
    """Tenta alternar para a visão mais “simples” (lista ou sumário)."""
    with contextlib.suppress(Exception):
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            return True
    return False

def find_best_frame(context):
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        with contextlib.suppress(Exception):
            score += fr.get_by_role("combobox").count()
        with contextlib.suppress(Exception):
            score += fr.locator("select").count()
        with contextlib.suppress(Exception):
            score += fr.get_by_role("textbox").count()
        if score > best_score:
            best_score = score
            best = fr
    return best

