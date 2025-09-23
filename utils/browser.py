# utils/browser.py
# Funções de manipulação do navegador e Playwright

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

def fmt_date(date_str: Optional[str] = None) -> str:
    """Formata uma data ou retorna a data atual."""
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")

def close_cookies(page) -> None:
    """Fecha pop-ups de cookies comuns."""
    for texto in ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(150)
        except Exception:
            pass

def goto(page, data: str, secao: str) -> None:
    """Navega para página do DOU com data e seção específicas."""
    url = f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
    print(f"[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)
    close_cookies(page)
    # alternar visão se necessário
    try_visualizar_em_lista(page)

def try_visualizar_em_lista(page) -> bool:
    """Tenta alternar para a visão mais 'simples' (lista ou sumário)."""
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    return False

def find_best_frame(context):
    """Encontra o frame com mais elementos interativos."""
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        try:
            score += fr.get_by_role("combobox").count()
        except Exception:
            pass
        try:
            score += fr.locator("select").count()
        except Exception:
            pass
        try:
            score += fr.get_by_role("textbox").count()
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best = fr
    return best

def dump_debug(page, prefix="debug") -> None:
    """Salva screenshot e HTML para debugging."""
    try: 
        page.screenshot(path=f"{prefix}.png", full_page=True)
    except Exception: 
        pass
    try:
        html = page.content()
        Path(f"{prefix}.html").write_text(html, encoding="utf-8")
    except Exception: 
        pass

def text_of(locator) -> str:
    """Extrai texto de um elemento de forma segura."""
    try:
        return (locator.text_content() or "").strip()
    except Exception:
        return ""

def meta_content(page, selector: str) -> Optional[str]:
    """Extrai conteúdo de uma meta tag."""
    try:
        value = page.locator(selector).first.get_attribute("content")
        return value.strip() if value else None
    except Exception:
        return None
