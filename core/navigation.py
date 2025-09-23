# core/navigation.py
# Funções para navegação e interação com páginas

import re
from playwright.sync_api import Page, Frame, BrowserContext

def close_cookies(page: Page) -> None:
    """Tenta fechar banners de cookies."""
    for texto in ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(150)
        except Exception:
            pass

def goto(page, data: str, secao: str) -> None:
    """
    Navega para a página do DOU e aguarda carregamento completo.
    """
    url = f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
    print(f"\n[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)
    close_cookies(page)
    
    # Verificação adicional de carregamento
    try:
        page.wait_for_selector("#hierarchy_content, #conteudoDOU", timeout=10000)
    except:
        pass
        
    # Tentar "Visualizar em Lista" OU "Visualizar em Sumário"
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

def find_best_frame(context: BrowserContext) -> Frame:
    """Encontra o frame mais adequado para interação."""
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

def apply_query(frame: Frame, query: str = None) -> None:
    """Aplica uma consulta no campo de busca da página."""
    if not query:
        return
    locs = [
        lambda f: f.locator("#search-bar").first,
        lambda f: f.get_by_role("searchbox").first,
        lambda f: f.get_by_role("textbox", name=re.compile("pesquis", re.I)).first,
        lambda f: f.locator('input[placeholder*="esquis" i]').first,
        lambda f: f.locator('input[type="search"]').first,
        lambda f: f.locator('input[aria-label*="pesquis" i]').first,
        lambda f: f.locator('input[id*="pesquis" i], input[name*="pesquis" i]').first,
    ]
    sb = None
    for get in locs:
        try:
            cand = get(frame)
            if cand and cand.count() > 0:
                cand.wait_for(state="visible", timeout=5000)
                sb = cand
                break
        except Exception:
            continue
    if not sb:
        print("[Aviso] Campo de busca não encontrado; seguindo sem query.")
        return
    try:
        sb.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    try:
        sb.fill(query)
    except Exception:
        sb.evaluate(
            "(el, val) => { el.value = val; el.dispatchEvent(new Event('input',{bubbles:true})); }",
            query
        )
    try:
        sb.press("Enter")
    except Exception:
        try:
            bt = frame.get_by_role("button", name=re.compile("pesquis", re.I))
            if bt.count() > 0 and bt.first.is_visible():
                bt.first.click()
        except Exception:
            pass
    frame.page.wait_for_load_state("networkidle", timeout=90_000)
