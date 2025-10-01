# query_utils.py
# Utilitários para aplicar busca e coletar links no DOU

import re

def apply_query(frame, query: str):
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
    frame.page.wait_for_load_state("networkidle", timeout=90000)

def collect_links(frame, max_links: int = 30, max_scrolls: int = 40, scroll_pause_ms: int = 350, stable_rounds: int = 3):
    page = frame.page
    # Aguarda breve estabilização
    try:
        page.wait_for_timeout(500)
    except Exception:
        pass

    selectors = [
        "#hierarchy_content a[href*='/web/dou/']",
        "article a[href*='/web/dou/']",
        "main a[href*='/web/dou/']",
        "section a[href*='/web/dou/']",
        "a.card__link[href*='/web/dou/']",
        "a[href*='/web/dou/']",
    ]

    # Escolher o melhor frame + locator (primeiro tenta o frame fornecido)
    frames = [frame] + [f for f in page.frames if f is not frame]
    best = None
    best_cnt = -1
    best_frame = frame
    for fr in frames:
        for sel in selectors:
            try:
                loc = fr.locator(sel)
                cnt = loc.count()
                if cnt > best_cnt:
                    best = loc
                    best_cnt = cnt
                    best_frame = fr
            except Exception:
                continue
    anchors = best or frame.locator("a[href*='/web/dou/']")
    active_frame = best_frame

    # Tente "carregar mais"/"ver mais" dentro do frame ativo
    for _ in range(5):
        try:
            btn = active_frame.get_by_role("button", name=re.compile(r"(carregar|ver).*(mais|resultados)", re.I)).first
            if btn and btn.count() > 0 and btn.is_visible():
                btn.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                active_frame.wait_for_timeout(200)
            else:
                break
        except Exception:
            break

    # Scroll incremental no frame e na página
    last = -1
    stable = 0
    for _ in range(max_scrolls):
        try:
            count = anchors.count()
        except Exception:
            count = 0
        if count >= max_links:
            break
        if count == last:
            stable += 1
        else:
            stable = 0
        if stable >= stable_rounds:
            break
        last = count
        try:
            active_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        try:
            active_frame.wait_for_timeout(scroll_pause_ms)
        except Exception:
            pass

    # Extrair itens
    items = []
    try:
        total = anchors.count()
    except Exception:
        total = 0
    for i in range(min(total, max_links)):
        a = anchors.nth(i)
        try:
            titulo = (a.text_content() or "").strip()
            link = a.get_attribute("href") or ""
            if titulo and link:
                items.append({"titulo": titulo, "link": link})
        except Exception:
            continue
    return items
